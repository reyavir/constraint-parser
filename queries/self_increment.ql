/**
 * @name Target write adds a literal (self-increment shape)
 * @description Stage 1 / Row A — P(w(ej, r(ej) + c) | A(ei)) = 1.
 *   Confirms that a write to the target element, reachable from the
 *   action's handler, has a right-hand side whose expression tree
 *   contains an addition or subtraction with a numeric-literal operand
 *   (the "+ c" / "- c" part).
 *
 *   This is the *literal-addition* half of Row A. The complementary
 *   "value also reads the target element" half is verified separately
 *   by the source-set check (all_sources_to_sink) in the dispatcher,
 *   which confirms r(ej) actually flows into the write.
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

/** A + or - expression with at least one numeric-literal operand. */
predicate literalArith(BinaryExpr arith) {
  (arith instanceof AddExpr or arith instanceof SubExpr) and
  arith.getAnOperand() instanceof NumberLiteral
}

from Function handler, AssignExpr write, Function writeFn, BinaryExpr arith
where
  registeredHandler("__ACTION_ID__", handler) and
  writesElement("__TARGET_ID__", write) and
  writeFn = write.getEnclosingFunction() and
  reaches(handler, writeFn) and
  literalArith(arith) and
  // The arithmetic is part of the write's right-hand side expression tree,
  // OR lives in the same handler feeding the written variable.
  (
    arith = write.getRhs().getAChildExpr*()
    or
    arith.getEnclosingFunction() = writeFn
  )
select
  write.getFile().getRelativePath()       as file,
  write.getLocation().getStartLine()      as line,
  arith.getLocation().getStartLine()      as arith_line
