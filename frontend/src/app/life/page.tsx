"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { LifeOptions } from "@/lib/types";

const DEFAULT_VOICE = "Chinese (Mandarin)_Gentleman";
const DEFAULT_BGM = "illusionary_daytime";

const FALLBACK_OPTIONS: LifeOptions = {
  durations: [],
  bgm_tracks: [
    { id: "illusionary_daytime", title: "Illusionary Daytime" },
    { id: "windy_hill", title: "Windy Hill" },
    { id: "", title: "系统随机" },
  ],
  voices: [
    { id: DEFAULT_VOICE, label: "温润男声（推荐）", group: "说书男声" },
    { id: "Chinese (Mandarin)_Radio_Host", label: "电台男主播", group: "说书男声" },
    { id: "Chinese (Mandarin)_Male_Announcer", label: "男声播音", group: "说书男声" },
  ],
  defaults: {
    target_sec: 0,
    tts_voice: DEFAULT_VOICE,
    bgm_track_id: DEFAULT_BGM,
  },
};

export default function LifePage() {
  const router = useRouter();
  const [options, setOptions] = useState<LifeOptions>(FALLBACK_OPTIONS);
  const [title, setTitle] = useState("");
  const [storyText, setStoryText] = useState("");
  const [notes, setNotes] = useState("");
  const [ttsVoice, setTtsVoice] = useState(DEFAULT_VOICE);
  const [bgmTrackId, setBgmTrackId] = useState(DEFAULT_BGM);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getLifeOptions()
      .then((o) => {
        setOptions(o);
        setTtsVoice(String(o.defaults.tts_voice || DEFAULT_VOICE));
        setBgmTrackId(String(o.defaults.bgm_track_id || DEFAULT_BGM));
      })
      .catch(() => {
        /* keep fallback */
      });
  }, []);

  const voiceGroups = useMemo(() => {
    const map = new Map<string, { id: string; label: string }[]>();
    for (const v of options.voices) {
      if (!v.id) continue; // 配方已有明确默认音色，隐藏「系统默认」空项
      const g = v.group || "其它";
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push({ id: v.id, label: v.label });
    }
    return [...map.entries()];
  }, [options.voices]);

  const bgmTracks = useMemo(() => {
    // 推荐曲放前，随机放后
    const tracks = options.bgm_tracks.filter((t) => t.id);
    const auto = options.bgm_tracks.find((t) => !t.id);
    return auto ? [...tracks, auto] : tracks;
  }, [options.bgm_tracks]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const story = storyText.trim();
    if (!story) {
      setError("请先写进故事正文");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await api.createLife({
        title: title.trim(),
        story_text: story,
        notes: notes.trim(),
        target_sec: 0,
        tts_voice: ttsVoice || DEFAULT_VOICE,
        bgm_track_id: bgmTrackId || DEFAULT_BGM,
      });
      router.push(`/life/${project.id}`);
      void api.runLifePipeline(project.id).catch(() => undefined);
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
        <h1 className="font-display text-4xl text-[var(--ink)]">人生副本</h1>
        <p className="mt-3 text-[var(--ink-muted)]">
          《1000种不一样的人生》· 不内卷样本 · 治愈视听
        </p>
        <p className="mt-1 text-xs text-[var(--ink-muted)]">
          你写人生，系统用固定配方呈现
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4 rounded-[28px] bg-white/70 p-6 shadow-sm">
        <label className="block">
          <span className="label">标题（可选）</span>
          <input
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="留在县城的那十年"
            maxLength={80}
          />
          <span className="mt-1 block text-xs text-[var(--ink-muted)]">
            片头：1000种平行人生之{title.trim() || "（标题）"}
          </span>
        </label>

        <label className="block">
          <span className="label">故事正文（必填）</span>
          <textarea
            className="input min-h-[220px] font-sans leading-relaxed"
            rows={12}
            value={storyText}
            onChange={(e) => setStoryText(e.target.value)}
            placeholder={
              "把口播故事写在这里，建议一句一行：\n\n假如那年我没离开县城……\n高考后我报了本地师范。\n毕业进了中学，骑电动车上下班。\n同学在大城市漂着，我在菜市场挑西红柿。\n……"
            }
            maxLength={12000}
            required
          />
          <p className="mt-2 text-xs leading-relaxed text-[var(--ink-muted)]">
            结构提示：钩子设定 → 高考/志愿/就业/婚恋/育儿节点 → 大城市对比 →
            日常细节 → 河流式收束
          </p>
          <span className="mt-1 block text-right text-xs text-[var(--ink-muted)]">
            {storyText.trim().length} / 12000
          </span>
        </label>

        <div className="rounded-2xl border border-[var(--sand)] bg-[var(--cream)]/60 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-[var(--ink)]">
                本集配方：县城安稳·治愈
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[var(--ink-muted)]">
                日系圆润人物 + 写实县城场景 · 暖色胶片 · 克制男声 · 轻钢琴垫乐
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-[var(--leaf)]/15 px-2.5 py-0.5 text-xs text-[var(--leaf)]">
              推荐
            </span>
          </div>
          <button
            type="button"
            className="mt-3 text-xs text-[var(--accent)] underline"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? "收起高级设置" : "展开高级设置"}
          </button>

          {advancedOpen && (
            <div className="mt-4 space-y-3 border-t border-[var(--sand)] pt-4">
              <label className="block">
                <span className="label">配音音色</span>
                <select
                  className="input"
                  value={ttsVoice}
                  onChange={(e) => setTtsVoice(e.target.value)}
                >
                  {voiceGroups.map(([group, list]) => (
                    <optgroup key={group} label={group}>
                      {list.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="label">背景音乐</span>
                <select
                  className="input"
                  value={bgmTrackId}
                  onChange={(e) => setBgmTrackId(e.target.value)}
                >
                  {bgmTracks.map((t) => (
                    <option key={t.id || "auto"} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="label">主角外貌（可选）</span>
                <input
                  className="input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="例如：三十岁男人，短发，常穿深色外套"
                  maxLength={200}
                />
              </label>
            </div>
          )}
        </div>

        {error && (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full py-3">
          {busy ? "开启一种人生…" : "开启第 N 种人生"}
        </button>
        <p className="text-center text-xs text-[var(--ink-muted)]">
          成片时长跟配音走 · 先配音再出图
        </p>
      </form>
    </main>
  );
}
