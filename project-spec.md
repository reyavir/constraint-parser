constraint     ::= prob_constraint "=" probability_expr

prob_constraint ::= "P(" event "|" condition ")"

probability_expr ::= ("=" | "<" | ">" | "<=" | ">=") probability
probability      ::= float                          -- 0.0 to 1.0

event ::= write_event                               -- single write
        | call_event                                -- API call fired
        | write_event "∧" write_event              -- both must update
        | write_event "XOR" write_event            -- exactly one updates

write_event  ::= "w(" element ")"
               | "w(" element "," value_expr ")"

call_event   ::= "call(" "api" ")"
               | "call(" "api" "," value_expr ")"

condition    ::= "A(" element ")"                  -- action taken
               | "¬A(" element ")"                 -- action NOT taken
               | "A(" element ")," guard           -- action + input condition
               | guard                             -- standalone condition 

guard        ::= expr comparator expr
               | expr "∈" range

expr         ::= "r(" element ")"                  -- read UI element value
               | "len(" "r(" element ")" ")"       -- length of UI element
               | "len(" "r(" "api_result" ")" ")"  -- length of API response
               | "status(" "api" ")"               -- HTTP status code
               | "r(" element ")" "+" number       -- increment
               | "r(" element ")" "-" number       -- decrement
               | literal                           -- constant


comparator   ::= "=" | "!=" | "<" | ">" | "<=" | ">="

value_expr   ::= "r(" element ")"                  -- copy from input
               | "f(" "r(" element ")" ")"         -- opaque function of input
               | "r(" element ")" "+" number       -- increment
               | "r(" element ")" "-" number       -- decrement
               | "r(" element ")" "_last"          -- latest value in sequence
               | literal                           -- constant k

range        ::= "[" number "," number "]"         -- inclusive range
               | "D"                               -- user-defined distribution

element      ::= identifier                        -- must match a DOM ID in the app
identifier   ::= [a-zA-Z][a-zA-Z0-9_]*
literal      ::= number | quoted_string | "null"
number       ::= [0-9]+ ("." [0-9]+)?
