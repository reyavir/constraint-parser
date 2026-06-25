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

predicate registeredHandlerById(string id, Function fn) {
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

bindingset[id]
predicate registeredHandlerByClass(string id, Function fn) {
  id.matches(".%") and
  exists(string cls |
    cls = id.suffix(1) and
    registeredViaForEach(cls, fn)
  )
}

bindingset[id]
predicate registeredHandler(string id, Function fn) {
  registeredHandlerById(id, fn)
  or
  registeredHandlerByClass(id, fn)
  or
  exists(string datasetKey |
    datasetKey = [__DATASET_KEYS__] and
    registeredViaBodyDelegation(id, datasetKey, fn)
  )
  or
  registeredViaArrayForEachId(id, fn)
  or
  registeredViaPageLoad(id, fn)
}

/** Pattern E — page-load lifecycle. Reserved synthetic id. */
bindingset[id]
predicate registeredViaPageLoad(string id, Function fn) {
  id = "page-load" and
  (
    exists(MethodCallExpr addEvt |
      addEvt.getMethodName() = "addEventListener" and
      addEvt.getReceiver().(VarRef).getName() = ["window", "document"] and
      addEvt.getArgument(0).getStringValue() = ["load", "DOMContentLoaded"] and
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
    or
    exists(AssignExpr assign, PropAccess lhs |
      assign.getLhs() = lhs and
      lhs.getPropertyName() = "onload" and
      lhs.getBase().(VarRef).getName() = "window" and
      (
        fn = assign.getRhs()
        or
        exists(VarRef ref |
          ref = assign.getRhs() and
          fn.getName() = ref.getName() and
          fn.getFile() = assign.getFile()
        )
      )
    )
  )
}

/** Pattern D — forEach + getElementById(prefix + loopVar). See handler_exists.ql. */
bindingset[id]
predicate registeredViaArrayForEachId(string id, Function fn) {
  exists(MethodCallExpr forEach, ArrayExpr arr, Function cb,
         Variable loopVar, MethodCallExpr getEl, AddExpr concatExpr,
         MethodCallExpr addEvt, string prefix, string suffix |
    forEach.getMethodName() = "forEach" and
    exists(Variable arrVar, VariableDeclarator decl |
      forEach.getReceiver().(VarRef).getVariable() = arrVar and
      decl.getBindingPattern().(VarRef).getVariable() = arrVar and
      arr = decl.getInit()
    ) and
    suffix = arr.getAnElement().getStringValue() and
    cb = forEach.getArgument(0) and
    loopVar = cb.getAParameter().(SimpleParameter).getVariable() and
    getEl.getEnclosingFunction() = cb and
    getEl.getMethodName() = "getElementById" and
    concatExpr = getEl.getArgument(0) and
    (
      concatExpr.getLeftOperand().getStringValue() = prefix and
      concatExpr.getRightOperand().(VarRef).getVariable() = loopVar
      or
      concatExpr.getRightOperand().getStringValue() = prefix and
      concatExpr.getLeftOperand().(VarRef).getVariable() = loopVar
    ) and
    id = prefix + suffix and
    addEvt.getMethodName() = "addEventListener" and
    addEvt.getReceiver() = getEl and
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

/** Pattern C — body-level event delegation. See handler_exists.ql. */
bindingset[id, datasetKey]
predicate registeredViaBodyDelegation(string id, string datasetKey, Function fn) {
  exists(MethodCallExpr addEvt, Function cb |
    addEvt.getMethodName() = "addEventListener" and
    isGlobalListenerTarget(addEvt.getReceiver()) and
    cb = addEvt.getArgument(1) and
    (
      exists(PropAccess dsAccess, PropAccess datasetProp |
        dsAccess.getEnclosingFunction() = cb and
        dsAccess.getPropertyName() = datasetKey and
        datasetProp = dsAccess.getBase() and
        datasetProp.getPropertyName() = "dataset"
      )
      or
      exists(EqualityTest eq, Expr lit |
        eq.getEnclosingFunction() = cb and
        eq.getAnOperand() = lit and
        lit.getStringValue() = id
      )
    ) and
    fn = cb
  )
}

predicate isGlobalListenerTarget(Expr e) {
  e.(VarRef).getName() = ["document", "window"]
  or
  exists(PropAccess pa | pa = e |
    pa.getPropertyName() = "body" and
    pa.getBase().(VarRef).getName() = "document"
  )
}

/** Pattern A — handler bound by querySelectorAll(...).forEach(el =>
 *  el.addEventListener(...)). See path_exists.ql for the docstring. */
predicate registeredViaForEach(string cls, Function fn) {
  exists(MethodCallExpr querySel, MethodCallExpr forEach,
         Function cb, MethodCallExpr addEvt |
    querySel.getMethodName() = "querySelectorAll" and
    querySel.getArgument(0).getStringValue() = "." + cls and
    forEach.getMethodName() = "forEach" and
    forEach.getReceiver() = querySel and
    cb = forEach.getArgument(0) and
    addEvt.getMethodName() = "addEventListener" and
    addEvt.getEnclosingFunction() = cb and
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

/**
 * DOM-mutation method calls that change what the element renders.
 * Treated as writes alongside `el.prop = value` assignments. Methods
 * that *parse HTML strings* into new DOM nodes (insertAdjacentHTML,
 * innerHTML-as-creation) are deliberately excluded — they cannot
 * operate on a static-HTML app's existing element set.
 */
predicate writesElementVia(string id, MethodCallExpr call) {
  call.getMethodName() = [
    "appendChild", "append", "prepend",
    "insertBefore", "replaceChild", "replaceChildren",
    "insertAdjacentElement",
    "removeChild", "remove",
    "setAttribute"
  ] and
  isElementRef(id, call.getReceiver())
}

/**
 * `localStorage.setItem(key, …)` or `sessionStorage.setItem(key, …)`.
 * Disabled when __STORAGE_KEY__ is empty (DOM-only constraints).
 */
predicate writesStorage(string key, MethodCallExpr call) {
  key != "" and
  call.getMethodName() = "setItem" and
  call.getArgument(0).getStringValue() = key and
  exists(VarRef base |
    base = call.getReceiver() and
    base.getName() = ["localStorage", "sessionStorage"]
  )
}

/** A basic block in fn that directly writes the target — DOM assignment,
 *  DOM-mutation method call, or storage setItem. */
predicate writingBlock(Function fn, ReachableBasicBlock bb) {
  exists(AssignExpr w, Stmt s |
    writesElement("__TARGET_ID__", w) and
    w.getEnclosingFunction() = fn and
    s = w.getEnclosingStmt() and
    bb.getANode() = s.getFirstControlFlowNode()
  )
  or
  exists(MethodCallExpr c, Stmt s |
    writesElementVia("__TARGET_ID__", c) and
    c.getEnclosingFunction() = fn and
    s = c.getEnclosingStmt() and
    bb.getANode() = s.getFirstControlFlowNode()
  )
  or
  exists(MethodCallExpr c, Stmt s |
    writesStorage("__STORAGE_KEY__", c) and
    c.getEnclosingFunction() = fn and
    s = c.getEnclosingStmt() and
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
