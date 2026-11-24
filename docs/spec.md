# TesseractFinance: Spec v1

Status: draft for review
Owner: Krzysztof Oszczapiński (LUNARITY)

## 1. Purpose

TesseractFinance is a personal expense-tracking REST API. Users record expenses by hand or upload a photo of a receipt. A background worker runs Tesseract OCR on the photo and proposes an expense, which the user confirms.

It is also a backend learning project. Each milestone exercises one backend topic: async FastAPI, SQLAlchemy 2.0, Alembic migrations, background jobs, auth, CI, and later cloud storage and MCP.

## 2. Goals

- CRUD for expenses, scoped per user.
- Per-user categories (plus global defaults) and tags, with filtering and pagination.
- Receipt upload, background OCR, and a confirm step that turns a receipt into an expense.
- JWT auth.
- Reproducible local dev with Docker Compose and CI on GitHub Actions.
- Test-first development with pytest against a real Postgres.

## 3. Non-goals (v1)

- No frontend. Use the OpenAPI docs (`/docs`), curl, or HTTPie.
- No multi-currency conversion. `currency` is stored as given and totals are never summed across currencies.
- No budgets, reports, recurring expenses, or bank imports.
- No line-item or vendor extraction in v1 (see section 8.4).
- No cloud storage in v1. Receipts go to a local volume.
- No OAuth, password reset, email verification, or refresh tokens.
- No horizontal scaling concerns beyond "one API + one worker".

## 4. Architecture

```
            +-----------+        +----------------+
client ---> |   api     | -----> |   postgres     |
 (HTTP)     |  FastAPI  |        | app tables +   |
            +-----------+        | job queue      |
                 |               +----------------+
                 | writes file          ^
                 v                      |
          [receipts volume] <----- +-----------+
                                   |  worker   |
                                   | Tesseract |
                                   +-----------+
```

Docker Compose services:

| Service    | Image / build              | Role                                           |
|------------|----------------------------|------------------------------------------------|
| `db`       | `postgres:16`              | Application data and the job queue            |
| `api`      | `Dockerfile` (target `api`)    | FastAPI app served by uvicorn               |
| `worker`   | `Dockerfile` (target `worker`) | Procrastinate worker running OCR jobs; has `tesseract-ocr` + `tesseract-ocr-pol` installed |

`api` and `worker` share one Python package and one image base. Only the worker image needs Tesseract. Both mount the `receipts` volume.

## 5. Tech stack

- Python 3.12 (3.11+ supported), dependency management with `uv` (`pyproject.toml` + `uv.lock`).
- FastAPI (async), Pydantic v2, `pydantic-settings` for config.
- PostgreSQL 16, SQLAlchemy 2.0 (async, `asyncpg` driver), Alembic.
- Job queue: `procrastinate` (Postgres-backed), see section 8.2.
- OCR: Tesseract via `pytesseract`, image preprocessing with Pillow.
- Auth: JWT (`pyjwt`), password hashing with `argon2-cffi` (or `pwdlib`).
- Tooling: Ruff (lint + format), pytest, `pytest-asyncio`, `httpx` `AsyncClient`.
- CI: GitHub Actions.

## 6. Data model

Conventions:

- Primary keys are UUIDs (`uuid4`, generated in the app) unless noted.
- `created_at` / `updated_at` are `timestamptz`, set by the database (`now()`), `updated_at` refreshed on update.
- Money is `NUMERIC(12,2)` in the database, `Decimal` in Python, and a string in JSON (`"25.00"`), so no float rounding.
- `currency` is an ISO 4217 code, `CHAR(3)`, uppercase, default `PLN`.
- Every user-owned row has `user_id`, and every query filters by it.

### 6.1 users

| Column          | Type          | Notes                     |
|-----------------|---------------|---------------------------|
| id              | uuid PK       |                           |
| email           | varchar(320)  | unique, stored lowercase  |
| password_hash   | varchar       | nullable until M4         |
| created_at      | timestamptz   |                           |
| updated_at      | timestamptz   |                           |

### 6.2 categories

| Column     | Type         | Notes                                   |
|------------|--------------|-----------------------------------------|
| id         | uuid PK      |                                         |
| user_id    | uuid FK null | `NULL` = global category (seeded)       |
| name       | varchar(100) |                                         |
| created_at | timestamptz  |                                         |
| updated_at | timestamptz  |                                         |

