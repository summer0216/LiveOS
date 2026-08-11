# LiveOS

AI Native Living Decision System

## Development

## Quick Start

在仓库根目录打开三个终端，按以下顺序启动本地服务。

### 1. PostgreSQL

```bash
docker compose up -d postgres
```

确认数据库服务已就绪：

```bash
docker compose ps
```

### 2. API

```bash
cd apps/api
uv sync --python 3.13
# 首次启动时复制配置文件，并填写 OPENAI_API_KEY 等真实配置。
cp -n .env.example .env
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

API 启动后可通过 http://127.0.0.1:8000/docs 访问接口文档。

### 3. Web

```bash
cd apps/web
pnpm install
pnpm dev
```

Web 启动后访问 http://localhost:3000。

### 常见启动问题

- `5432` 已被其他 PostgreSQL 占用时，先确认占用的数据库是否可使用项目配置中的
  `liveos / liveos_dev` 用户；否则请停止冲突服务后再运行 `docker compose up -d postgres`。
- API 报 `DATABASE_URL` 缺失时，检查 `apps/api/.env` 是否存在并包含上方的数据库连接配置。
- API 不使用 SQLite 回退；必须先启动并连接 PostgreSQL。

## Common Development Issues

### Cannot find module

请检查：

- 文件夹名称是否包含空格
- 文件名大小写是否一致
- macOS 是否缓存目录名称
- TypeScript Server 是否需要重启
