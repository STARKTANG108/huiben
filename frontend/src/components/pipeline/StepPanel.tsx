"use client";

import { assetUrl } from "@/lib/api";
import type { Project, StepName } from "@/lib/types";

interface StepPanelProps {
  project: Project;
  step: StepName;
  busy: boolean;
  onRegenerate: () => void;
  onContinue: () => void;
  onSaveStory: (title: string, summary: string, paragraphs: string[]) => void;
}

export function StepPanel({
  project,
  step,
  busy,
  onRegenerate,
  onContinue,
  onSaveStory,
}: StepPanelProps) {
  const state = project.steps[step];
  const error = state?.error;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={onRegenerate}
          className="btn-secondary"
        >
          {busy ? "处理中…" : "重新生成本步"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onContinue}
          className="btn-primary"
        >
          从本步继续到成片
        </button>
        {project.job_status === "running" && (
          <span className="text-sm text-[var(--ink-muted)]">流水线运行中…</span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        {step === "story" && (
          <StoryView project={project} onSave={onSaveStory} busy={busy} />
        )}
        {step === "script" && <ScriptView project={project} />}
        {step === "storyboard" && <StoryboardView project={project} />}
        {step === "images" && <ImagesView project={project} />}
        {step === "tts" && <AudioView project={project} kind="tts" />}
        {step === "bgm" && <AudioView project={project} kind="bgm" />}
        {step === "video" && <VideoView project={project} />}
      </div>
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <p className="rounded-2xl border border-dashed border-[var(--sand)] bg-white/40 px-6 py-16 text-center text-[var(--ink-muted)]">
      {text}
    </p>
  );
}

function StoryView({
  project,
  onSave,
  busy,
}: {
  project: Project;
  onSave: (title: string, summary: string, paragraphs: string[]) => void;
  busy: boolean;
}) {
  const story = project.story;
  if (!story) {
    return <EmptyHint text="点击「重新生成本步」生成故事，或使用「从本步继续到成片」。" />;
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const title = String(fd.get("title") || "");
        const summary = String(fd.get("summary") || "");
        const paragraphs = story.paragraphs.map((_, i) =>
          String(fd.get(`p-${i}`) || "")
        );
        onSave(title, summary, paragraphs);
      }}
    >
      <label className="block">
        <span className="label">标题</span>
        <input name="title" defaultValue={story.title} className="input" />
      </label>
      <label className="block">
        <span className="label">简介</span>
        <textarea
          name="summary"
          defaultValue={story.summary}
          rows={2}
          className="input"
        />
      </label>
      {story.paragraphs.map((p, i) => (
        <label key={p.index} className="block">
          <span className="label">段落 {i + 1}</span>
          <textarea
            name={`p-${i}`}
            defaultValue={p.text}
            rows={3}
            className="input"
          />
        </label>
      ))}
      <button type="submit" disabled={busy} className="btn-secondary">
        保存修改
      </button>
      <p className="text-xs text-[var(--ink-muted)]">
        Provider: {story.provider} · 适合 {story.age_range} 岁
      </p>
    </form>
  );
}

function ScriptView({ project }: { project: Project }) {
  const script = project.script;
  if (!script) return <EmptyHint text="尚未生成脚本。" />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--ink-muted)]">
        合计约 {script.total_sec.toFixed(1)} 秒 · Provider: {script.provider}
      </p>
      {script.lines.map((line) => (
        <div
          key={line.index}
          className="rounded-2xl bg-white/70 px-4 py-3 shadow-sm"
        >
          <div className="mb-1 flex justify-between text-xs text-[var(--ink-muted)]">
            <span>第 {line.index + 1} 句</span>
            <span>{line.estimated_sec.toFixed(1)}s</span>
          </div>
          <p className="leading-relaxed text-[var(--ink)]">{line.text}</p>
        </div>
      ))}
    </div>
  );
}

