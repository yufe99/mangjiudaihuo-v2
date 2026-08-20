# API 快速上手

只需要 **5 个端点** 就能跑通带货完整流程。

## Base URL

本地开发: `http://localhost:8000/api/v1`

## 5 个端点(按顺序调用)

### 1. 注册账号

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your_password_8_chars_min","name":"昵称"}'
```

返回 `{access_token, refresh_token, user}`。**保存 access_token**。

### 2. 登录(已有账号)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your_password"}'
```

### 3. 填商品 → 创建带货项目

```bash
curl -X POST http://localhost:8000/api/v1/products/from-manual \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "name": "胶原蛋白口服液",
    "price": 199,
    "selling_points": ["法国进口原料", "7天见效", "0添加蔗糖"],
    "target_audience": "25-35岁都市女性",
    "style": "美妆时尚",
    "episode_count": 3,
    "seconds_per_episode": 8
  }'
```

返回 `{project_id, project_name, episode_count, next_step}`。

### 4. 一键跑完整流程

```bash
curl -X POST http://localhost:8000/api/v1/projects/<project_id>/run-all \
  -H "Authorization: Bearer <your_token>"
```

返回:
- `characters`: 角色列表 + status
- `episodes`: 每个 episode 的故事板 + 视频状态
- `final_videos`: 每个 episode 的最终 MP4 路径
- `project_final_video`: 整剧视频路径(如果成功)

**耗时约 30-90 秒**(无 key 走 local_preview 时约 10-30 秒)。

### 5. 下载视频

```bash
# 下载整剧
curl -o project.mp4 http://localhost:8000/api/v1/projects/<project_id>/download/project

# 下载单集
curl -o ep1.mp4 http://localhost:8000/api/v1/projects/<project_id>/download/episode-1

# 下载剧本 JSON
curl http://localhost:8000/api/v1/projects/<project_id>/download/script
```

## 配置 API key(可选,带 key 走真 AI)

```bash
curl -X PATCH http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "provider_configs": {
      "toapis": {
        "api_key": "sk-你的toapis密钥",
        "base_url": "https://toapis.com/v1",
        "model": ""
      }
    },
    "billing_mode": "byok"
  }'
```

API key 在哪申请:
- **ToAPIs** — https://toapis.com/dashboard 注册登录拿 key
- **易加 AI** — https://ai.yijiarj.cn 注册拿 key

不填 key → 自动走 local_preview 模式(模板视频,演示用)。

## 完整带货流程的 cURL 例子

```bash
# 1. 注册
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"daihuo@example.com","password":"daihuo1234","name":"带货"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. 创建项目
PID=$(curl -s -X POST http://localhost:8000/api/v1/products/from-manual \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"胶原蛋白口服液","price":199,"selling_points":["法国进口原料","7天见效","0添加蔗糖"],"style":"美妆时尚","episode_count":3,"seconds_per_episode":8}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['project_id'])")

# 3. 一键跑通
curl -X POST http://localhost:8000/api/v1/projects/$PID/run-all \
  -H "Authorization: Bearer $TOKEN"

# 4. 下载第 1 集
curl -o ep1.mp4 http://localhost:8000/api/v1/projects/$PID/download/episode-1
```

## 关键说明

- **没填 API key 也能跑** —— 用本地预览(local_preview),生成模板化的 MP4(每个镜头 5-10 秒)
- **填了 API key 走真 AI** —— ToAPIs 网关调 deepseek / gpt-image-2 / seedance 等模型
- **生成失败的环节自动 fallback** —— 比如视频生成失败会用本地 ffmpeg 渲染占位视频
- **耗时** —— 无 key 全流程约 10-30 秒,有 key 看模型和网络

## 5 个端点之外的其他端点(高级用法,不需要看)

`/api/v1/projects` (CRUD)、`/api/v1/projects/{id}/characters` 等。**正常流程不需要调**。