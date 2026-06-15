/**
 * @name Action handler reaches an API call whose args derive from the named source
 * @description Stage 1 — subset-membership check for
 *   `P(call(api, r(source)) | A(action)) = 1`.
 *
 *   Returns one row per call site where:
 *     1. the action's handler reaches the call
 *     2. the call invokes a function whose name matches __API_NAME__
 *     3. taint flows from a read of __SOURCE_ID__ to any of the call's
 *        arguments
 *
 *   Subset semantics (NOT set equality): the source must reach the
 *   call's args, but other sources are allowed to mix in. This matches
 *   "is this input used somehow" intent — API calls naturally combine
 *   user input with literals and module state.
 *
 *   Verdict mapping (in src/static_checks.py):
 *     - P = 1 → PASS iff ≥1 row
 *     - P = 0 → PASS iff zero rows (the named source must NOT reach
 *               the call's args)
 *
 *   Honest scope:
 *     - Name-based matching (same as call_reaches.ql).
 *     - Intra-file reachability.
 *     - Taint follows the standard TaintTracking config used elsewhere
 *       (arithmetic, parseInt/String/Number, etc.) plus property reads.
 *
 *   Placeholders __ACTION_ID__, __API_NAME__, __SOURCE_ID__,
 *   __DATASET_KEYS__ are substituted by src/static_checks.py.
 */

import javascript
import semmle.javascript.dataflow.TaintTracking

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
predicate registeredViaPageLoad(string id, Function fn) {
  id = "page-load" and
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
}

bindingset[id]
predicate registeredHandler(string id, Function fn) {
  registeredHandlerById(id, fn)
  or
  registeredViaPageLoad(id, fn)
}

predicate isCallToNamed(string name, InvokeExpr call) {
  exists(VarRef ref |
    ref = call.getCallee() and
    ref.getName() = name
  )
  or
  exists(MethodCallExpr mc |
    mc = call and
    mc.getMethodName() = name
  )
}

/** Holds if pa is a property read on the DOM element with id *src_id*. */
predicate isElementPropRead(string src_id, PropAccess pa) {
  isElementRef(src_id, pa.getBase()) and
  pa.getPropertyName() in ["value", "textContent", "innerText", "innerHTML", "checked"]
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

class SourceToCallArg extends TaintTracking::Configuration {
  SourceToCallArg() { this = "SourceToCallArg" }

  override predicate isSource(DataFlow::Node src) {
    exists(PropAccess pa |
      isElementPropRead("__SOURCE_ID__", pa) and
      src = DataFlow::valueNode(pa)
    )
  }

  override predicate isSink(DataFlow::Node sink) {
    exists(InvokeExpr call |
      isCallToNamed("__API_NAME__", call) and
      sink = DataFlow::valueNode(call.getAnArgument())
    )
  }

  override predicate isAdditionalTaintStep(DataFlow::Node pred, DataFlow::Node succ) {
    // Arithmetic and parse/convert calls — same set as all_sources_to_sink.
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
    or
    // Object literal property value → the enclosing object literal.
    // Most real API calls wrap args in objects (e.g.
    // `dbPut('cart', { id, qty: qtyInput.value })`).
    exists(ObjectExpr obj, Property prop |
      prop.getParent() = obj and
      prop.getInit() = pred.asExpr() and
      succ = DataFlow::valueNode(obj)
    )
  }
}

from SourceToCallArg cfg, DataFlow::Node src, DataFlow::Node sink,
     Function handler, InvokeExpr callSite, Function callFn
where
  registeredHandler("__ACTION_ID__", handler) and
  reaches(handler, callFn) and
  isCallToNamed("__API_NAME__", callSite) and
  callSite.getEnclosingFunction() = callFn and
  cfg.hasFlow(src, sink) and
  sink.asExpr() = callSite.getAnArgument()
select
  callSite.getFile().getRelativePath()         as file,
  callSite.getLocation().getStartLine()        as line,
  callSite.toString()                          as call_text
