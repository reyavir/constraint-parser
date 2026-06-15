/**
 * @name Page-load handler reads the named storage key
 * @description Restore-side check for `persist(target)` constraints.
 *   Returns one row if there exists a page-load handler
 *   (window.addEventListener("load"|"DOMContentLoaded", fn),
 *   document.addEventListener("DOMContentLoaded", fn), or
 *   window.onload = fn) whose body contains a
 *   `localStorage.getItem("__STORAGE_KEY__")` or
 *   `sessionStorage.getItem("__STORAGE_KEY__")` call.
 *
 *   The dispatcher pairs this with a separate save-side check
 *   (path_exists on the action handler writing the storage). Both must
 *   return rows for the persist constraint to PASS.
 *
 *   Placeholder __STORAGE_KEY__ is substituted by src/static_checks.py.
 */

import javascript

predicate isPageLoadHandler(Function fn) {
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
}

predicate isStorageGetItem(string key, MethodCallExpr call) {
  call.getMethodName() = "getItem" and
  call.getArgument(0).getStringValue() = key and
  exists(VarRef base |
    base = call.getReceiver() and
    base.getName() = ["localStorage", "sessionStorage"]
  )
}

from Function handler, MethodCallExpr getCall
where
  isPageLoadHandler(handler) and
  isStorageGetItem("__STORAGE_KEY__", getCall) and
  handler.getBody().getAChildStmt*().getAChildExpr*() = getCall
select
  getCall.getFile().getRelativePath()       as file,
  getCall.getLocation().getStartLine()      as line
