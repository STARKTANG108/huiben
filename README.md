# Pictale

儿童绘本视频制作站：输入主题 → 故事 → 脚本 → 分镜 → 画面 → 配音 → 配乐 → 约 1 分钟成片。

各能力通过 **Provider 接口** 解耦，默认全部为 Mock，可随时换成真实模型。

## 儿童定制绘本（custom-book）

半自动生产后台：照片 → 角色确认 → Flux 8 页 → PDF。

- 入口：http://localhost:3000/custom-book
- API：`/api/custom-book/orders`
- Flux：在定制绘本页填写 CatsAPI Token（`cats-…`），模型 `flux2Pro`
- 文本：沿用「模型配置」里的 DeepSeek

不替换现有绘本视频 / 听页 / 混剪产品线。

## 模型配置（免费已接好）

打开前端 **模型配置** 页（`/settings`）：

| 模块 | 默认 | 说明 |
|------|------|------|
| 文本（故事/脚本/分镜） | 本地演示 | 可一键切 Gemini / Groq（填免费 Key）或自定义 URL+Key |
| 生图 | Pollinations | **免费、无需 Key** |
| 配音 | Edge TTS | **免费真人声、无需 Key** |
| 配乐 / 成片 | Mock + ffmpeg | 本机合成 |

配置保存在 `backend/data/runtime_config.json`（勿提交 Key）。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 15 · TypeScript · Tailwind |
| 后端 | FastAPI · Pydantic v2 |
| 状态 | 内存 Store（可换 Redis/DB） |
| 媒体 | 本地 `backend/storage/` |

## 快速开始

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 一键部署

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/STARKTANG108/huiben)

支持 **Render / Railway / Zeabur** 等容器平台，仓库内已带：

- `docker-compose.yml` — Railway / Zeabur 自动识别；本地 `docker compose up -d` 亦可
- `render.yaml` — Render 蓝图（含后端持久盘，重启不丢数据）
- `backend/Dockerfile` + `frontend/Dockerfile`

### Render（一键）

1. 点击上方按钮（或访问 `https://render.com/deploy?repo=https://github.com/STARKTANG108/huiben`）
2. 选仓库 → 自动创建 `huiben-backend`（FastAPI + 持久盘）与 `huiben-frontend`（Next.js）
3. 前端会自动把 `/api/*` 代理到后端，**无需配置任何前端环境变量**

### Railway / Zeabur

1. 控制台 → New Project → Deploy from GitHub repo → 选择 `STARKTANG108/huiben`
2. 平台识别 `docker-compose.yml`，自动起 backend + frontend
3. 把 frontend 服务暴露到公网域名即可

### 本地 Docker

```bash
docker compose up -d --build
# 前端 http://localhost:3000 · 后端 http://localhost:8000
```

> 数据持久化：模型 Key（在网页 /settings 里配置）、订单数据库、生成的图片/视频都保存在持久卷中，重启/重新部署不丢失。
> 模型 Key 永远只存在于你部署实例的环境/配置里，不会写入仓库。

### 手动启动

```bash
# 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

## 流水线步骤

1. **story** — 主题生成故事  
2. **script** — 旁白脚本（约 60 秒）  
3. **storyboard** — 6–8 个分镜  
4. **images** — 每镜绘本静帧  
5. **tts** — 配音  
6. **bgm** — 背景乐  
7. **video** — 合成 MP4（有 ffmpeg 则做幻灯片；否则占位文件）

## 切换 / 接入新模型

在 `backend/.env` 中设置：

```env
PROVIDER_STORY=mock
PROVIDER_SCRIPT=mock
PROVIDER_STORYBOARD=mock
PROVIDER_IMAGE=mock
PROVIDER_TTS=mock
PROVIDER_BGM=mock
PROVIDER_VIDEO=mock
```

接入步骤：

1. 在 `backend/app/providers/` 实现与 Mock 相同的 `Protocol`（见 `base.py`）
2. 在 `registry.py` 对应字典中注册，例如 `"openai": OpenAIStoryProvider`
3. 将 `PROVIDER_*` 改为新名称

已预留 stub：`stub_openai_story.py`、`stub_cosyvoice_tts.py`。

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}` | 项目状态 |
| POST | `/api/projects/{id}/steps/{step}` | 执行单步 |
| POST | `/api/projects/{id}/run` | 一键跑流水线（可带 `from_step`） |
| GET | `/api/projects/{id}/assets/{asset_id}` | 媒体文件 |
| GET | `/api/providers` | 当前/可用 Provider |

## 目录结构

```
pictale/
├── backend/app/providers/   # 可插拔模型
├── backend/app/services/    # 流水线编排
├── backend/storage/         # 生成的图/音/视频
├── frontend/                # 步进工作台
└── scripts/dev.sh
```