- Unique `(user_id, name)` for user categories, and a partial unique index on `name WHERE user_id IS NULL` for globals.
- `is_global` from the draft is dropped. It is derived from `user_id IS NULL`, so storing it would allow contradictions.
- Global categories are seeded by a migration (e.g. Groceries, Transport, Housing, Health, Entertainment, Music gear, Other) and are read-only through the API.

### 6.3 tags

| Column     | Type        | Notes                       |
|------------|-------------|-----------------------------|
| id         | uuid PK     |                             |
| user_id    | uuid FK     | not null                    |
| name       | varchar(50) | unique per `(user_id, name)`|
| created_at | timestamptz |                             |

### 6.4 expenses

| Column      | Type          | Notes                                        |
|-------------|---------------|----------------------------------------------|
| id          | uuid PK       |                                              |
| user_id     | uuid FK       | not null                                     |
| category_id | uuid FK null  | must be global or owned by the same user    |
| amount      | numeric(12,2) | not null, `> 0`                              |
| currency    | char(3)       | not null, default `PLN`                      |
| date        | date          | not null; calendar date of the purchase, no timezone |
| description | varchar(500)  | nullable                                     |
| source_url  | text          | nullable (e.g. link to an online order)      |
| is_planned  | boolean       | not null, default `false`                    |
| created_at  | timestamptz   |                                              |
| updated_at  | timestamptz   |                                              |

- Index on `(user_id, date DESC)`.
- `receipt_image_url` and `ocr_metadata` from the draft move to `receipts`. An expense links back via `receipts.expense_id`.

### 6.5 expense_tags

| Column     | Type    | Notes                                  |
|------------|---------|----------------------------------------|
| expense_id | uuid FK | `ON DELETE CASCADE`                    |
| tag_id     | uuid FK | `ON DELETE CASCADE`                    |

Primary key `(expense_id, tag_id)`. A tag attached to an expense must belong to the same user.

### 6.6 receipts

| Column        | Type         | Notes                                                   |
|---------------|--------------|---------------------------------------------------------|
| id            | uuid PK      |                                                         |
| user_id       | uuid FK      | not null                                                |
| file_path     | text         | storage key, relative to the storage root               |
| content_type  | varchar(50)  | `image/png` or `image/jpeg`                             |
| status        | varchar(20)  | `pending` → `processing` → `done` \| `failed`; `confirmed` after confirm |
| raw_text      | text         | nullable, Tesseract output                              |
| ocr_metadata  | jsonb        | nullable, see section 8.3                               |
| error         | text         | nullable, last failure reason                           |
| expense_id    | uuid FK null | set on confirm, `ON DELETE SET NULL`                    |
| created_at    | timestamptz  |                                                         |
| updated_at    | timestamptz  |                                                         |

`status` is a Postgres enum or a `CHECK` constraint.

## 7. REST API

Base path: `/api/v1`. JSON in and out. OpenAPI at `/docs`.

### 7.1 Common rules

- **Auth:** every endpoint except `/auth/*` and `/health` requires a user. Before M4 the user comes from a `get_current_user` dependency that returns a fixed dev user. M4 swaps its implementation for JWT `Authorization: Bearer <token>` without changing the routes.
- **Ownership:** a resource that belongs to another user returns `404` (not `403`), so the API does not reveal that it exists. Global categories are readable by everyone but return `403` on write.
- **Status codes:** `200` OK, `201` Created, `202` Accepted, `204` No Content, `400` bad request (e.g. invalid file), `401` missing or invalid token, `403` forbidden, `404` not found, `409` conflict (duplicate name, receipt already confirmed), `413` file too large, `415` unsupported media type, `422` validation error.
- **Errors** use one shape:
  ```json
  { "detail": "Expense not found", "code": "not_found" }
  ```
  `422` keeps FastAPI's default `detail` list.
- **Pagination:** `limit` (default 20, max 100) and `offset` (default 0). List responses:
  ```json
  { "items": [ ... ], "total": 57, "limit": 20, "offset": 0 }
  ```
- **Updates** use `PATCH` with partial bodies. Only fields present in the body change.

### 7.2 Health

- `GET /health` → `200 {"status": "ok", "db": "ok"}`.

### 7.3 Expenses

Expense object:

