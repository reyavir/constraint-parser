/**
 * @name At least one handler is recognised for the action element
 * @description Sanity-check probe run before any other primitive.
 *
 *   Stage-1 queries enumerate exit points from a handler function. When
 *   no handler is recognised (e.g. the binding uses body delegation or
 *   `.onclick = fn`, neither of which the queries match), the `from`
 *   clause returns zero rows. Some primitives interpret zero rows as
 *   PASS (vacuously: "no exit path skips the write — there are no
 *   exits") which is misleading.
 *
 *   This query emits one row per recognised handler. The dispatcher
 *   treats zero rows as "no handler recognised" and SKIPs the
 *   downstream primitives with an explicit reason, instead of letting
 *   them produce vacuous PASS verdicts.
 *
 *   Recognised binding patterns mirror those in `registeredHandler`
 *   across the other queries — id-based addEventListener plus
 *   class-based querySelectorAll(...).forEach(...).
 *
 *   Placeholder __ACTION_ID__ is substituted by src/static_checks.py.
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

/**
 * Pattern C — body-level event delegation. The single document/window
 * click listener filters incoming events and dispatches. Two filter
 * shapes are recognised:
 *
 *   1. Dataset truthy check: `if (e.target.dataset.add)` — fires for
 *      any element with `data-add`. Matched against *datasetKey* (a
 *      camelCase attribute name like "add").
 *   2. Id equality:           `if (e.target.id === "X")` — fires for
 *      the element with id X. Matched against *id*.
 *
 * The "handler" returned is the dispatching callback itself (not a
 * narrower branch). Downstream universality checks like
 * all_paths_write may pessimistically FAIL for delegated handlers
 * because the callback has many branches; only path_exists reliably
 * succeeds in this mode.
 *
 * Receiver must be a top-level global object (`document`, `window`, or
 * `document.body`) — narrow on-element addEventListener is already
 * covered by registeredHandlerById.
 */
bindingset[id, datasetKey]
predicate registeredViaBodyDelegation(string id, string datasetKey, Function fn) {
  exists(MethodCallExpr addEvt, Function cb |
    addEvt.getMethodName() = "addEventListener" and
    isGlobalListenerTarget(addEvt.getReceiver()) and
    cb = addEvt.getArgument(1) and
    (
      // Filter shape 1: e.target.dataset.<datasetKey>
      exists(PropAccess dsAccess, PropAccess datasetProp |
        dsAccess.getEnclosingFunction() = cb and
        dsAccess.getPropertyName() = datasetKey and
        datasetProp = dsAccess.getBase() and
        datasetProp.getPropertyName() = "dataset"
      )
      or
      // Filter shape 2: comparison `e.target.id === "id"` or `== "id"`
      exists(EqualityTest eq, Expr lit |
        eq.getEnclosingFunction() = cb and
        eq.getAnOperand() = lit and
        lit.getStringValue() = id
      )
    ) and
    fn = cb
  )
}

/** Receiver is a top-level listener target — document, window, or
 *  document.body. Narrow per-element listeners are not body delegation. */
predicate isGlobalListenerTarget(Expr e) {
  e.(VarRef).getName() = ["document", "window"]
  or
  exists(PropAccess pa | pa = e |
    pa.getPropertyName() = "body" and
    pa.getBase().(VarRef).getName() = "document"
  )
}

/**
 * Pattern D — handler bound by iterating a const string array and
 * computing the id from a prefix concatenated with the loop variable:
 *
 *     const IDS = ['charger', 'earbuds'];
 *     IDS.forEach(id => {
 *       document.getElementById('add-' + id).addEventListener('click', fn);
 *     });
 *
 * For each element X in IDS, we register `prefix + X` as a recognised
 * action id. Constraints `A(add-charger)`, `A(add-earbuds)` etc. then
 * resolve to the inner callback as the handler.
 *
 * Limitations:
 *   - Array must be a const literal of string elements (no dynamic
 *     construction, no spreads).
 *   - Concatenation must be exactly `<string literal> + <loop var>` or
 *     `<loop var> + <string literal>` (both orders supported).
 *   - One-level forEach only. Nested loops aren't recognised.
 */
bindingset[id]
predicate registeredViaArrayForEachId(string id, Function fn) {
  exists(MethodCallExpr forEach, ArrayExpr arr, Function cb,
         Variable loopVar, MethodCallExpr getEl, AddExpr concatExpr,
         MethodCallExpr addEvt, string prefix, string suffix |
    forEach.getMethodName() = "forEach" and
    // Receiver is a VarRef whose declared variable's initializer is an array literal.
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
      // prefix + loopVar
      concatExpr.getLeftOperand().getStringValue() = prefix and
      concatExpr.getRightOperand().(VarRef).getVariable() = loopVar
      or
      // loopVar + prefix
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

/** Pattern E — page-load lifecycle.
 *  Matches `window.addEventListener("load"|"DOMContentLoaded", fn)`,
 *  `document.addEventListener("DOMContentLoaded", fn)`, and
 *  `window.onload = fn`. The synthetic id `page-load` is reserved
 *  for this — the branch is silently dormant for every other id. */
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

bindingset[id]
predicate registeredHandler(string id, Function fn) {
  registeredHandlerById(id, fn)
  or
  exists(string cls |
    id.matches(".%") and
    cls = id.suffix(1) and
    registeredViaForEach(cls, fn)
  )
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

from Function fn
where registeredHandler("__ACTION_ID__", fn)
select
  fn.getFile().getRelativePath()    as file,
  fn.getLocation().getStartLine()   as line
