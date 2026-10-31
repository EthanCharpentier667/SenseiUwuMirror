# Python cart: intentionally failing version

This small project contains an intentional defect: an empty cart has subtotal 1
instead of 0. It provides a known result for a real SensaiUwu demonstration without
using a private project. Its executable files live in `docs/demo_assets/examples/demos/python-tests/`.

From the repository root:

```bash
.venv/bin/python -m pytest -c docs/demo_assets/examples/demos/python-tests/pytest.ini --no-cov -q docs/demo_assets/examples/demos/python-tests
```

Expected result before correction: **one failure and one pass**, with
`test_empty_basket` failing. This is a demo fixture; the deliberate failure is
not a regression in SensaiUwu's own tests. The [correct version](python-tests-passing.md)
provides the passing counterpart without modifying this fixture.
