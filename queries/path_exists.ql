/**
 * @name Path exists from action handler to target write
 * @description Stage 1, Check 1.
 *   At least one code path that, starting from an event listener registered
 *   on the action element, reaches a write on the target element — either
 *   inside the handler itself or in a function the handler transitively
 *   calls. Recognises the common pattern of caching
 *   `document.getElementById('foo')` in a top-level const.
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py before the query is run.
 */

import javascript

/**
 * Holds if *ref* refers (directly or via a cached const) to the DOM element
 * with the given *id*.
 */
predicate isElementRef(string id, Expr ref) {
  // Direct: `document.getElementById(id)`
  exists(MethodCallExpr mc | mc = ref |
    mc.getMethodName() = "getElementById" and
    mc.getArgument(0).getStringValue() = id
  )
  or
  // Cached: `const x = document.getElementById(id); … x …`
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
      // Inline function literal — the arg expr IS the function
      fn = addEvt.getArgument(1)
      or
      // Named reference — match the VarRef to a Function with that name
      exists(VarRef ref |
        ref = addEvt.getArgument(1) and
        fn.getName() = ref.getName() and
        fn.getFile() = addEvt.getFile()
      )
    )
  )
}

/** Assignment that writes to a property of the element with id *id*. */
predicate writesElement(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    isElementRef(id, lhs.getBase())
  )
}

/** Direct call from caller to a named function in the same file. */
predicate callsDirect(Function caller, Function callee) {
  exists(InvokeExpr invoke, VarRef ref |
    invoke.getEnclosingFunction() = caller and
    ref = invoke.getCallee() and
    callee.getName() = ref.getName() and
    callee.getFile() = caller.getFile()
  )
}

/** Transitive closure of callsDirect, plus reflexivity. */
predicate reaches(Function caller, Function callee) {
  caller = callee
  or
  exists(Function mid | callsDirect(caller, mid) and reaches(mid, callee))
}

from Function handler, AssignExpr write, Function writeFn
where
  registeredHandler("__ACTION_ID__", handler) and
  writesElement("__TARGET_ID__", write) and
  writeFn = write.getEnclosingFunction() and
  reaches(handler, writeFn)
select
  write.getFile().getRelativePath() as file,
  write.getLocation().getStartLine() as line
