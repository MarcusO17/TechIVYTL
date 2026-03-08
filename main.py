from typing import Any, Dict, List, Tuple
def validate_tool_call(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Returns (clean, errors). 'clean' strictly follows the schema with defaults applied.
    - Trim strings; coerce numeric strings to ints.
    - Remove unknown keys.
    - If action=='answer', ignore 'q' if present (no error).
    - On fatal errors (e.g., missing/invalid 'action', or missing/empty 'q' for search), return ({}, errors).
    """
    errors = []
    clean = {}

    ## Action Validation
    raw_action = payload.get("action")          # avoid KeyError on direct access
    if raw_action is None:
        return {}, ["Missing required field: 'action'"]
    if not isinstance(raw_action, str):
        return {}, [f"'action' must be a string, got {type(raw_action).__name__}"]
    action = raw_action.strip().lower()         # normalize before membership check
    if action not in ("search", "answer"):
        return {}, [f"'action' must be 'search' or 'answer', got {raw_action!r}"]

    clean["action"] = action

    ## K Validation
    raw_k = payload.get("k")                   # None if absent, k is fully optional
    if raw_k is None:
        pass                                    # omit k from clean entirely
    else:
        if isinstance(raw_k, bool):            # bool subclasses int IMPORTANT
            errors.append(f"'k' must be an integer, got bool ({raw_k!r}); using default 3")
            coerced_k = 3
        elif isinstance(raw_k, int):
            coerced_k = raw_k
        elif isinstance(raw_k, str):
            stripped = raw_k.strip()
            try:
                coerced_k = int(stripped)
            except ValueError:                 # e.g. "few", "3 results"
                errors.append(f"'k' could not be coerced to int ({raw_k!r}); using default 3")
                coerced_k = 3
        elif isinstance(raw_k, float):
            if raw_k.is_integer():             # e.g. 3.0 = 3
                coerced_k = int(raw_k)
            else:                              # e.g. 3.9 = reject
                errors.append(f"'k' is a non-integer float ({raw_k!r}); using default 3")
                coerced_k = 3
        else:                                  # list, dict, etc.
            errors.append(f"'k' has unexpected type {type(raw_k).__name__!r}; using default 3")
            coerced_k = 3

        if not (1 <= coerced_k <= 5):          # pull to nearest boundary
            errors.append(f"'k' must be in [1, 5], got {coerced_k}; clamping to range")
            coerced_k = max(1, min(5, coerced_k))

        clean["k"] = coerced_k

    ## Q Validation
    if action == "search":
        raw_q = payload.get("q")
        if raw_q is None:
            return {}, ["'q' is required when action is 'search'"]
        if not isinstance(raw_q, str):
            return {}, [f"'q' must be a string, got {type(raw_q).__name__}"]
        q = raw_q.strip()
        if not q:                              # catches "   " after strip
            return {}, ["'q' must be a non-empty string"]

        clean["q"] = q                         # q will be ignored if action == "answer" silently

    return (clean, errors)



if __name__ == "__main__":
    cases = [
        # ── happy path ──────────────────────────────────────────────────────
        ("happy path search",               {"action": "search", "q": "hello", "k": 2},
                                            {"action": "search", "q": "hello", "k": 2}, []),
        ("happy path answer",               {"action": "answer", "k": 3},
                                            {"action": "answer", "k": 3}, []),
        ("answer ignores q",                {"action": "answer", "q": "ignored"},
                                            {"action": "answer"}, []),
        ("k absent — omitted from clean",   {"action": "answer"},
                                            {"action": "answer"}, []),

        # ── action weirdness ────────────────────────────────────────────────
        ("uppercase action",                {"action": "SEARCH", "q": "hi"},
                                            {"action": "search", "q": "hi"}, []),
        ("padded whitespace action",        {"action": "  answer  "},
                                            {"action": "answer"}, []),
        ("newline-padded action",           {"action": "search\n", "q": "hi"},
                                            {"action": "search", "q": "hi"}, []),
        ("punctuation in action",           {"action": "Search!"},
                                            {}, ["'action' must be 'search' or 'answer', got 'Search!'"]),
        ("empty action string",             {"action": ""},
                                            {}, ["'action' must be 'search' or 'answer', got ''"]),
        ("explicit None action",            {"action": None},
                                            {}, ["Missing required field: 'action'"]),
        ("list as action",                  {"action": ["search"]},
                                            {}, ["'action' must be a string, got list"]),
        ("dict as action",                  {"action": {"type": "search"}},
                                            {}, ["'action' must be a string, got dict"]),
        ("bool as action",                  {"action": True},
                                            {}, ["'action' must be a string, got bool"]),

        # ── k weirdness ─────────────────────────────────────────────────────
        ("k as numeric string",             {"action": "search", "q": "hi", "k": "3"},
                                            {"action": "search", "q": "hi", "k": 3}, []),
        ("k as padded numeric string",      {"action": "search", "q": "hi", "k": "  2 "},
                                            {"action": "search", "q": "hi", "k": 2}, []),
        ("k as whole float",                {"action": "search", "q": "hi", "k": 3.0},
                                            {"action": "search", "q": "hi", "k": 3}, []),
        ("k as explicit None — omitted",    {"action": "search", "q": "hi", "k": None},
                                            {"action": "search", "q": "hi"}, []),
        ("k below range — clamp to 1",      {"action": "search", "q": "hi", "k": 0},
                                            {"action": "search", "q": "hi", "k": 1},
                                            ["'k' must be in [1, 5], got 0; clamping to range"]),
        ("k above range — clamp to 5",      {"action": "search", "q": "hi", "k": 6},
                                            {"action": "search", "q": "hi", "k": 5},
                                            ["'k' must be in [1, 5], got 6; clamping to range"]),
        ("k way below range",               {"action": "search", "q": "hi", "k": -99},
                                            {"action": "search", "q": "hi", "k": 1},
                                            ["'k' must be in [1, 5], got -99; clamping to range"]),
        ("k as False — bool trap",          {"action": "search", "q": "hi", "k": False},
                                            {"action": "search", "q": "hi", "k": 3},
                                            ["'k' must be an integer, got bool (False); using default 3"]),
        ("k as True — bool trap",           {"action": "search", "q": "hi", "k": True},
                                            {"action": "search", "q": "hi", "k": 3},
                                            ["'k' must be an integer, got bool (True); using default 3"]),
        ("k as fractional float",           {"action": "search", "q": "hi", "k": 3.9},
                                            {"action": "search", "q": "hi", "k": 3},
                                            ["'k' is a non-integer float (3.9); using default 3"]),
        ("k as garbage string",             {"action": "search", "q": "hi", "k": "abc"},
                                            {"action": "search", "q": "hi", "k": 3},
                                            ["'k' could not be coerced to int ('abc'); using default 3"]),
        ("k as empty list",                 {"action": "search", "q": "hi", "k": []},
                                            {"action": "search", "q": "hi", "k": 3},
                                            ["'k' has unexpected type 'list'; using default 3"]),

        # ── q weirdness ─────────────────────────────────────────────────────
        ("q padded — stripped",             {"action": "search", "q": "  hello  "},
                                            {"action": "search", "q": "hello"}, []),
        ("q only whitespace",               {"action": "search", "q": "   "},
                                            {}, ["'q' must be a non-empty string"]),
        ("q empty string",                  {"action": "search", "q": ""},
                                            {}, ["'q' must be a non-empty string"]),
        ("q explicit None",                 {"action": "search", "q": None},
                                            {}, ["'q' is required when action is 'search'"]),
        ("q as int",                        {"action": "search", "q": 42},
                                            {}, ["'q' must be a string, got int"]),
        ("q as list",                       {"action": "search", "q": ["hello"]},
                                            {}, ["'q' must be a string, got list"]),

        # ── unknown keys ────────────────────────────────────────────────────
        ("unknown key confidence",          {"action": "answer", "confidence": 0.95},
                                            {"action": "answer"}, []),
        ("unknown key reasoning",           {"action": "search", "q": "hi", "reasoning": "because"},
                                            {"action": "search", "q": "hi"}, []),
        ("duplicate-ish key k2",            {"action": "search", "q": "hi", "k": 2, "k2": 5},
                                            {"action": "search", "q": "hi", "k": 2}, []),

        # ── missing fields ───────────────────────────────────────────────────
        ("empty payload",                   {},
                                            {}, ["Missing required field: 'action'"]),
        ("missing action",                  {"q": "hello", "k": 2},
                                            {}, ["Missing required field: 'action'"]),
        ("missing q for search",            {"action": "search"},
                                            {}, ["'q' is required when action is 'search'"]),

        # ── llm being helpful ────────────────────────────────────────────────
        ("query instead of q",              {"action": "search", "query": "hello"},
                                            {}, ["'q' is required when action is 'search'"]),
        ("natural language k",              {"action": "search", "q": "hello", "k": "few"},
                                            {"action": "search", "q": "hello", "k": 3},
                                            ["'k' could not be coerced to int ('few'); using default 3"]),
        ("k with units",                    {"action": "search", "q": "hello", "k": "3 results"},
                                            {"action": "search", "q": "hello", "k": 3},
                                            ["'k' could not be coerced to int ('3 results'); using default 3"]),
        ("type instead of action",          {"type": "search", "q": "hello"},
                                            {}, ["Missing required field: 'action'"]),
    ]

    passed = 0
    failed = 0

    for desc, payload, expected_clean, expected_errors in cases:
        clean, errors = validate_tool_call(payload)
        ok = clean == expected_clean and errors == expected_errors
        status = "✓" if ok else "✗"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"{status} [{desc}]")
            print(f"  payload        : {payload}")
            if clean != expected_clean:
                print(f"  expected clean : {expected_clean}")
                print(f"  got clean      : {clean}")
            if errors != expected_errors:
                print(f"  expected errors: {expected_errors}")
                print(f"  got errors     : {errors}")
            print()

    print(f"{'─'*40}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(cases)} total")
    print(f"{'─'*40}")