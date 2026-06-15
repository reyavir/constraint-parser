/**
 * @name All sources reaching a target write inside an action handler
 * @description Stage 1 / Row 3 — exclusivity.
 *   Enumerates every property-access source that taint-flows into a
 *   write on the target — *restricted to write sites inside the
 *   specified action's handler*. The Python dispatcher then checks
 *   that the only contributing element is the expected one.
 *
 *   Why scoped to the action handler:
 *     Storage keys can be written from multiple handlers (e.g. one
 *     "save" button writes user input, one "reset" button writes a
 *     constant). Without handler scoping the source set is pooled
 *     across all handlers and a constant-write handler would
 *     spuriously satisfy a "value derives from r(ei)" claim because
 *     a sibling handler does. DOM IDs rarely collide this way, so
 *     the older unscoped version happened to work — until storage
 *     keys arrived.
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py before the query is run.
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

/** Function registered as a handler on the element with id *id*.
 *  Includes the reserved synthetic id `page-load` for window/document
 *  load and DOMContentLoaded lifecycle events. */
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

/** Holds if pa is a property read on the DOM element with id *src_id*. */
predicate isElementPropRead(string src_id, PropAccess pa) {
  isElementRef(src_id, pa.getBase()) and
  pa.getPropertyName() in ["value", "textContent", "innerText", "innerHTML", "checked"]
}

/**
 * Holds if *call* is `localStorage.getItem(key)` or
 * `sessionStorage.getItem(key)` for the given *key*. Storage reads count
 * as sources for constraints that name a storage entry in `r(...)`.
 */
predicate isStorageRead(string key, MethodCallExpr call) {
  call.getMethodName() = "getItem" and
  call.getArgument(0).getStringValue() = key and
  exists(VarRef base |
    base = call.getReceiver() and
    base.getName() = ["localStorage", "sessionStorage"]
  )
}

class AnyElementToTarget extends TaintTracking::Configuration {
  AnyElementToTarget() { this = "AnyElementToTarget" }

  /** Source: a property read on any DOM element, OR a storage getItem call. */
  override predicate isSource(DataFlow::Node src) {
    exists(string id, PropAccess pa |
      isElementPropRead(id, pa) and
      src = DataFlow::valueNode(pa)
    )
    or
    exists(string key, MethodCallExpr call |
      isStorageRead(key, call) and
      src = DataFlow::valueNode(call)
    )
  }

  /**
   * Barrier: storage getItem calls. CodeQL's taint tracking otherwise
   * follows `setItem(key, x)` → `getItem(key)` chains transitively, which
   * would surface the setItem-side source (e.g. the input that wrote
   * the storage) as a source of the getItem-side read. We treat the
   * getItem call as a fresh source AND a barrier — taint stops here,
   * and the storage read itself becomes the only reported source.
   */

  /**
   * Sink: the RHS of a write on the target DOM element, OR the
   * value arg of `localStorage.setItem(key, …)` / `sessionStorage.setItem(key, …)`
   * for the constraint's storage key. The storage disjunct self-disables
   * for DOM-only constraints via the empty-string guard.
   */
  override predicate isSink(DataFlow::Node sink) {
    exists(AssignExpr write, PropAccess lhs |
      write.getLhs() = lhs and
      isElementRef("__TARGET_ID__", lhs.getBase()) and
      sink = DataFlow::valueNode(write.getRhs())
    )
    or
    exists(MethodCallExpr call |
      "__STORAGE_KEY__" != "" and
      call.getMethodName() = "setItem" and
      call.getArgument(0).getStringValue() = "__STORAGE_KEY__" and
      exists(VarRef base |
        base = call.getReceiver() and
        base.getName() = ["localStorage", "sessionStorage"]
      ) and
      sink = DataFlow::valueNode(call.getArgument(1))
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

from AnyElementToTarget cfg, DataFlow::Node src, DataFlow::Node sink,
     string src_id, Function handler, Expr writeSite
where
  registeredHandler("__ACTION_ID__", handler) and
  cfg.hasFlow(src, sink) and
  (
    isElementPropRead(src_id, src.asExpr().(PropAccess))
    or
    exists(MethodCallExpr call |
      call = src.asExpr() and
      isStorageRead(src_id, call)
    )
  ) and
  // Tie the dataflow sink to a concrete write site so we can scope the
  // write site (not just the dataflow node) to the action's handler.
  // Without this, a write to the same target inside a *different*
  // handler can still match the dataflow sink and produce spurious
  // "extra source" rows. See test-app-slack pageload smoke test for
  // the regression that motivated this scoping.
  (
    exists(AssignExpr w |
      w = writeSite and
      isElementRef("__TARGET_ID__", w.getLhs().(PropAccess).getBase()) and
      sink = DataFlow::valueNode(w.getRhs())
    )
    or
    exists(MethodCallExpr c |
      c = writeSite and
      "__STORAGE_KEY__" != "" and
      c.getMethodName() = "setItem" and
      c.getArgument(0).getStringValue() = "__STORAGE_KEY__" and
      exists(VarRef base |
        base = c.getReceiver() and
        base.getName() = ["localStorage", "sessionStorage"]
      ) and
      sink = DataFlow::valueNode(c.getArgument(1))
    )
  ) and
  // Both the write site AND the source expression must be inside the
  // action's handler body. Requiring just the write site lets storage
  // round-trips (setItem in handler A → getItem in handler B) surface
  // handler A's input as a "source" for handler B; requiring the source
  // too cuts that cross-handler bleed-through. Direct intra-handler
  // dataflow (input → write in the same handler) still works because
  // both endpoints live in the same body.
  handler.getBody().getAChildStmt*().getAChildExpr*() = writeSite and
  handler.getBody().getAChildStmt*().getAChildExpr*() = src.asExpr()
select
  src_id                                            as source_id,
  src.asExpr().getFile().getRelativePath()          as file,
  src.asExpr().getLocation().getStartLine()         as line
