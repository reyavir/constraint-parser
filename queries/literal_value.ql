/**
 * @name Target write assigns a specific literal
 * @description Stage 1 / Row C — P(w(ej, k) | A(ei)) = 1 where k is a constant.
 *   Confirms a write to the target element, reachable from the action's
 *   handler, assigns the literal __LITERAL__ as its right-hand side.
 *
 *   `Literal.getRawValue()` gives the source text for numbers/booleans and
 *   the unquoted contents for strings, so the dispatcher substitutes the
 *   bare value (e.g. 0, "" , Cart cleared).
 *
 *   Placeholders __ACTION_ID__, __TARGET_ID__, __LITERAL__ are substituted
 *   by src/static_checks.py.
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

/** The literal's value rendered as a string, for both numbers and strings. */
string literalValue(Literal lit) {
  result = lit.(StringLiteral).getValue()
  or
  result = lit.(NumberLiteral).getValue()
  or
  (lit instanceof NullLiteral and result = "null")
}

from Function handler, AssignExpr write, Function writeFn, Literal lit
where
  registeredHandler("__ACTION_ID__", handler) and
  writesElement("__TARGET_ID__", write) and
  writeFn = write.getEnclosingFunction() and
  reaches(handler, writeFn) and
  lit = write.getRhs() and
  literalValue(lit) = "__LITERAL__"
select
  write.getFile().getRelativePath()       as file,
  write.getLocation().getStartLine()      as line,
  literalValue(lit)                        as value
