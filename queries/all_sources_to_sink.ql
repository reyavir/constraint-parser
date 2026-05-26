/**
 * @name All sources reaching a target write
 * @description Stage 1 / Row 3 — exclusivity.
 *   Enumerates every property-access source that taint-flows into a write
 *   on the target element. The Python dispatcher then checks that the
 *   only contributing element is the expected action.
 *
 *   Placeholder __TARGET_ID__ is substituted by src/static_checks.py
 *   before the query is run. (No __ACTION_ID__ — the point of this
 *   primitive is to *discover* sources, not assume one.)
 *
 *   The select returns the contributing element id and the location of
 *   the source read, so Python can both count distinct sources and tell
 *   the user where they came from.
 */

import javascript
import semmle.javascript.dataflow.TaintTracking

/** ref refers (directly or via a cached const) to the DOM element id. */
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

/** Holds if pa is a property read on the DOM element with id *src_id*. */
predicate isElementPropRead(string src_id, PropAccess pa) {
  isElementRef(src_id, pa.getBase()) and
  pa.getPropertyName() in ["value", "textContent", "innerText", "innerHTML", "checked"]
}

class AnyElementToTarget extends TaintTracking::Configuration {
  AnyElementToTarget() { this = "AnyElementToTarget" }

  /** Source: a property read on *any* element with an id in the project. */
  override predicate isSource(DataFlow::Node src) {
    exists(string id, PropAccess pa |
      isElementPropRead(id, pa) and
      src = DataFlow::valueNode(pa)
    )
  }

  /** Sink: the right-hand side of a write on the target element. */
  override predicate isSink(DataFlow::Node sink) {
    exists(AssignExpr write, PropAccess lhs |
      write.getLhs() = lhs and
      isElementRef("__TARGET_ID__", lhs.getBase()) and
      sink = DataFlow::valueNode(write.getRhs())
    )
  }

  /**
   * Value flows used by these constraints routinely pass through numeric
   * arithmetic (`r(x) + 1`) and parse/convert calls (`parseInt(x)`), which
   * the default string-oriented taint config does not propagate. Add them
   * so self-increment / sum expressions stay connected end to end.
   */
  override predicate isAdditionalTaintStep(DataFlow::Node pred, DataFlow::Node succ) {
    exists(BinaryExpr be |
      (be instanceof AddExpr or be instanceof SubExpr or
       be instanceof MulExpr or be instanceof DivExpr) and
      be.getAnOperand() = pred.asExpr() and
      succ = DataFlow::valueNode(be)
    )
    or
    exists(CallExpr ce |
      ce.getCalleeName() = ["parseInt", "parseFloat", "Number", "String"] and
      ce.getAnArgument() = pred.asExpr() and
      succ = DataFlow::valueNode(ce)
    )
  }
}

from AnyElementToTarget cfg, DataFlow::Node src, DataFlow::Node sink, string src_id
where
  cfg.hasFlow(src, sink) and
  isElementPropRead(src_id, src.asExpr().(PropAccess))
select
  src_id                                            as source_id,
  src.asExpr().getFile().getRelativePath()          as file,
  src.asExpr().getLocation().getStartLine()         as line
