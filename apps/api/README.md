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

Start the API:

```bash
uv run --python 3.13 uvicorn app.main:app --reload
```

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
