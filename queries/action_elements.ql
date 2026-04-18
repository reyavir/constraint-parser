import javascript

from HTML::Element el
where
  el.getName() in ["button", "input", "select", "textarea", "form"] and
  exists(el.getAttributeByName("id"))
select
  el.getName()                            as tag,
  el.getAttributeByName("id").getValue() as dom_id,
  el.getFile().getRelativePath()          as file,
  el.getLocation().getStartLine()         as line
