# tesseract-finance
Expense tracking API with receipt OCR (FastAPI, PostgreSQL, Tesseract) — backend learning project

## Development

See [docs/spec.md](docs/spec.md) section 12. Tests need the Compose Postgres on `localhost:5434`:

```bash
uv sync
uv run pytest                       # uses DATABASE_URL, default .../tesseract_finance_test
uv run ruff check . && uv run ruff format --check .
```

The suite creates its databases if missing: the test database named in `DATABASE_URL`, and a
`_migrate` twin (`tesseract_finance_test` -> `tesseract_finance_migrate`) for the migration
roundtrip, which downgrades to base and so never runs against the test schema.
