<div align="center">

# 📚 Pictale · AI 儿童绘本创作平台

**输入一个主题，AI 自动完成「写故事 → 画插画 → 配音 → 配乐 → 剪视频」，**
**一键产出 绘本视频 / 定制绘本 PDF —— 不需要会画画、会剪辑、会写代码。**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/STARKTANG108/huiben)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

</div>

---

## 🤔 这是什么？

Pictale 是一个 **AI 绘本制作平台**，把绘本创作的全流程自动化：

- 🎬 给一个主题（如「月亮上的小兔子学会分享」）→ 约 **1 分钟**得到有配音、有配乐的**绘本短视频**
- 📖 上传 3–5 张孩子照片 → AI 生成以孩子为主角的 **8 页定制绘本 PDF**（Flux 角色锁定，主角长相贯穿全书）
- 🧬 你写一段人生故事 → 约 30 秒**治愈系短片**（《1000种人生》配方）
- 📚 给一个书名 → 3 分钟**说书式视频**（《一生》式 + 开场动效）
- ✂️ 一句话 brief → 分镜静帧 + 字幕 → **混剪预览成片**

## ✨ 五大创作模块

| 模块 | 入口 | 输入 → 输出 |
|------|------|-------------|
| 🎬 儿童绘本视频 | `/pictale` | 主题 + 年龄段 → 故事/分镜/插画/配音/配乐 → 约 1 分钟竖屏成片 |
| 📖 儿童定制绘本 | `/custom-book` | 3–5 张孩子照片 → 角色确认 → Flux 生成 8 页 → 精美 PDF |
| 🧬 人生副本 | `/life` | 一段人生故事 → 先配音再出图 → 30 秒治愈短片 |
| 📚 书籍剪辑 | `/book` | 书名 → 3 分钟说书视频（开场 8 秒图生视频） |
| ✂️ 混剪视频 | `/cut` | 一句话 brief → 分镜静帧 + 字幕 → 预览成片 |

## 🔄 工作流程

绘本视频全自动流水线（每步都可以在界面上单独执行 / 重做）：

```
输入主题
   │
   ▼
① 故事 ──▶ ② 脚本 ──▶ ③ 分镜 ──▶ ④ 插画 ──▶ ⑤ 配音 ──▶ ⑥ 配乐 ──▶ ⑦ 成片 MP4
（起承转合） （约60秒旁白） （6–8镜） （每镜静帧） （Edge/MiniMax） （ffmpeg 合成）
```

## 💎 为什么用它

- 🆓 **免费模型已接好**：生图 Pollinations（免费免 Key）、配音 Edge TTS（免费真人声），文本一键切换 DeepSeek / Gemini / Groq（填免费 Key）
- 🔑 **Key 只在网页里配**：所有模型 Key 在 `/settings` 页面填写，存在你自己的部署实例里，**永不写入仓库**
- 🔌 **Provider 可插拔**：每个能力一个接口（`backend/app/providers/`），Mock 随时换成真实模型
- 🖼️ **角色一致性**：定制绘本用 Flux 角色锁定（正面/侧面/全身/表情四视图确认），同一主角贯穿 8 页
- 📦 **数据持久化**：部署带持久卷，订单、Key、生成的作品重启不丢
- 🚀 **一键部署**：Render / Railway / Zeabur / 本地 Docker

## 🚀 快速开始

### 方式一：本地开发（已装 Python + Node）

```bash
git clone https://github.com/STARKTANG108/huiben.git
cd huiben
chmod +x scripts/dev.sh
./scripts/dev.sh
```

- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 方式二：一键部署（推荐）

支持 **Render / Railway / Zeabur**，仓库已内置部署文件：

| 文件 | 说明 |
|------|------|
| `render.yaml` | Render 一键蓝图（后端带 2GB 持久盘） |
| `docker-compose.yml` | Railway / Zeabur 自动识别；本地 `docker compose up -d` 亦可 |
| `backend/Dockerfile` · `frontend/Dockerfile` | 前后端镜像 |

**Render（点一下就行）**：点上方按钮 → 选仓库 → 自动创建后端（FastAPI + 持久盘）与前端（Next.js），前端自动把 `/api/*` 代理到后端，**无需配置任何环境变量**。

**Railway / Zeabur**：New Project → Deploy from GitHub repo → 选 `STARKTANG108/huiben` → 平台识别 `docker-compose.yml` → 把 frontend 暴露到公网即可。

**本地 Docker**：

```bash
docker compose up -d --build
```

> 部署后打开网页 → 「模型配置」填上你的模型 Key 即可开始制作。Key 保存在持久卷，不进仓库。

## 🧰 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 15 · TypeScript · Tailwind |
| 后端 | FastAPI · Pydantic v2 |
| 状态 | 内存 Store + SQLite（定制绘本订单持久化） |
| 媒体 | 本地 `backend/storage/`（ffmpeg 合成） |

## 📐 目录结构

```
huiben/
├── backend/
│   ├── app/providers/    # 可插拔模型（文本/生图/配音/配乐/视频）
│   ├── app/services/     # 流水线编排（pictale/life/book/cut/custom-book）
│   ├── app/routers/      # REST API
│   ├── app/store/        # 内存 Store + SQLite
│   ├── data/             # 运行时配置（Key，不入库）
│   └── storage/          # 生成的图/音/视频（不入库）
├── frontend/             # Next.js 工作台
├── docker-compose.yml    # 一键部署
├── render.yaml           # Render 蓝图
└── scripts/dev.sh        # 本地开发脚本
```

## 🔌 接入自己的模型

在 `backend/app/providers/` 实现与 Mock 相同的 Protocol（见 `base.py`），在 `registry.py` 注册即可切换。已预留 `stub_openai_story.py`、`stub_cosyvoice_tts.py`。

## 📡 API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}` | 项目状态 |
| POST | `/api/projects/{id}/steps/{step}` | 执行单步 |
| POST | `/api/projects/{id}/run` | 一键跑流水线（可带 `from_step`） |
| GET | `/api/projects/{id}/assets/{asset_id}` | 媒体文件 |
| GET | `/api/providers` | 当前/可用 Provider |

---

<div align="center">

**Made with ❤️ · 给每个孩子一个属于自己的故事**

</div>
