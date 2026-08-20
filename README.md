# 漫剧带货平台 (mangjiudaihuo-v2)

> AI 漫剧/带货 系列生产平台 —— 填商品,点按钮,拿视频。

**只需要 5 个 API 端点** + **一个表单** 就能跑通完整带货流程。

## 一句话使用

```bash
# 注册 → 创建带货项目 → 一键生成 → 下载视频
curl 注册 → 创建项目 → run-all → 下载 MP4
```

详细 cURL 见 [docs/API_QUICKSTART.md](docs/API_QUICKSTART.md)。

## 5 个端点

| # | 端点 | 用途 |
|---|---|---|
| 1 | `POST /auth/register` 或 `/auth/login` | 注册/登录拿 JWT |
| 2 | `POST /products/from-manual` | 填商品名/卖点 → 创建带货项目 |
| 3 | `POST /projects/{id}/run-all` | 一键跑通 ①剧本 → ②角色 → ③分镜 → ③视频 → 配音 → ④合成 |
| 4 | `GET /projects/{id}/download/{type}` | 下载视频/剧本(`project` / `episode-N` / `script`) |
| 5 | `PATCH /settings` | (可选) 填你自己的 API key |

## 本地启动

### 方式 A:Docker(最快)

```bash
docker compose up --build
# 前端 http://localhost:3000
# 后端 http://localhost:8000
```

### 方式 B:分开跑

**后端**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

**前端**:
```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
# 浏览器 http://localhost:3000
```

## 工作流(用户视角)

1. **打开** `http://localhost:3000` → 注册/登录
2. **填表单**:商品名 /价格 /卖点(每行 1 条) /目标人群 /风格 /集数 /时长
3. **点 "🎬 生成带货短剧"** → 等 30-90 秒
4. **点下载链接** → 拿到 MP4 文件

## 计费模式

| 模式 | 配置 | 平台收入 |
|---|---|---|
| **BYOK(自带 key)** | 默认。在 "API 设置" 填你自己的 toapis/yijia key | 0(用户自己付 API) |
| **平台积分** | 预留 UI,暂时不可用 | 平台代理调 API,差价抽成 |

**没填 key → 自动走 local_preview 模式**(任何人能跑通,模板视频演示用)。

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 (async) + SQLite + ffmpeg
- **前端**: Next.js 16 + React 19 + TypeScript + Tailwind
- **AI 集成**: OpenAI  兼容(toapis / /yijia / /openai_compat),可扩展

## 项目结构

```
mangjiudaihuo-v2/
├── README.md                # 本文档
├── docker-compose.yml        # 一键起
├── docs/
│   └── API_QUICKSTART.md     # 5 端点 cURL 范例
├── backend/
│   ├── app/
│   │   ├── core/             # config, db, security, log
│   │   ├── providers/        # 5 类 Provider 抽象 + 4 个实现
│   │   └── modules/
│   │       ├── auth/         # 注册/登录/JWT
│   │       ├── project/      # 项目 CRUD + download + run-all
│   │       ├── settings/     # BYOK API key 配置
│   │       ├── product/      # 带货入口: from-manual + run-all
│   │       ├── script/       # ① 剧本生成
│   │       ├── character/    # ② 角色锚点图
│   │       ├── storyboard/   # ③ 分镜
│   │       ├── video/        # ③ 视频生成
│   │       ├── tts/          # 配音 (edge-tts)
│   │       └── composite/    # ④ 合成 (ffmpeg)
│   ├── tests/                # pytest, 5/5 通过
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── login/            # 登录/注册
    │   ├── settings/         # API 设置(BYOK)
    │   └── page.tsx          # 主页:带货表单
    ├── components/
    │   └── Navbar.tsx
    └── lib/api.ts            # API client
```

## 完整 API 文档

启动后端后访问 **http://localhost:8000/docs** 看 Swagger 自动生成的 API 文档(全部端点)。

用户面只需要上面 5 个端点。

## 测试

```bash
cd backend
APP_ENV=test python -m pytest tests/ -v
# 5 passed
```