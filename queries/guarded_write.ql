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

from Function handler, AssignExpr write, IfStmt guard
where
  registeredHandler("__ACTION_ID__", handler) and
  writesElement("__TARGET_ID__", write) and
  // Write must be inside the handler.
  write.getEnclosingFunction() = handler and
  // Write's statement is lexically nested inside the guard if-statement.
  write.getEnclosingStmt().getParentStmt*() = guard and
  // Guard's condition reads the guarded element.
  readsAction("__GUARD_ID__", guard.getCondition())
select
  write.getFile().getRelativePath()         as file,
  write.getLocation().getStartLine()        as line,
  guard.getLocation().getStartLine()        as guard_line
