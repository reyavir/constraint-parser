/**
 * @name Taint path from action element to target write
 * @description Stage 1, Check 2.
 *   Verifies a taint-tracking path exists from a read of the action
 *   element (.value / .textContent / …) to the right-hand side of a
 *   write on the target element. Confirms the written value actually
 *   derives from the user-controlled action element rather than a
 *   coincidence.
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py before the query is run.
 */

import javascript
import semmle.javascript.dataflow.TaintTracking

/**
 * Holds if *ref* refers (directly or via a cached const) to the DOM element
 * with the given *id*. Mirrors the predicate in path_exists.ql.
 */
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

class ActionToTarget extends TaintTracking::Configuration {
  ActionToTarget() { this = "ActionToTarget" }

  override predicate isSource(DataFlow::Node src) {
    exists(PropAccess pa |
      isElementRef("__ACTION_ID__", pa.getBase()) and
      pa.getPropertyName() in ["value", "textContent", "innerText", "innerHTML"] and
      src = DataFlow::valueNode(pa)
    )
  }

  override predicate isSink(DataFlow::Node sink) {
    exists(AssignExpr write, PropAccess lhs |
      write.getLhs() = lhs and
      isElementRef("__TARGET_ID__", lhs.getBase()) and
      sink = DataFlow::valueNode(write.getRhs())
    )
  }
}

from ActionToTarget cfg, DataFlow::Node src, DataFlow::Node sink
where cfg.hasFlow(src, sink)
select
  src.asExpr().getFile().getRelativePath() as file,
  src.asExpr().getLocation().getStartLine() as line
