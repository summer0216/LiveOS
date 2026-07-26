# LiveOS

AI Native Living Decision System

## Development

## Quick Start

### API

```bash
cd apps/api

uv venv

source .venv/bin/activate

uv sync

uv run uvicorn app.main:app --reload


### Web

cd apps/web

pnpm install

pnpm dev


## Common Development Issues

### Cannot find module

请检查：

- 文件夹名称是否包含空格
- 文件名大小写是否一致
- macOS 是否缓存目录名称
- TypeScript Server 是否需要重启