kp-gateway-selector

A small library for dynamic payment gateway selection based on configurable rules.

Requirements
- Python >= 3.9, < 4.0
- Optional: Poetry (for dependency management)

Install (development)
- Using Poetry
  - cd my_monorepo/packages/kp_gateway_selector
  - poetry install
- Using pip (editable)
  - cd my_monorepo/packages/kp_gateway_selector
  - pip install -e .

Run tests
- With Poetry (recommended)
  - cd my_monorepo/packages/kp_gateway_selector
  - poetry install
  - poetry run pytest -q
  - Verbose output: poetry run pytest -v
  - Show passed summary: poetry run pytest -q -rP
- If you must avoid installing the package itself
  - poetry install --no-root && poetry run pytest -q

Usage and detailed docs
- See [Gateway Selector README](gateway_selector/README.md) for architecture, matchers, actions, ruleset compiler usage, and examples.

What’s included
- Rule compiler (gateway_selector/compiler/rule_compiler.py) that turns JSON conditions into fast matchers (VALUE_IN, REGEX, AMOUNT_RANGE, TIME_WINDOW, etc.).
- Ruleset compiler (gateway_selector/compiler/ruleset_compiler.py) that loads, validates, and compiles an immutable ruleset snapshot (rules, gateways, defaults).
- Selector (gateway_selector/selector.py) that evaluates compiled rules and resolves actions (FIXED/WEIGHTED/DENY).
- SQLAlchemy models and a DB repo adapter under postgresql/.
- Minimal tests under tests/ covering simple predicate compilation.

Notes
- The logger uses asgi-correlation-id when available; it degrades gracefully if the package is missing.
- SQLAlchemy 2.x emits a deprecation warning for declarative_base(); this is harmless for tests and can be silenced or updated later.
