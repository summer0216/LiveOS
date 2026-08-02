# LiveOS API

## Development Environment

Use the project-managed Python environment. Do not run the backend test suite
with the system Python.

Required runtime:

- Python 3.13
- `uv`

The dependency lock fixes the compatible client stack:

- `openai==2.46.0`
- `httpx==0.28.1`
- `pytest>=8.3,<9`

## Setup

```bash
cd apps/api
uv sync --python 3.13
```

## Verification

Run all backend tests:

```bash
cd apps/api
uv run --python 3.13 pytest
```

Run Ruff:

```bash
cd apps/api
uv run --python 3.13 ruff check app tests
```

`pyproject.toml` configures pytest with `pythonpath = ["."]`, so tests can
import the `app` package without manually exporting `PYTHONPATH`.

## Environment Variables

Copy `.env.example` to `.env` and provide the configured OpenAI values before
starting the API. Test commands may use non-production placeholder values when
the tests mock the AI client.
