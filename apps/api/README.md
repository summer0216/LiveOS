# LiveOS API

## Development Environment

The API requires PostgreSQL. SQLite is not a runtime option or fallback.

Required tools:

- Python 3.13
- `uv`
- Docker with Compose

The lockfile fixes the Python dependency stack, including Psycopg 3, OpenAI,
HTTPX, pytest, and Ruff.

## PostgreSQL Setup

Start the repository's PostgreSQL service from the repository root:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U liveos liveos_test
```

The second command is only needed once. The application initializes its seven
runtime tables on startup. Docker stores local PostgreSQL data in the named
`liveos-postgres` volume.

Development URL:

```text
postgresql://liveos:liveos_dev@127.0.0.1:5432/liveos
```

Test URL:

```text
postgresql://liveos:liveos_dev@127.0.0.1:5432/liveos_test
```

These are local-only development credentials, not production secrets.

## Setup

```bash
cd apps/api
uv sync --python 3.13
cp .env.example .env
```

Set the real OpenAI values in `.env`. `DATABASE_URL` is mandatory for the API.

A complete local development configuration should include:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
DATABASE_URL=postgresql://liveos:liveos_dev@127.0.0.1:5432/liveos
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
COOKIE_SECURE=false
```

Start the API:

```bash
uv run --python 3.13 uvicorn app.main:app --reload
```

## Startup Troubleshooting

If startup fails with the following Pydantic error:

```text
ValidationError: DATABASE_URL
Field required
```

the local `apps/api/.env` is missing the required PostgreSQL connection URL.
Add the development `DATABASE_URL` shown above, then make sure PostgreSQL is
running before starting Uvicorn:

```bash
# Run from the repository root.
docker compose up -d postgres

# Run from apps/api.
uv run --python 3.13 uvicorn app.main:app --reload
```

This is an environment configuration failure. Do not change Runtime or
business logic to bypass it, and do not add a SQLite fallback.

## Verification

With the `liveos_test` database running, execute:

```bash
cd apps/api
uv run --python 3.13 pytest
uv run --python 3.13 ruff check app tests
```

Tests default to the local `liveos_test` URL. To use another isolated test
database without changing application configuration:

```bash
TEST_DATABASE_URL=postgresql://user:password@host:5432/liveos_test \
  uv run --python 3.13 pytest
```

`pyproject.toml` configures `pythonpath = ["."]`; no manual `PYTHONPATH` is
required.
