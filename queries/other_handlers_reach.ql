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

/** Function registered as a handler on the element with id *id* (or
 *  bound via class selector `.cls`). See path_exists.ql for details. */
// Id-based — enumerable; used by anyRegisteredHandler to walk every
// concrete-id handler in the codebase. Class-based selectors are
// intentionally omitted from "other handlers reach" — they're not
// addressable by an id that would compare against __ACTION_ID__.
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

/** Pattern A — handler bound by querySelectorAll(...).forEach(el =>
 *  el.addEventListener(...)). */
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

/** Any handler registered on any element id we can resolve. */
predicate anyRegisteredHandler(string id, Function fn) {
  registeredHandlerById(id, fn)
  or
  (
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
  )
}

predicate writesElement(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    isElementRef(id, lhs.getBase())
  )
}

/** DOM-mutation method calls (appendChild, replaceChildren, etc.).
 *  Methods that parse HTML strings into new DOM nodes are excluded —
 *  they cannot operate on a static-HTML app's existing element set. */
predicate writesElementVia(string id, MethodCallExpr call) {
  call.getMethodName() = [
    "appendChild", "append", "prepend",
    "insertBefore", "replaceChild", "replaceChildren",
    "insertAdjacentElement",
    "removeChild", "remove",
    "setAttribute"
  ] and
  isElementRef(id, call.getReceiver())
  or
  exists(PropAccess classListAccess |
    classListAccess = call.getReceiver() and
    classListAccess.getPropertyName() = "classList" and
    isElementRef(id, classListAccess.getBase()) and
    call.getMethodName() = ["add", "remove", "toggle", "replace"]
  )
  or
  exists(PropAccess styleAccess |
    styleAccess = call.getReceiver() and
    styleAccess.getPropertyName() = "style" and
    isElementRef(id, styleAccess.getBase()) and
    call.getMethodName() = ["setProperty", "removeProperty"]
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

from string other_id, Function handler, Expr writeSite, Function writeFn
where
  anyRegisteredHandler(other_id, handler) and
  other_id != "__ACTION_ID__" and
  (
    exists(AssignExpr w |
      writesElement("__TARGET_ID__", w) and
      writeSite = w
    )
    or
    exists(MethodCallExpr c |
      writesElementVia("__TARGET_ID__", c) and
      writeSite = c
    )
  ) and
  writeFn = writeSite.getEnclosingFunction() and
  reaches(handler, writeFn)
select
  other_id                                      as other_handler_id,
  writeSite.getFile().getRelativePath()         as file,
  writeSite.getLocation().getStartLine()        as line