```json
{
  "id": "6f1c...",
  "amount": "25.00",
  "currency": "PLN",
  "date": "2026-11-23",
  "category_id": "a2b3...",
  "description": "Plectrums",
  "source_url": null,
  "is_planned": false,
  "tags": [{ "id": "9e8d...", "name": "music" }],
  "receipt_id": null,
  "created_at": "2026-11-23T18:30:00Z",
  "updated_at": "2026-11-23T18:30:00Z"
}
```

- `POST /api/v1/expenses` → `201` expense.
  Body: `amount` (string or number, `> 0`, max 2 decimals), `currency` (optional, default `PLN`), `date` (required), `category_id`, `description`, `source_url`, `is_planned`, `tag_ids` (all optional).
  Unknown or foreign `category_id` / `tag_ids` → `422`.
- `GET /api/v1/expenses` → `200` paginated list, newest `date` first.
  Filters: `category_id`, `tag_id`, `is_planned`, `start_date`, `end_date` (inclusive), `currency`.
- `GET /api/v1/expenses/{id}` → `200` or `404`.
- `PATCH /api/v1/expenses/{id}` → `200` or `404`. `tag_ids`, when present, replaces the whole tag set.
- `DELETE /api/v1/expenses/{id}` → `204` or `404`.

### 7.4 Categories

- `GET /api/v1/categories` → global plus the user's own, each with `"is_global": true|false` (computed).
- `POST /api/v1/categories` → `201`, `409` on duplicate name for this user.
- `PATCH /api/v1/categories/{id}` → `200`, `403` for global, `404` for missing or foreign.
- `DELETE /api/v1/categories/{id}` → `204`. Expenses keep existing with `category_id = NULL`.

### 7.5 Tags

- `GET /api/v1/tags`, `POST /api/v1/tags` (`409` on duplicate), `PATCH /api/v1/tags/{id}`, `DELETE /api/v1/tags/{id}` (removes it from expenses).

### 7.6 Receipts

