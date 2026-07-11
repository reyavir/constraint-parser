grammar Constraint;

// ── entry point ──────────────────────────────────────────────────────────────

constraint
    : prob_constraint EOF
    ;

prob_constraint
    : 'P(' logic_expr '|' logic_expr ')' probability_expr
    ;

probability_expr
    : '=' NUMBER
    ;

// ── boolean logic ────────

logic_expr
    : logic_expr OR logic_xor
    | logic_xor
    ;

logic_xor
    : logic_xor XOR logic_term
    | logic_term
    ;

logic_term
    : logic_term AND logic_factor
    | logic_factor
    ;

logic_factor
    : NOT logic_factor
    | '(' logic_expr ')'
    | atom
    ;

// ── atoms ────────────────────────────────────────────────────────────────────

atom
    : write_event
    | user_action
    | system_event
    | persist_event
    | guard
    | literal_bool
    ;

// Three write-event forms:
//   w(target)                            — existence only, no value claim
//   w(target, expr)                      — value derives from an expression
//                                          (arithmetic shape, e.g. r(x) + 1)
//   w(target, sources={r(s1), r(s2)})    — value derives from EXACTLY this
//                                          set of element reads (set
//                                          equality — no extras, no
//                                          missing). Empty set { } means
//                                          "no element sources" (literal
//                                          or api-only value).
write_event
    : 'w(' identifier ')'
    | 'w(' identifier ',' expr ')'
    | 'w(' identifier ',' 'sources=' source_set ')'
    ;

source_set
    : '{' source_item (',' source_item)* '}'
    | '{' '}'
    ;

source_item
    : 'r(' identifier ')'
    | 'r(' 'api_result' ')'
    ;

user_action
    : 'A(' identifier ')'
    ;

system_event
    : 'call(' identifier ')'
    | 'call(' identifier ',' expr ')'
    ;

// `persist(storage_target)` — true iff the action handler writes to the
// named storage AND a page-load handler reads from that same storage.
// Sugar for the conjunction of save and restore checks.
persist_event
    : 'persist(' identifier ')'
    ;

// ── expressions (for values and guards) ──────────────────────────────────────

guard
    : expr comparator expr
    | expr IN range
    ;

expr
    : expr ('+' | '-') term
    | term
    ;

term
    : term ('*' | '/') factor
    | factor
    ;

factor
    : '(' expr ')'
    | atom_expr
    ;

atom_expr
    : 'r(' identifier ')'
    | 'r(' 'api_result' ')'
    | 'len(' 'r(' identifier ')' ')'
    | 'len(' 'r(' 'api_result' ')' ')'
    | 'status(' identifier ')'
    | 'f(' expr ')'
    | literal
    ;

// ── terminals ────────────────────────────────────────────────────────────────

identifier : IDENTIFIER ;
comparator : '=' | '!=' | '<' | '>' | '<=' | '>=' ;
range      : '[' NUMBER ',' NUMBER ']' | 'D' ;
literal    : NUMBER | STRING | 'null' ;
literal_bool : TRUE | FALSE ;

// ── lexer rules ──────────────────────────────────────────────────────────────

NOT   : '¬' | '!' | 'NOT' ;
AND   : '∧' | '&&' | 'AND' ;
OR    : '∨' | '||' | 'OR' ;
XOR   : 'XOR' ;
IN    : 'in' ;
TRUE  : 'true' ;
FALSE : 'false' ;

// IDENTIFIER also accepts a leading '.' so class selectors like
// `.wishlist-heart` parse as a single token. Downstream layers
// (semantic check, dispatcher) treat the leading-dot form as a
// CSS class selector to bind against dynamic per-instance elements.
IDENTIFIER : '.'? [a-zA-Z][a-zA-Z0-9_-]* ;
NUMBER     : [0-9]+ ('.' [0-9]+)? ;
STRING     : '"' (~["\r\n])* '"' ;

WS : [ \t\r\n]+ -> skip ;