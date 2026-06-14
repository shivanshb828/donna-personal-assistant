# dell-hack

Donna is a local-first AI legal secretary for personal injury lawyers.

## M3 Glue Layer

- [M3 implementation plan](docs/m3-glue-layer-plan.md)
- [M2 testing tools](docs/m2-testing-tools.md)

Create the seed context and calendar databases:

```bash
python3 scripts/init_m3_test_db.py
```

Run a sample context lookup:

```bash
python3 scripts/context_lookup.py Maria
```
