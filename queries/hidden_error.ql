/**
 * Finds catch clauses with no data path to a DOM write.
 *
 * A catch clause that never writes to textContent, innerHTML, innerText,
 * or value is a silent failure — the user sees nothing when an error occurs.
 */

import javascript

from CatchClause catch
where not exists(AssignExpr assign |
  // The assign is anywhere inside this catch body (any depth)
  assign.getEnclosingStmt().nestedIn(catch.getBody()) and
  // And it writes to a visible DOM property
  assign.getLhs().(PropAccess).getPropertyName() in
    ["textContent", "innerHTML", "innerText", "value"]
)
select
  catch.getFile().getRelativePath() as file,
  catch.getLocation().getStartLine() as line
