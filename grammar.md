constraint       ::= prob_constraint probability_expr
                   | static_constraint

prob_constraint  ::= "P(" event "|" condition ")"

probability_expr ::= ("=" | "<" | ">" | "<=" | ">=") float

event      ::= event_atom (("∧" | "XOR") event_atom)*

event_atom ::= write_event
             | call_event
             | expr "∈" range
             | guard
             | "(" event ")"

write_event ::= "w(" element ")"
              | "w(" element "," expr ")"

call_event  ::= "call(" "api" ")"

condition  ::= condition_atom ("∧" condition_atom)*

condition_atom ::= "A(" element ")"
                 | "¬A(" element ")"
                 | "A(" element ")," guard
                 | "call(" "api" ")"
                 | guard

guard ::= expr comparator expr
        | expr "∈" range

expr ::= atom (("+" | "-") atom)*

atom ::= "r(" element ")"
       | "r(" element ")_last"
       | "r(" "api_result" ")"
       | "len(" "r(" element ")" ")"
       | "len(" "r(" "api_result" ")" ")"
       | "status(" "api" ")"
       | "f(" expr ")"
       | literal

static_constraint ::= "no_literal(" element ")"
                    | "no_hidden_param(" "api" ")"
                    | "hidden_errors()"


comparator ::= "=" | "!=" | "<" | ">" | "<=" | ">="
range      ::= "[" number "," number "]"
             | "D"
element    ::= identifier
identifier ::= [a-zA-Z][a-zA-Z0-9_]*
literal    ::= number | quoted_string | "null"
number     ::= [0-9]+ ("." [0-9]+)?