function StoryboardView({ project }: { project: Project }) {
  const board = project.storyboard;
  if (!board) return <EmptyHint text="尚未生成分镜。" />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--ink-muted)]">
        {board.shots.length} 个镜头 · 约 {board.total_sec.toFixed(1)} 秒
      </p>
      {board.shots.map((shot) => (
        <div
          key={shot.index}
          className="rounded-2xl border border-[var(--sand)] bg-white/70 p-4"
        >
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[var(--ink-muted)]">
            <span className="rounded-full bg-[var(--sand)] px-2 py-0.5 font-medium text-[var(--ink)]">
              镜头 {shot.index + 1}
            </span>
            <span>{shot.duration_sec.toFixed(1)}s</span>
            <span>{shot.camera}</span>
          </div>
          <p className="mb-2 font-medium text-[var(--ink)]">{shot.narration}</p>
          <p className="text-sm leading-relaxed text-[var(--ink-muted)]">
            {shot.visual_prompt}
          </p>
        </div>
      ))}
    </div>
  );
}

function ImagesView({ project }: { project: Project }) {
  const board = project.storyboard;
  if (!board?.shots.some((s) => s.image_asset_id)) {
    return <EmptyHint text="尚未生成画面。" />;
  }
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {board.shots.map((shot) => {
        const asset = shot.image_asset_id
          ? project.assets[shot.image_asset_id]
          : null;
        return (
          <figure
            key={shot.index}
            className="overflow-hidden rounded-2xl bg-white/70 shadow-sm"
          >
            {asset ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={assetUrl(asset.url)}
                alt={`镜头 ${shot.index + 1}`}
                className="aspect-video w-full object-cover"
              />
            ) : (
              <div className="flex aspect-video items-center justify-center bg-[var(--sand)] text-sm text-[var(--ink-muted)]">
                无图
              </div>
            )}
            <figcaption className="px-3 py-2 text-sm text-[var(--ink-muted)]">
              镜头 {shot.index + 1}
            </figcaption>
          </figure>
        );
      })}
    </div>
  );
}

function AudioView({
  project,
  kind,
}: {
  project: Project;
  kind: "tts" | "bgm";
}) {
  const result = kind === "tts" ? project.tts : project.bgm;
  if (!result) {
    return <EmptyHint text={kind === "tts" ? "尚未生成配音。" : "尚未生成配乐。"} />;
  }
  return (
    <div className="rounded-2xl bg-white/70 p-6 shadow-sm">
      <p className="mb-4 text-sm text-[var(--ink-muted)]">
        时长约 {result.duration_sec.toFixed(1)}s · Provider: {result.provider}
        {"mood" in result ? ` · 情绪: ${result.mood}` : ""}
      </p>
      <audio controls className="w-full" src={assetUrl(result.asset.url)} />
      <a
        href={assetUrl(result.asset.url)}
        download={result.asset.filename}
        className="mt-4 inline-block text-sm text-[var(--accent)] underline"
      >
        下载音频
      </a>
    </div>
  );
}

function VideoView({ project }: { project: Project }) {
  const video = project.video;
  if (!video) return <EmptyHint text="尚未生成成片。" />;
  const ffmpeg = video.asset.meta?.ffmpeg;
  return (
    <div className="rounded-2xl bg-white/70 p-6 shadow-sm">
      <p className="mb-4 text-sm text-[var(--ink-muted)]">
        约 {video.duration_sec.toFixed(1)}s · Provider: {video.provider}
        {ffmpeg === false && " · （未检测到 ffmpeg，已写入占位文件）"}
      </p>
      <video
        controls
        className="aspect-video w-full rounded-xl bg-black"
        src={assetUrl(video.asset.url)}
      />
      <a
        href={assetUrl(video.asset.url)}
        download={video.asset.filename}
        className="btn-primary mt-4 inline-flex"
      >
        下载成片
      </a>
    </div>
  );
}
