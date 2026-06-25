/**
 * @name Path exists from action handler to target write
 * @description Stage 1, Check 1.
 *   At least one code path that, starting from an event listener registered
 *   on the action element, reaches a write on the target element — either
 *   inside the handler itself or in a function the handler transitively
 *   calls. Recognises the common pattern of caching
 *   `document.getElementById('foo')` in a top-level const.
 *
 *   Placeholders __ACTION_ID__ and __TARGET_ID__ are substituted by
 *   src/static_checks.py before the query is run.
 */

import javascript

/**
 * Holds if *ref* refers (directly or via a cached const) to the DOM element
 * with the given *id*.
 */
predicate isElementRef(string id, Expr ref) {
  // Direct: `document.getElementById(id)`
  exists(MethodCallExpr mc | mc = ref |
    mc.getMethodName() = "getElementById" and
    mc.getArgument(0).getStringValue() = id
  )
  or
  // Cached: `const x = document.getElementById(id); … x …`
  exists(VariableDeclarator decl, MethodCallExpr getEl, Variable v |
    getEl = decl.getInit() and
    getEl.getMethodName() = "getElementById" and
    getEl.getArgument(0).getStringValue() = id and
    v = decl.getBindingPattern().(VarRef).getVariable() and
    ref.(VarRef).getVariable() = v
  )
}

/**
 * Function registered as a handler on the element identified by *id*.
 * *id* is either:
 *   - a DOM id (the receiver is `getElementById(id)` or a cached ref); or
 *   - a class selector "`.cls`" (binding via `querySelectorAll('.cls')`).
 *
 * The class-selector branch recognises only Pattern A — `querySelectorAll(...).forEach(el => el.addEventListener(...))`. Event-delegation (Pattern B: a parent's
 * addEventListener that filters by `e.target.matches('.cls')`) is not
 * yet recognised; add a disjunct here when that comes up.
 */
// Id-based binding is enumerable — isElementRef provides id values.
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

// Class-based binding only filters id — must be invoked with id bound.
bindingset[id]
predicate registeredHandlerByClass(string id, Function fn) {
  id.matches(".%") and
  exists(string cls |
    cls = id.suffix(1) and
    registeredViaForEach(cls, fn)
  )
}

// Combined convenience predicate — accepts id-based, class-based, AND
// body-delegated binding modes when the caller provides id (which is
// the case throughout our query files, where __ACTION_ID__ is
// substituted as a constant).
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

/** Pattern D — handler bound by iterating const array of strings and
 *  computing id as `prefix + loopVar`. See handler_exists.ql. */
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

/** Pattern C — body-level event delegation. See handler_exists.ql for
 *  the full docstring; both filter shapes (e.target.dataset.<key> and
 *  e.target.id === "<id>") are recognised. */
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

/**
 * Pattern A — handler bound by iterating a class match:
 *   document.querySelectorAll('.cls').forEach(el => {
 *     el.addEventListener('click', fn);
 *   });
 * The element variable used inside the forEach callback becomes the
 * receiver of addEventListener; we tie that callback parameter back
 * to the originating querySelectorAll's class argument.
 */
predicate registeredViaForEach(string cls, Function fn) {
  exists(MethodCallExpr querySel, MethodCallExpr forEach,
         Function cb, MethodCallExpr addEvt |
    querySel.getMethodName() = "querySelectorAll" and
    querySel.getArgument(0).getStringValue() = "." + cls and
    forEach.getMethodName() = "forEach" and
    forEach.getReceiver() = querySel and
    // forEach's callback argument is itself a Function (arrow or fn-expr).
    cb = forEach.getArgument(0) and
    // The addEventListener happens *inside* that callback. Don't bother
    // tracking the parameter through to the receiver — the structural
    // "inside this callback" check is enough for typical bindings.
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

/** Assignment that writes to a property of the element with id *id*. */
predicate writesElement(string id, AssignExpr write) {
  exists(PropAccess lhs |
    lhs = write.getLhs() and
    isElementRef(id, lhs.getBase())
  )
}

/**
 * DOM-mutation method calls that change what the element renders.
 * Treated as writes alongside `el.prop = value` assignments. Methods
 * that *parse HTML strings* into new DOM nodes (`insertAdjacentHTML`,
 * and innerHTML-as-creation) are deliberately excluded — they cannot
 * operate on a static-HTML app's existing element set. `receiver` is
 * the element being mutated (the parent for appendChild, the element
 * itself for setAttribute / remove).
 */
predicate writesElementVia(string id, MethodCallExpr call) {
  call.getMethodName() = [
    "appendChild", "append", "prepend",
    "insertBefore", "replaceChild", "replaceChildren",
    "insertAdjacentElement",
    "removeChild", "remove",
    "setAttribute"
  ] and
  isElementRef(id, call.getReceiver())
}

/**
 * Holds if *call* is `localStorage.setItem(key, …)` or
 * `sessionStorage.setItem(key, …)` for the given *key*. The
 * `key != ""` guard means the storage branch is silently disabled
 * for DOM-only constraints (where the renderer substitutes an
 * empty string for __STORAGE_KEY__).
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

/** Direct call from caller to a named function in the same file. */
predicate callsDirect(Function caller, Function callee) {
  exists(InvokeExpr invoke, VarRef ref |
    invoke.getEnclosingFunction() = caller and
    ref = invoke.getCallee() and
    callee.getName() = ref.getName() and
    callee.getFile() = caller.getFile()
  )
}

/** Transitive closure of callsDirect, plus reflexivity. */
predicate reaches(Function caller, Function callee) {
  caller = callee
  or
  exists(Function mid | callsDirect(caller, mid) and reaches(mid, callee))
}

from Function handler, Expr writingSite, Function writeFn
where
  registeredHandler("__ACTION_ID__", handler) and
  reaches(handler, writeFn) and
  (
    exists(AssignExpr w |
      writesElement("__TARGET_ID__", w) and
      w.getEnclosingFunction() = writeFn and
      writingSite = w
    )
    or
    exists(MethodCallExpr c |
      writesElementVia("__TARGET_ID__", c) and
      c.getEnclosingFunction() = writeFn and
      writingSite = c
    )
    or
    exists(MethodCallExpr c |
      writesStorage("__STORAGE_KEY__", c) and
      c.getEnclosingFunction() = writeFn and
      writingSite = c
    )
  )
select
  writingSite.getFile().getRelativePath() as file,
  writingSite.getLocation().getStartLine() as line
