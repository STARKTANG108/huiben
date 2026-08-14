---
version: 1
default_provider: openai
default_quality: 2k
default_aspect_ratio: "3:4"
default_image_size: null
default_image_api_dialect: openai-native
default_model:
  google: null
  openai: jimeng-3.0
  openrouter: null
  dashscope: null
  jimeng: null
  seedream: null
  replicate: null
  codex-cli: null
batch:
  max_workers: 3
---

# baoyu-image-gen 默认配置

使用 OpenAI 兼容接口（当前指向 suxi / jimeng-3.0）。
Key 写在 `.baoyu-skills/.env`（已 gitignore）。
Web 小红绿书也会从 Pictale `runtime_config` 自动补齐缺失的 OPENAI_*。
