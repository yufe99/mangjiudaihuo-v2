# 部署指南

mangjiudaihuo-v2 支持三种部署方式,按阶段选择。

## 1. 本地开发(最快)

```bash
# 后端(终端 1)
cd backend
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --port 8000
# API 文档: http://localhost:8000/docs

# 前端(终端 2)
cd frontend
npm install
npm run dev
# UI: http://localhost:3000
```

## 2. Docker 一键起(演示/内网)

```bash
docker compose up --build
# 前端 http://localhost:3000
# 后端 http://localhost:8000
```

## 3. Cloudflare SaaS(给别人用)

### 3.1 前端 → CF Pages

```bash
cd frontend
npm run build
# output: .next (standalone) 或改 output: "export" 得静态文件
# Dashboard → Pages → Create → Upload assets
# 或 Connect to Git (yufe99/mangjiudaihuo-v2) 自动部署
```

### 3.2 后端 → CF Workers

Workers 跑 FastAPI 需要适配(见 cf-workers/README),或者用独立 VM/容器跑 Docker 镜像。

### 3.3 数据库 → D1 / 外部 Postgres

SQLite 只在单机模式;SaaS 需切 Postgres:

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/mjdh
```

### 3.4 存储 → R2

`STORAGE_BACKEND=s3` + R2 配置(backend/.env.example 有注释)。