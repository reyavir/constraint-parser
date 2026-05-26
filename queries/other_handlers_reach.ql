/**
 * @name Other handlers reach target write
 * @description Stage 1 / Rows 4 & 6 — counterfactual.
 *   Lists every event handler in the codebase (registered via
 *   `addEventListener`) *other than* the expected action's handler from
 *   which a write to the target element is reachable. If this query
 *   returns any rows, the constraint P(w(target) | A(action)) = 0
 *   (equivalently P(w(target) | ¬A(action)) = 0) is violated — some
 *   other interaction also writes the target.
 *
 *   Placeholders __ACTION_ID__ (the expected handler — its writes are
 *   excluded) and __TARGET_ID__ (the protected target) are substituted
 *   by src/static_checks.py.
 *
 *   Reachability is the same intra-file callsDirect transitive closure
 *   used by path_exists.ql — same caveat: cross-file calls aren't
 *   followed.
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

/** Function registered as a handler on the element with id *id*. */
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

/** Any handler registered on any element id we can resolve. */
predicate anyRegisteredHandler(string id, Function fn) {
  registeredHandler(id, fn)
}

predicate writesElement(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    isElementRef(id, lhs.getBase())
  )
}

predicate callsDirect(Function caller, Function callee) {
  exists(InvokeExpr invoke, VarRef ref |
    invoke.getEnclosingFunction() = caller and
    ref = invoke.getCallee() and
    callee.getName() = ref.getName() and
    callee.getFile() = caller.getFile()
  )
}

predicate reaches(Function caller, Function callee) {
  caller = callee
  or
  exists(Function mid | callsDirect(caller, mid) and reaches(mid, callee))
}

from string other_id, Function handler, AssignExpr write, Function writeFn
where
  anyRegisteredHandler(other_id, handler) and
  other_id != "__ACTION_ID__" and
  writesElement("__TARGET_ID__", write) and
  writeFn = write.getEnclosingFunction() and
  reaches(handler, writeFn)
select
  other_id                                      as other_handler_id,
  write.getFile().getRelativePath()             as file,
  write.getLocation().getStartLine()            as line
