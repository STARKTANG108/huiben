"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function BookPage() {
  const router = useRouter();
  const [bookTitle, setBookTitle] = useState("");
  const [theme, setTheme] = useState("");
  const [keyLessons, setKeyLessons] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!bookTitle.trim()) {
      setError("请填写书名");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await api.createBook({
        book_title: bookTitle.trim(),
        theme: theme.trim(),
        key_lessons: keyLessons.trim(),
        notes: notes.trim(),
      });
      await api.runBookPipeline(project.id);
      router.push(`/book/${project.id}`);
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
        <h1 className="font-display text-4xl text-[var(--ink)]">书籍剪辑</h1>
        <p className="mt-3 text-[var(--ink-muted)]">
          《一生》式说书：veo3.1-fast 首尾帧开场 · 故事配图 · MiniMax 配音配乐
        </p>
        <p className="mt-1 text-xs text-[var(--ink-muted)]">
          约 3 分钟成片 · 前 8 秒图生视频 · 8–12 张配图
        </p>
      </header>

      <ul className="mb-8 space-y-1.5 rounded-2xl bg-white/50 px-4 py-3 text-left text-xs leading-relaxed text-[var(--ink-muted)]">
        <li>· 开场：第 1 张首帧 + 第 2 张尾帧，ToAPIs veo3.1-fast 生成 8 秒竖屏（保留原声）</li>
        <li>· 后续：其余配图烧录字幕，与开场视频拼接成完整成片</li>
        <li>· 配音：MiniMax 旁白贯穿全片；配乐压低不抢旁白</li>
        <li>· 布局：顶部《书名》，底部口播逐字稿</li>
      </ul>

      <form onSubmit={onSubmit} className="space-y-4 rounded-[28px] bg-white/70 p-6 shadow-sm">
        <label className="block">
          <span className="label">书名</span>
          <input
            className="input"
            value={bookTitle}
            onChange={(e) => setBookTitle(e.target.value)}
            placeholder="例如：小王子 / 人性的弱点 / 活着"
            required
            maxLength={120}
          />
        </label>

        <label className="block">
          <span className="label">讲述角度（可选）</span>
          <input
            className="input"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="例如：成年人如何重新学会看见真心"
          />
        </label>

        <label className="block">
          <span className="label">已知大道理 / 要点（可选）</span>
          <textarea
            className="input"
            rows={3}
            value={keyLessons}
            onChange={(e) => setKeyLessons(e.target.value)}
            placeholder="例如：真正重要的东西用眼睛看不见；驯养意味着责任…"
          />
        </label>

        <label className="block">
          <span className="label">补充材料（可选）</span>
          <textarea
            className="input"
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="可粘贴书摘、章节要点、想强调的情节…"
          />
        </label>

        {error && (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full py-3">
          {busy ? "创建中…" : "开始书籍剪辑"}
        </button>
        <p className="text-center text-xs text-[var(--ink-muted)]">
          成片约 3 分钟 · 配图约 10 张 · 发布时可用封面图作封面
        </p>
      </form>
    </main>
  );
}
