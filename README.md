# tesseract-finance
Expense tracking API with receipt OCR (FastAPI, PostgreSQL, Tesseract). Backend learning project.

## Development

See [docs/spec.md](docs/spec.md) section 12. Tests need the Compose Postgres on `localhost:5434`:

```bash
uv sync
uv run pytest                       # uses DATABASE_URL, default .../tesseract_finance_test
uv run ruff check . && uv run ruff format --check .
```

The suite creates its databases if missing. The test database is the name in `DATABASE_URL`.
The migration roundtrip uses that name with `_test` replaced by `_migrate`, so a downgrade to
base never runs against the test schema.
