# LiveOS

AI Native Living Decision System

## Development

## Quick Start

在仓库根目录启动数据库和 API，再启动要开发的前端。

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

### 3. Unified Frontend v2.0

新前端位于 `apps/liveos`，独立运行在 http://localhost:3002。Experience 01 提供 First Open、真实 SSE Conversation 与刷新历史恢复；当前不包含地图或 Living World。

```bash
pnpm install
pnpm --filter liveos-frontend dev
```

运行检查：

```bash
pnpm --filter liveos-frontend type-check
pnpm --filter liveos-frontend lint
pnpm --filter liveos-frontend build
pnpm --filter liveos-frontend exec node --experimental-strip-types --test tests/conversation-messages.test.mjs
```

新应用通过 Next rewrite 将 `/api/*` 转发到 API。开发环境默认使用 `http://127.0.0.1:8000`；部署时设置 `RENDER_API_URL` 或 `INTERNAL_API_URL`。

`apps/liveos/infrastructure/conversationApi.ts` 调用已验证的 Conversation API 实现。SSE、历史读取、API 请求配置及相关契约当前通过 `apps/liveos/tsconfig.json` 的路径映射复用 `apps/web/services`、`apps/web/lib` 和 `apps/web/types` 中的能力代码；新前端不依赖旧页面、First Open、Unified Surface、Presentation Policy 或 World Runtime。

### 4. Existing Web (Legacy)

```bash
cd apps/web
pnpm dev
```

旧 Web 启动后访问 http://localhost:3000。它保留现有体验及地图实现，作为能力参考；第三代新体验从 `apps/liveos` 开始开发。

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
