/**
 * @name Guarded write to target inside action handler
 * @description Stage 1 / Row 5 — guarded condition.
 *   Confirms that the write to the target element inside the expected
 *   action's handler is enclosed by an `if` statement whose condition
 *   reads the action element. This is the structural pre-condition for
 *   constraints of the form
 *
 *     P(w(target) | A(action), r(action) = v) = 1
 *     P(w(target) | A(action), r(action) != v) = 0
 *
 *   The query does NOT check the specific value v — comparing runtime
 *   input values to v is left to dynamic analysis. It only asserts that
 *   the code is *structured* to gate the write on a read of the guarded
 *   element.
 *
 *   Returns one row per guarded write found. The dispatcher requires
 *   at least one row to PASS.
 *
 *   Placeholders:
 *     __ACTION_ID__  the handler the write must live in
 *     __TARGET_ID__  the element being written
 *     __GUARD_ID__   the element the guarding if-condition must read
 *                    (for the canonical Row 5 this equals __ACTION_ID__,
 *                     but the grammar lets the guard read any element)
 *   are substituted by src/static_checks.py.
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

/** innerHTML assignment whose RHS embeds id="X" — treats the child
 *  element as having been written by that assignment. */
bindingset[id]
predicate isCreatedInInnerHTML(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    lhs.getPropertyName() = ["innerHTML", "outerHTML"]
  ) and
  write.getRhs().toString().regexpMatch(
    ".*\\bid\\s*=\\s*[\"']" + id + "[\"'].*"
  )
}

/** DOM-mutation method calls (appendChild, replaceChildren, etc.). */
predicate writesElementVia(string id, MethodCallExpr call) {
  call.getMethodName() = [
    "appendChild", "append", "prepend",
    "insertBefore", "replaceChild", "replaceChildren",
    "insertAdjacentHTML", "insertAdjacentElement",
    "removeChild", "remove",
    "setAttribute"
  ] and
  isElementRef(id, call.getReceiver())
}

/**
 * Storage setItem call for the given key. Mirrors path_exists.ql so that
 * constraints over a storage target (e.g. `w(draftStorage)`) can be
 * gated by an `if` the same way DOM-target constraints are. The
 * `key != ""` guard disables this branch when the dispatcher substitutes
 * an empty string for DOM-only constraints.
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

/** Holds if cond or any descendant expression reads a property of the action element. */
predicate readsAction(string id, Expr cond) {
  exists(PropAccess pa |
    pa = cond.getAChildExpr*() and
    isElementRef(id, pa.getBase()) and
    pa.getPropertyName() in ["value", "textContent", "innerText", "innerHTML", "checked"]
  )
  or
  // Also catch direct VarRef use of a cached action element.
  exists(VarRef vref |
    vref = cond.getAChildExpr*() and
    isElementRef(id, vref)
  )
}

from Function handler, Expr writeSite, IfStmt guard
where
  registeredHandler("__ACTION_ID__", handler) and
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
    or
    exists(AssignExpr w |
      isCreatedInInnerHTML("__TARGET_ID__", w) and
      writeSite = w
    )
    or
    exists(MethodCallExpr c |
      writesStorage("__STORAGE_KEY__", c) and
      writeSite = c
    )
  ) and
  // Write must be inside the handler.
  writeSite.getEnclosingFunction() = handler and
  // Write's statement is lexically nested inside the guard if-statement.
  writeSite.getEnclosingStmt().getParentStmt*() = guard and
  // Guard's condition reads the guarded element.
  readsAction("__GUARD_ID__", guard.getCondition())
select
  writeSite.getFile().getRelativePath()         as file,
  writeSite.getLocation().getStartLine()        as line,
  guard.getLocation().getStartLine()            as guard_line