- `POST /api/v1/receipts` (multipart, field `file`) → `202`
  ```json
  { "id": "c0ff...", "status": "pending" }
  ```
  Accepts `image/png` and `image/jpeg` only, checked by content sniffing (Pillow), not only by the header (`415` otherwise). Max size 10 MB (`413`). Stores the file, creates the receipt row, and enqueues the OCR job in the same transaction.
  (The draft's `POST /expenses/upload-receipt` is renamed, because the upload creates a receipt, not an expense.)
- `GET /api/v1/receipts/{id}` → `200` receipt object, used for polling:
  ```json
  {
    "id": "c0ff...",
    "status": "done",
    "raw_text": "THOMANN ... SUMA PLN 25,00 ...",
    "ocr_metadata": { ... },
    "error": null,
    "expense_id": null,
    "created_at": "...",
    "updated_at": "..."
  }
  ```
- `GET /api/v1/receipts` → paginated list, filter `status`.
- `POST /api/v1/receipts/{id}/confirm` → `201` expense.
  Body is an expense create payload. Every field is optional; missing `amount`, `date`, and `currency` are taken from `ocr_metadata`. If `amount` or `date` is still unknown → `422`. Receipt must be `done` (`409` otherwise, including already `confirmed`). Creates the expense, sets `receipts.expense_id` and `status = confirmed` in one transaction.
- `DELETE /api/v1/receipts/{id}` → `204`, deletes the file and row. Does not delete a linked expense.

### 7.7 Auth (M4)

- `POST /auth/register` `{ "email", "password" }` → `201 { "id", "email" }`, `409` if email exists. Password min 8 chars.
- `POST /auth/login` `{ "email", "password" }` → `200 { "access_token", "token_type": "bearer", "expires_in": 3600 }`, `401` on bad credentials (same message for unknown email and wrong password).
- `GET /api/v1/me` → current user.
- Access token: HS256, `sub` = user id, `exp` = 60 min. Secret from `JWT_SECRET` env var. No refresh tokens in v1.

## 8. Receipt processing

### 8.1 Flow

1. `api` validates and saves the file, inserts `receipts` (`pending`), and defers job `process_receipt(receipt_id)`.
2. `worker` picks the job, sets `processing`, loads the image, preprocesses it (grayscale, upscale small images, autocontrast), and runs Tesseract with `lang="pol+eng"`.
3. The worker stores `raw_text`, runs the extractor (8.3), stores `ocr_metadata`, sets `done`.
4. On error: retry up to 3 times with backoff. After the last failure, `status = failed` and `error` set.
5. The client polls `GET /receipts/{id}` until `done` or `failed`, shows the proposal, and calls `/confirm`.

### 8.2 Queue choice: procrastinate

We use [`procrastinate`](https://procrastinate.readthedocs.io/), a Postgres-backed task queue.

- **No extra infrastructure.** Jobs live in the same Postgres. No Redis or RabbitMQ in Compose.
- **Transactional enqueue.** The receipt row and its job are written in one transaction, so there is never a job without a receipt or a receipt without a job.
- **Async-native,** fits FastAPI and asyncpg, and gives retries, a CLI and a job table to inspect for free.
- Internally it uses `SELECT ... FOR UPDATE SKIP LOCKED` plus `LISTEN/NOTIFY`, so the learning value of the hand-rolled option is still visible by reading its schema.

A hand-rolled jobs table was considered. It teaches the locking pattern directly, but means writing retries, backoff, stale-job recovery and a worker loop ourselves, which is a project of its own. It can be a later optional exercise.

Procrastinate's schema is applied through Alembic (a migration that runs its schema SQL), so `alembic upgrade head` is the single way to build the database.

### 8.3 `ocr_metadata` (v1)

Tesseract returns text and per-word confidences only. v1 extracts total and date with regex heuristics and does not attempt vendor or line items.

```json
{
  "engine": "tesseract",
  "engine_version": "5.3.4",
  "languages": "pol+eng",
  "mean_word_confidence": 87.4,
  "extracted": {
    "total_amount": "25.00",
    "currency": "PLN",
    "purchase_date": "2026-11-23"
  },
  "extractor_version": 1
}
```

- `mean_word_confidence` is the mean of Tesseract's word confidences (0–100) from `image_to_data`, ignoring `-1` entries. It is OCR quality, not confidence that the extracted fields are right.
- Any `extracted` field may be `null`.
- Total heuristics: lines matching keywords such as `SUMA`, `RAZEM`, `TOTAL`, `DO ZAPŁATY` followed by an amount; amounts accept `25,00` and `25.00`; if several matches, take the last one; fallback is the largest amount on the receipt.
- Date heuristics: `DD-MM-YYYY`, `DD.MM.YYYY`, `YYYY-MM-DD`, ignoring dates in the future.
- Currency: `PLN`/`zł` → `PLN`, `EUR`/`€` → `EUR`, `USD`/`$` → `USD`, else `null`.
- The extractor is a pure function `extract(raw_text) -> Extracted`, unit-tested with fixture texts, no Tesseract needed.

### 8.4 Later (optional, not v1)

- An LLM step that turns `raw_text` into `vendor_name` and `line_items`, stored under `ocr_metadata.llm` with the model name.
- Better preprocessing (deskew, thresholding with OpenCV).

## 9. File storage

- A `Storage` protocol with `save(key, bytes)`, `open(key)`, `delete(key)`.
- v1: `LocalStorage` writing to `STORAGE_DIR` (`/data/receipts`), a Docker volume shared by `api` and `worker`. Keys are `{user_id}/{receipt_id}.{ext}`; the original filename is never used in the path.
- Later, as a cloud learning exercise: `S3Storage` (AWS) and `AzureBlobStorage` (Azure), chosen by `STORAGE_BACKEND`. Credentials come from env vars, never from the repo.

## 10. Configuration

All settings come from environment variables via `pydantic-settings`. `.env.example` is committed; `.env` is git-ignored.

| Variable          | Example                                                   |
|-------------------|-----------------------------------------------------------|
| `DATABASE_URL`    | `postgresql+asyncpg://tf:tf@db:5432/tesseract_finance`    |
| `STORAGE_BACKEND` | `local`                                                   |
| `STORAGE_DIR`     | `/data/receipts`                                          |
| `MAX_UPLOAD_MB`   | `10`                                                      |
| `JWT_SECRET`      | (generated locally, never committed)                     |
| `JWT_TTL_MINUTES` | `60`                                                      |
| `DEV_USER_EMAIL`  | `dev@example.com` (pre-M4 fixed user)                     |

## 11. Project layout

```
tesseract-finance/
  pyproject.toml, uv.lock, .python-version
  Dockerfile, compose.yaml, .env.example
  alembic.ini, migrations/
  src/tesseract_finance/
    main.py            # app factory
    config.py
    db.py              # engine, session dependency
    deps.py            # get_current_user, pagination
    models/            # SQLAlchemy models
    schemas/           # Pydantic models
    api/               # routers: expenses, categories, tags, receipts, auth
    services/          # business logic, ownership checks
    ocr/               # tesseract wrapper, extractor
    storage/           # Storage protocol + LocalStorage
    worker.py          # procrastinate app + tasks
  tests/
    unit/
    integration/
    fixtures/receipts/
  docs/spec.md
```

## 12. Local development

```bash
cp .env.example .env
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run fastapi dev src/tesseract_finance/main.py   # or: docker compose up api worker
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

- `docker compose up` starts `db`, `api` (port 8000) and `worker`. `api` runs `alembic upgrade head` on start in dev.
- The worker can also run on the host with `uv run procrastinate --app=tesseract_finance.worker.app worker` if Tesseract is installed locally (`brew install tesseract tesseract-lang`).

## 13. Testing strategy

- **Test-first:** each ticket starts with a failing test that describes the behaviour, then the code.
- **Real Postgres, no SQLite and no DB mocks.** Tests use a dedicated `tesseract_finance_test` database on the Compose `db` service locally and a Postgres service container in CI. (Testcontainers is an alternative, but Compose keeps local and CI the same and avoids Docker-in-test.)
- The test session runs `alembic upgrade head` once, so migrations are tested on every run. Each test runs inside a transaction that is rolled back.
- **API tests** use `httpx.AsyncClient` with `ASGITransport` against the app, override `get_current_user`, and cover the ownership rule: every endpoint has a test that user B gets `404` on user A's resource.
- **Unit tests** for pure logic: extractor, money parsing, pagination.
- **OCR tests:** the extractor is tested with text fixtures. One integration test runs real Tesseract on a small fixture image and is marked `@pytest.mark.ocr`, skipped when the `tesseract` binary is missing.
- **Worker tests** call the task function directly with procrastinate's in-memory connector; no running worker needed.
- **Migration check:** `alembic upgrade head`, `alembic downgrade base`, `alembic upgrade head`, and `alembic check` (no model changes without a migration).

## 14. CI (GitHub Actions)

One workflow on push and pull request:

1. `uv sync --frozen`
2. `ruff check` and `ruff format --check`
3. Postgres 16 service container, Tesseract installed via apt.
4. Migration check (section 13).
5. `pytest` (including `ocr` tests).
6. `docker build` for both targets (no push).

No secrets are needed in CI; `JWT_SECRET` is a throwaway value set in the workflow.

## 15. MCP server (optional, M6)

A TypeScript MCP server in `mcp/` that calls the REST API with a user's token. Tools: `list_expenses`, `add_expense`, `upload_receipt`, `get_receipt`, `confirm_receipt`, `spending_summary` (sum per category and currency over a date range, computed client-side from the list endpoint). Token and base URL come from env vars.

## 16. Milestones

| Milestone | Scope                                              |
|-----------|----------------------------------------------------|
| M1        | Scaffold, expenses CRUD, Alembic, pytest          |
| M2        | Categories, tags, filters                          |
| M3        | Receipts upload, worker, Tesseract, confirm        |
| M4        | Auth (JWT)                                         |
| M5        | CI                                                 |
| M6        | MCP server in TypeScript (optional)               |

Tickets are tracked as GitHub Issues, each sized for 30–90 minutes.

## 17. Changes from the first draft

- Added a `receipts` table and a confirm step; upload no longer creates an expense directly.
- Added a `worker` service and a Postgres-backed queue (procrastinate).
- `confidence_score`, `vendor_name` and `line_items` removed from v1 OCR output; `mean_word_confidence` comes from Tesseract.
- `DATE` has no timezone, so "stored UTC" is dropped; all timestamps are `timestamptz`.
- Tags are per user; categories use `user_id IS NULL` instead of `is_global`.
- Money serialized as string; IDs are UUIDs everywhere.
- `PUT` replaced by `PATCH`; `404` for missing or foreign resources; `409`, `413`, `415` added.
- Auth spelled out (register, login, JWT) as its own milestone.
- MCP server kept as optional M6.
