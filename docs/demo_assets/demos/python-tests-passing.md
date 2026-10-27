# Python cart: correct version

This version of the cart module returns zero for an empty cart. It complements
the [intentionally faulty version](python-tests.md) without modifying that fixture.
Its executable files live in `docs/demo_assets/examples/demos/python-tests-passing/`.

From the repository root:

```bash
.venv/bin/python -m pytest -c docs/demo_assets/examples/demos/python-tests-passing/pytest.ini --no-cov -q docs/demo_assets/examples/demos/python-tests-passing
```

Expected result: **2 passed**, exit code **0**. The same two checks cover a
non-empty cart and an empty cart. Run the two versions separately so their modules
and configurations remain independent.

The original pytest GIF shows the faulty version. This fixture supplies the passing
case; its existence alone does not constitute a new Sensai recording.
