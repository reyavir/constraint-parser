grammar Constraint;

// ── entry point ──────────────────────────────────────────────────────────────

constraint
    : prob_constraint EOF
    ;

prob_constraint
    : 'P(' logic_expr '|' logic_expr ')' probability_expr
    ;

probability_expr
    : ('=' | '<' | '>' | '<=' | '>=') NUMBER
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
    | guard
    | literal_bool
    ;

write_event
    : 'w(' ui_element ')'
    | 'w(' ui_element ',' expr ')'
    ;

user_action
    : 'A(' ui_element ')'
    ;

system_event
    : 'call(' api ')'
    | 'call(' api ',' expr ')'
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
    : 'r(' ui_element ')'
    | 'r(' 'api_result' ')'
    | 'len(' 'r(' ui_element ')' ')'
    | 'len(' 'r(' 'api_result' ')' ')'
    | 'status(' api ')'
    | 'f(' expr ')'
    | literal
    ;

// ── terminals ────────────────────────────────────────────────────────────────

ui_element : IDENTIFIER ;
api        : IDENTIFIER ;
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

IDENTIFIER : [a-zA-Z][a-zA-Z0-9_]* ;
NUMBER     : [0-9]+ ('.' [0-9]+)? ;
STRING     : '"' (~["\r\n])* '"' ;

WS : [ \t\r\n]+ -> skip ;