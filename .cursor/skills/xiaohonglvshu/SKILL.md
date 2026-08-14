---
name: xiaohonglvshu
description: >-
  小红绿书生成工具：粘贴 X/Twitter 或文章链接，提炼后输出可发帖标题+正文，并用
  baoyu-xhs-images + baoyu-image-gen 生成不超过 3 张竖版 3:4 内容卡片图。
  在 Pictale 使用 /xiaohonglvshu。
---

# 小红绿书生成工具

## 正确方向

用户丢 **X / 文章链接** → DeepSeek 提炼标题+正文+要点 → **baoyu-xhs-images** 风格组装提示 → **baoyu-image-gen** CLI 出卡片图（≤3 张，3:4）。

**不再**走 Pictale `/settings` 的 suxi 生图 Key。

## 依赖 Skill（已装）

| Skill | 路径 |
|-------|------|
| `baoyu-xhs-images` | `.agents/skills/baoyu-xhs-images` / `.cursor/skills/baoyu-xhs-images` |
| `baoyu-image-gen` | `.agents/skills/baoyu-image-gen` / `.cursor/skills/baoyu-image-gen` |

来源：https://github.com/JimLiu/baoyu-skills

## 配置

1. 复制 `.baoyu-skills/.env.example` → `.baoyu-skills/.env`
2. 填入 baoyu-image-gen 支持的任一 Provider Key（OpenAI / Google / OpenRouter / DashScope / 即梦官方 AK/SK 等）
3. 偏好：`.baoyu-skills/baoyu-xhs-images/EXTEND.md`（默认 notion + balanced）
4. 需要 `bun` 或 `npx bun`

## Web 流水线

- `POST /api/xhs` `{ url, notes?, max_cards, style?, layout? }`
- 后端：`xhs_fetch` → DeepSeek → `xhs_baoyu.generate_xhs_viz_via_baoyu`（首图作后续 ref 锚点）

## Agent 手动出图

也可在对话中直接调用 `baoyu-xhs-images`（可加 `--yes`），对已提炼的 `storage/xhs/{id}/` 内容出图。
