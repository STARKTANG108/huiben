"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

const AGES = ["3-5", "3-6", "6-8", "8-10"];

export function HomeForm() {
  const router = useRouter();
  const [theme, setTheme] = useState("");
  const [age, setAge] = useState("3-6");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!theme.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({
        theme: theme.trim(),
        age_range: age,
        style: "watercolor",
      });
      // Kick off full pipeline
      await api.runPipeline(project.id);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto w-full max-w-xl space-y-5">
      <label className="block">
        <span className="label">故事主题</span>
        <input
          className="input text-lg"
          placeholder="例如：月亮上的小兔子学会分享"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          required
          maxLength={200}
        />
      </label>

      <label className="block">
        <span className="label">适合年龄</span>
        <select
          className="input"
          value={age}
          onChange={(e) => setAge(e.target.value)}
        >
          {AGES.map((a) => (
            <option key={a} value={a}>
              {a} 岁
            </option>
          ))}
        </select>
      </label>
      <p className="text-sm text-[var(--ink-muted)]">画风固定：水彩绘本 · 竖屏 9:16</p>

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <button type="submit" disabled={busy} className="btn-primary w-full py-3 text-lg">
        {busy ? "正在创建…" : "开始制作"}
      </button>
      <p className="text-center text-xs text-[var(--ink-muted)]">
        未配置文本 Key 时用本地演示故事；生图/配音默认免费
      </p>
    </form>
  );
}
