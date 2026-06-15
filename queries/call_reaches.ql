/**
 * @name Action handler reaches a call to the named function (API call)
 * @description Stage 1 — reachability check for `P(call(api) | A(ei))`.
 *   Returns one row per call site, reachable (intra-file, transitive)
 *   from the action's event handler, that invokes a function whose
 *   name matches __API_NAME__.
 *
 *   Verdict mapping (in src/static_checks.py):
 *     - constraint expects P = 1 → PASS iff ≥1 row (handler reaches a call)
 *     - constraint expects P = 0 → PASS iff zero rows (handler never calls)
 *
 *   Honest scope limits:
 *     - Name-based matching of the called function (`fn-name`). Does not
 *       distinguish overloads or namespaced calls (e.g. `db.put(...)`
 *       would match `__API_NAME__ = "put"`; `dbPut(...)` would match
 *       `__API_NAME__ = "dbPut"`).
 *     - Intra-file reachability only — handler → helper → fetch chains
 *       inside the same file are followed; cross-file calls are not.
 *
 *   Placeholders __ACTION_ID__, __API_NAME__, __DATASET_KEYS__ are
 *   substituted by src/static_checks.py.
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

/** Pattern E — page-load lifecycle (reserved synthetic id). */
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

bindingset[id]
predicate registeredHandler(string id, Function fn) {
  registeredHandlerById(id, fn)
  or
  registeredViaPageLoad(id, fn)
}

/** Direct or method-style call whose called-name matches *name*. */
predicate isCallToNamed(string name, InvokeExpr call) {
  // Plain call: foo(...)
  exists(VarRef ref |
    ref = call.getCallee() and
    ref.getName() = name
  )
  or
  // Method call: obj.foo(...) — match on the property name.
  exists(MethodCallExpr mc |
    mc = call and
    mc.getMethodName() = name
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

from Function handler, InvokeExpr callSite, Function callFn
where
  registeredHandler("__ACTION_ID__", handler) and
  reaches(handler, callFn) and
  isCallToNamed("__API_NAME__", callSite) and
  callSite.getEnclosingFunction() = callFn
select
  callSite.getFile().getRelativePath()         as file,
  callSite.getLocation().getStartLine()        as line,
  callSite.toString()                          as call_text
