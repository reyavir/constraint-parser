import javascript

from AssignExpr assign
where
  assign.getLhs().(PropAccess).getPropertyName() in
    ["textContent", "innerHTML", "innerText", "value"]
select
  assign.getLhs().(PropAccess).getPropertyName()    as write_property,
  assign.getLhs().(PropAccess).getBase().toString() as element,
  assign.getFile().getRelativePath()                as file,
  assign.getLocation().getStartLine()               as line
