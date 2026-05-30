/**
 * @name All paths through handler write the target (path-based)
 * @description Stage 1 — universal/sufficient check for P(w(ej) | A(ei)) = 1.
 *
 *   Returns one row per exit point in the action's handler that is
 *   reachable from the function entry via a path passing through zero
 *   writing points. A "writing point" is either:
 *     (a) a basic block containing a direct write to the target, OR
 *     (b) a basic block calling a function that "definitely writes"
 *         the target intra-procedurally.
 *
 *   Zero rows ⇒ every entry-to-exit path through the handler passes
 *   through at least one writing point ⇒ every execution writes.
 *
 *   This is path-based rather than dominance-based: it correctly
 *   handles `if (...) { write; } else { write; }` patterns, where two
 *   different writes are on two different paths, neither dominating
 *   the join — every actual execution still writes the target.
 *
 *   Honest scope limits:
 *     - **One level** of inter-procedural delegation. A handler calling
 *       a helper that always writes the target is recognised; a handler
 *       calling A which calls B which writes is not. (Deeper chains
 *       would require recursive predicates through negation that CodeQL
 *       doesn't stratify; a depth-N predicate would have to be
 *       enumerated explicitly.)
 *     - Callee resolution is name-and-file based.
 *     - Synchronous control flow only.
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py.
 */

import javascript

predicate isElementRef(string id, Expr ref) {
  exists(MethodCallExpr mc | mc = ref |
    mc.getMethodName() = "getElementById" and
    mc.getArgument(0).getStringValue() = id
  )
  or
  exists(VariableDeclarator decl, MethodCallExpr getEl, Variable v |
    getEl = decl.getInit() and
    getEl.getMethodName() = "getElementById" and
    getEl.getArgument(0).getStringValue() = id and
    v = decl.getBindingPattern().(VarRef).getVariable() and
    ref.(VarRef).getVariable() = v
  )
}

predicate registeredHandler(string id, Function fn) {
  exists(MethodCallExpr addEvt |
    addEvt.getMethodName() = "addEventListener" and
    isElementRef(id, addEvt.getReceiver()) and
    (
      fn = addEvt.getArgument(1)
      or
      exists(VarRef ref |
        ref = addEvt.getArgument(1) and
        fn.getName() = ref.getName() and
        fn.getFile() = addEvt.getFile()
      )
    )
  )
}

predicate writesElement(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    isElementRef(id, lhs.getBase())
  )
}

/** A basic block in fn that directly assigns to the target. */
predicate writingBlock(Function fn, ReachableBasicBlock bb) {
  exists(AssignExpr w, Stmt s |
    writesElement("__TARGET_ID__", w) and
    w.getEnclosingFunction() = fn and
    s = w.getEnclosingStmt() and
    bb.getANode() = s.getFirstControlFlowNode()
  )
}

predicate callsAt(Function caller, Function callee, ReachableBasicBlock bb) {
  exists(InvokeExpr invoke, VarRef ref, Stmt s |
    invoke.getEnclosingFunction() = caller and
    ref = invoke.getCallee() and
    callee.getName() = ref.getName() and
    callee.getFile() = caller.getFile() and
    s = invoke.getEnclosingStmt() and
    bb.getANode() = s.getFirstControlFlowNode()
  )
}

predicate bbInFunction(Function fn, ReachableBasicBlock bb) {
  fn.getEntry().getBasicBlock().getASuccessor*() = bb
}

/**
 * True when *t* is inside a try-block of some try/catch in the same
 * function — i.e. the throw is caught and is just a control transfer
 * to the catch, not a function exit.
 */
predicate isCaughtThrow(ThrowStmt t) {
  exists(TryStmt try, BlockStmt body |
    try.getContainer() = t.getContainer() and
    body = try.getBody() and
    body.getAChildStmt*() = t and
    exists(try.getCatchClause())
  )
}

predicate handlerExitBB(Function fn, ReachableBasicBlock bb) {
  exists(ReturnStmt r |
    r.getContainer() = fn and
    bb.getANode() = r.getFirstControlFlowNode()
  )
  or
  exists(ThrowStmt t |
    t.getContainer() = fn and
    bb.getANode() = t.getFirstControlFlowNode() and
    not isCaughtThrow(t)
  )
  or
  bbInFunction(fn, bb) and
  not exists(ReachableBasicBlock succ |
    succ = bb.getASuccessor() and bbInFunction(fn, succ)
  )
}

// ── Intra-procedural "definitely writes" ───────────────────────────────
// No inter-procedural recursion here — only direct writes count. This
// breaks the recursive cycle through negation that CodeQL rejects.

predicate nonDirectWritingBB(Function fn, ReachableBasicBlock bb) {
  bbInFunction(fn, bb) and not writingBlock(fn, bb)
}

predicate reachableViaNonDirectWriting(Function fn,
                                        ReachableBasicBlock a,
                                        ReachableBasicBlock b) {
  a = b and nonDirectWritingBB(fn, a)
  or
  exists(ReachableBasicBlock mid |
    nonDirectWritingBB(fn, a) and
    mid = a.getASuccessor() and
    reachableViaNonDirectWriting(fn, mid, b)
  )
}

/** fn definitely writes the target through direct writes only. */
predicate definitelyDirectWrites(Function fn) {
  exists(ReachableBasicBlock anyExit | handlerExitBB(fn, anyExit)) and
  not exists(ReachableBasicBlock entry, ReachableBasicBlock exit |
    entry = fn.getEntry().getBasicBlock() and
    handlerExitBB(fn, exit) and
    reachableViaNonDirectWriting(fn, entry, exit)
  )
}

// ── Handler-level check with one level of inter-procedural ─────────────
// A writing point for the handler is either a direct write OR a call to
// a function that intra-procedurally definitely-writes. No further
// recursion needed — depth bounded at one.

predicate writingPointForHandler(Function fn, ReachableBasicBlock bb) {
  writingBlock(fn, bb)
  or
  exists(Function callee |
    callsAt(fn, callee, bb) and
    definitelyDirectWrites(callee)
  )
}

predicate nonWritingForHandler(Function fn, ReachableBasicBlock bb) {
  bbInFunction(fn, bb) and not writingPointForHandler(fn, bb)
}

predicate reachableViaNonWriting(Function fn,
                                  ReachableBasicBlock a,
                                  ReachableBasicBlock b) {
  a = b and nonWritingForHandler(fn, a)
  or
  exists(ReachableBasicBlock mid |
    nonWritingForHandler(fn, a) and
    mid = a.getASuccessor() and
    reachableViaNonWriting(fn, mid, b)
  )
}

from Function handler, ReachableBasicBlock exitBB
where
  registeredHandler("__ACTION_ID__", handler) and
  handlerExitBB(handler, exitBB) and
  exists(ReachableBasicBlock entryBB |
    entryBB = handler.getEntry().getBasicBlock() and
    reachableViaNonWriting(handler, entryBB, exitBB)
  )
select
  exitBB.getLastNode().getFile().getRelativePath()      as file,
  exitBB.getLastNode().getLocation().getStartLine()     as line
