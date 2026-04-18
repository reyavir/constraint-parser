import javascript

from CallExpr call
where
  (call.getCalleeName() = "fetch" or call.getReceiver().toString() = "axios") and
  exists(call.getArgument(0).getStringValue())
select
  call.getArgument(0).getStringValue()  as endpoint,
  call.getFile().getRelativePath()      as file,
  call.getLocation().getStartLine()     as line
