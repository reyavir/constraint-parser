# ── Base case: write event, simple action ─────────────────────────────────
# P(w(cartDisplay) | A(addBtn)) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "WriteEvent",
        "element": "cartDisplay",   # required — must exist in mapping
        "value_expr": None          # optional — None means just check it was written
    },
    "condition": {
        "type": "Action",
        "element": "addBtn",        # required — must exist in mapping as kind=action
        "negated": False,           # required — defaults False, never None
        "guard": None               # optional — None means no input condition
    },
    "probability": 1.0,             # required — float in [0.0, 1.0]
    "prob_operator": "="            # required — one of = < > <= >=
}

# ── Value constraint ──────────────────────────────────────────────────────
# P(w(cartDisplay, r(addBtn) + 1) | A(addBtn)) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "WriteEvent",
        "element": "cartDisplay",
        "value_expr": {
            "type": "IncrementExpr",
            "element": "addBtn",    # the element being read
            "delta": 1              # the constant being added
        }
    },
    "condition": {
        "type": "Action",
        "element": "addBtn",
        "negated": False,
        "guard": None
    },
    "probability": 1.0,
    "prob_operator": "="
}

# ── Counterfactual: negated action ────────────────────────────────────────
# P(w(cartDisplay) | ¬A(addBtn)) = 0
{
    "type": "Probabilistic",
    "event": {
        "type": "WriteEvent",
        "element": "cartDisplay",
        "value_expr": None
    },
    "condition": {
        "type": "Action",
        "element": "addBtn",
        "negated": True,            # ← this is what makes it counterfactual
        "guard": None
    },
    "probability": 0.0,
    "prob_operator": "="
}

# ── Guard on condition ────────────────────────────────────────────────────
# P(w(submitBtn) | A(submitBtn), r(cartDisplay) > 0) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "WriteEvent",
        "element": "submitBtn",
        "value_expr": None
    },
    "condition": {
        "type": "Action",
        "element": "submitBtn",
        "negated": False,
        "guard": {                  # ← optional, only present when user added condition
            "type": "Guard",
            "left":  {"type": "ReadExpr",    "element": "cartDisplay"},
            "op":    ">",
            "right": {"type": "LiteralExpr", "value": 0}
        }
    },
    "probability": 1.0,
    "prob_operator": "="
}

# ── Compound event: two components must both update ───────────────────────
# P(w(cartDisplay) AND w(cartTotal) | A(addBtn)) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "CompoundEvent",    # ← when AND/OR/XOR appears on left side
        "op": "AND",
        "left":  {"type": "WriteEvent", "element": "cartDisplay", "value_expr": None},
        "right": {"type": "WriteEvent", "element": "cartTotal",   "value_expr": None}
    },
    "condition": {
        "type": "Action",
        "element": "addBtn",
        "negated": False,
        "guard": None
    },
    "probability": 1.0,
    "prob_operator": "="
}

# ── API call event ────────────────────────────────────────────────────────
# P(call(api) | A(submitBtn)) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "CallEvent",
        "api": "/api/cart",         # required — endpoint string
        "params": None              # optional — None means just check call was made
    },
    "condition": {
        "type": "Action",
        "element": "submitBtn",
        "negated": False,
        "guard": None
    },
    "probability": 1.0,
    "prob_operator": "="
}


# ── value_expr variants (all valid on WriteEvent) ─────────────────────────

# ReadExpr — copy from element: w(resultsList, r(searchInput))
"value_expr": {"type": "ReadExpr", "element": "searchInput"}

# LiteralExpr — constant: w(cartDisplay, 0)
"value_expr": {"type": "LiteralExpr", "value": 0}

# LiteralExpr — null: w(statusDisplay, null)
"value_expr": {"type": "LiteralExpr", "value": "null"}  # string "null", not None

# FuncExpr — function of input: w(cartDisplay, f(r(searchInput)))
"value_expr": {"type": "FuncExpr", "arg": {"type": "ReadExpr", "element": "searchInput"}}

# LenExpr — length of API result: w(resultsList, len(r(api_result)))
"value_expr": {"type": "LenExpr", "element": "api_result"}


# ── Guard as event (left side read + comparison) ──────────────────────────
# P(r(cartDisplay) = 0 | A(clearBtn)) = 1
{
    "type": "Probabilistic",
    "event": {
        "type": "Guard",
        "left":  {"type": "ReadExpr",    "element": "cartDisplay"},
        "op":    "=",
        "right": {"type": "LiteralExpr", "value": 0}
    },
    "condition": {
        "type": "Action",
        "element": "clearBtn",
        "negated": False,
        "guard": None
    },
    "probability": 1.0,
    "prob_operator": "="
}