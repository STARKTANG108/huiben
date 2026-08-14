"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

const WORKFLOWS = [
  { id: "social-short", title: "短视频强节奏", hint: "抖音 / 小红书 / Reels" },
  { id: "stock-story", title: "免费素材故事", hint: "科普 / 概念 / B-roll" },
  { id: "person-profile", title: "人物档案", hint: "介绍 / 创始人 / 历史人物" },
  { id: "explainer", title: "知识科普", hint: "机制解释 / 抽象概念" },
  { id: "english-mix", title: "影视英语混剪", hint: "台词学习（需本地片源）" },
];

const FORMATS = ["9:16", "16:9", "1:1"];
const DURATIONS = [30, 45, 60, 90];

export default function CutPage() {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [workflow, setWorkflow] = useState("social-short");
  const [duration, setDuration] = useState(45);
  const [format, setFormat] = useState("9:16");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (brief.trim().length < 4) {
      setError("请写一句至少 4 字的创作 brief");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await api.createCut({
        brief: brief.trim(),
        workflow,
        duration,
        format,
        notes,
      });
      router.push(`/cut/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-12">
      <div className="mb-8 flex items-center justify-between">
        <Link href="/" className="text-sm text-[var(--accent)]">
          ← 返回首页
        </Link>
        <Link href="/settings" className="btn-secondary text-sm">
          模型配置
        </Link>
      </div>

      <header className="mb-10 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)]">混剪视频</h1>
        <p className="mt-3 text-[var(--ink-muted)]">
          一句话 brief → 分镜静帧 + 字幕 → 预览成片
        </p>
        <p className="mt-1 text-xs text-[var(--ink-muted)]">
          基于 qiaomu-cut · 文本用 DeepSeek · 静帧用生图 Key
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4 rounded-[28px] bg-white/70 p-6 shadow-sm">
        <label className="block">
          <span className="label">创作 brief</span>
          <textarea
            className="input"
            rows={4}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="例如：30 秒讲清「为什么早起反而更累」，节奏快、结尾要收藏点"
          />
        </label>

        <label className="block">
          <span className="label">工作流</span>
          <select
            className="input"
            value={workflow}
            onChange={(e) => setWorkflow(e.target.value)}
          >
            {WORKFLOWS.map((w) => (
              <option key={w.id} value={w.id}>
                {w.title} · {w.hint}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="label">时长（秒）</span>
            <select
              className="input"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            >
              {DURATIONS.map((d) => (
                <option key={d} value={d}>
                  {d}s
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">画幅</span>
            <select
              className="input"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              {FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="block">
          <span className="label">补充要求（可选）</span>
          <textarea
            className="input"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="例如：不要出现真人脸、字幕大一点、偏冷色…"
          />
        </label>

        {error && (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full py-3">
          {busy ? "创建中…" : "开始混剪预览"}
        </button>
      </form>
    </main>
  );
}
