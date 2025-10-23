# kp-gateway-selector – Library

Pequeña librería para selección dinámica de gateways de pago basada on reglas configurables (rule/ ruleset compilers + selector).

---

## 📦 Requirements

- Python >= 3.9, < 4.0
- Optional: Poetry (dependency management)

---

## 🚀 Install (development)

### Using Poetry
```
cd my_monorepo/packages/kp_gateway_selector
poetry install
```

### Using pip (editable)
```
cd my_monorepo/packages/kp_gateway_selector
pip install -e .
```

---

## ✅ Run tests

### With Poetry (recommended)
```
cd my_monorepo/packages/kp_gateway_selector
poetry install
poetry run pytest -q
```
- Verbose output:
```
poetry run pytest -v
```
- Show passed summary:
```
poetry run pytest -q -rP
```

### If you must avoid installing the package itself
```
poetry install --no-root && poetry run pytest -q
```

---

## 📚 Usage and detailed docs
- See [Gateway Selector README](gateway_selector/README.md) for architecture, matchers, actions, ruleset compiler usage, and examples.

---

## 🧩 What’s included
- Rule compiler: gateway_selector/compiler/rule_compiler.py — compiles JSON conditions into fast matchers (VALUE_IN, REGEX, AMOUNT_RANGE, TIME_WINDOW, etc.).
- Ruleset compiler: gateway_selector/compiler/ruleset_compiler.py — loads, validates and compiles an immutable ruleset snapshot (rules, gateways, defaults).
- Selector: gateway_selector/selector.py — evaluates compiled rules and resolves actions (FIXED/WEIGHTED/DENY).
- SQLAlchemy models and DB repo under postgresql/.
- Minimal tests under tests/ for predicate compilation.

---

## 📝 Notes
- Logger uses asgi-correlation-id when available; degrades gracefully otherwise.
- SQLAlchemy 2.x may warn about declarative_base(); harmless for tests and can be updated later.
