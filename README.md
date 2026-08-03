# LiveOS

AI Native Living Decision System

## Development

## Quick Start

### API

```bash
# Start PostgreSQL from the repository root.
docker compose up -d postgres

cd apps/api
uv sync --python 3.13
cp .env.example .env
uv run --python 3.13 uvicorn app.main:app --reload
```

The API requires `DATABASE_URL` in `apps/api/.env`:

```dotenv
DATABASE_URL=postgresql://liveos:liveos_dev@127.0.0.1:5432/liveos
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
COOKIE_SECURE=false
```

If startup reports `ValidationError: DATABASE_URL / Field required`, update
`apps/api/.env` and confirm the PostgreSQL Compose service is running. The API
does not fall back to SQLite.

### Web

```bash
cd apps/web
pnpm install
pnpm dev
```

## Common Development Issues

### Cannot find module

请检查：

- 文件夹名称是否包含空格
- 文件名大小写是否一致
- macOS 是否缓存目录名称
- TypeScript Server 是否需要重启
