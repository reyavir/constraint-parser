/**
 * @name Target write derives from an API response
 * @description Stage 1 — verifies the value written to the target
 *   element taint-flows from an API response (specifically, the result
 *   of a `.json()` or `.text()` call). Used for constraints of shape
 *
 *     P(w(ej, r(api_result)) | A(ei)) = 1
 *
 *   which claim that ej's displayed value comes from whatever the API
 *   returned, not from a literal, a different element, or a hardcoded
 *   string.
 *
 *   Returns one row per (source, sink) flow found. Zero rows ⇒ no
 *   API-response taint reaches the target write ⇒ the constraint's
 *   "value from API" claim is unsupported by the code structure.
 *
 *   Honest scope:
 *     - Source = any `RemoteFlowSource`. This is CodeQL JS's canonical
 *       abstraction for "data from outside the application over a
 *       network call" — it spans fetch, axios, XHR, jQuery, etc. via
 *       framework models.
 *     - A manual `isAdditionalTaintStep` bridges the `.json()` / `.text()`
 *       parse-call step. The fetch framework model in current
 *       `codeql/javascript-all` versions doesn't always trace through
 *       this step (especially for POST + options-object patterns), so
 *       we explicitly tell the dataflow engine that taint flows from
 *       the receiver of a `.json()` / `.text()` call to its result.
 *       This is a documented workaround pattern that CodeQL's own
 *       client-side request forgery queries use.
 *     - Source does NOT distinguish *which* endpoint — any client
 *       request response counts. If the constraint syntax someday names
 *       a specific endpoint, the source predicate would tighten via
 *       URL pattern matching.
 *     - Sink scope is restricted to writes inside the action's handler
 *       (so a value flowing into a write in some unrelated function
 *       doesn't satisfy the constraint).
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py.
 */

import javascript
import semmle.javascript.dataflow.TaintTracking
import semmle.javascript.frameworks.ClientRequests

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

class ApiResponseToTarget extends TaintTracking::Configuration {
  ApiResponseToTarget() { this = "ApiResponseToTarget" }

  /**
   * Source: the parsed body of an outgoing HTTP request's response.
   *
   * Composed predicate, correct by construction:
   *   - The source is the result of a `.json()` or `.text()` call,
   *     AND the call's receiver flows from a `ClientRequest`'s
   *     `getAResponseDataNode()`.
   *
   * This excludes accidental `.json()` methods on unrelated objects
   * (they wouldn't trace back to a ClientRequest) AND excludes
   * `response.status` / `response.headers` / other Response metadata
   * (those are property reads, not parse calls). Only the actual
   * parsed body counts.
   */
  override predicate isSource(DataFlow::Node src) {
    exists(DataFlow::MethodCallNode parse, ClientRequest req |
      parse.getMethodName() = ["json", "text"] and
      (
        // Direct local-source match (no Promise wrapping in the way).
        parse.getReceiver().getALocalSource() = req.getAResponseDataNode()
        or
        // Common fetch pattern: `response = await fetch(...)`. The receiver's
        // local source is `await <fetch>`, so we strip one await level.
        exists(AwaitExpr aw |
          aw = parse.getReceiver().getALocalSource().asExpr() and
          aw.getOperand() = req.getAResponseDataNode().asExpr()
        )
      ) and
      src = parse
    )
  }

  /**
   * Sink: the RHS of a write on the target DOM element, OR the value
   * arg of `localStorage.setItem(key, …)` / `sessionStorage.setItem(key, …)`
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
   * Arithmetic + numeric-conversion steps so values transformed through
   * these operations stay tracked. No `.json()` / `.text()` bridge is
   * needed because the source predicate already starts taint at the
   * parse call's result.
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

from ApiResponseToTarget cfg, DataFlow::Node src, DataFlow::Node sink,
     Function handler, Expr writeSite
where
  registeredHandler("__ACTION_ID__", handler) and
  cfg.hasFlow(src, sink) and
  writeSite.getEnclosingFunction() = handler and
  (
    exists(AssignExpr w |
      w.getRhs() = sink.asExpr() and
      w = writeSite
    )
    or
    exists(MethodCallExpr c |
      c.getArgument(1) = sink.asExpr() and
      c = writeSite
    )
  )
select
  writeSite.getFile().getRelativePath()      as file,
  writeSite.getLocation().getStartLine()     as line
