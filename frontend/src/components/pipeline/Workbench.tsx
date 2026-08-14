"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, assetUrl } from "@/lib/api";
import type { BookProject, LifeProject, Project, StepName } from "@/lib/types";
import { LIFE_PIPELINE_STEPS, PIPELINE_STEPS } from "@/lib/types";
import { useJobPoll } from "@/lib/useJobPoll";

type PipelineProject = Project | BookProject | LifeProject;
type WorkbenchMode = "pictale" | "book" | "life";

interface WorkbenchProps {
  projectId: string;
  mode?: WorkbenchMode;
}

export function Workbench({ projectId, mode = "pictale" }: WorkbenchProps) {
  const [project, setProject] = useState<PipelineProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const p =
      mode === "book"
        ? await api.getBook(projectId)
        : mode === "life"
          ? await api.getLife(projectId)
          : await api.getProject(projectId);
    setProject(p);
    return p;
  }, [projectId, mode]);

  useEffect(() => {
    refresh().catch((e) => setError(String(e.message || e)));
  }, [refresh]);

  // 人生副本：进入工作台后若还在 pending，自动开跑（每个项目只触发一次）
  const autoStartedRef = useRef<string | null>(null);
  useEffect(() => {
    if (mode !== "life" || !project) return;
    if (autoStartedRef.current === project.id) return;
    if (project.job_status !== "pending") return;
    if (!("story_text" in project) || !(project as LifeProject).story_text) return;
    autoStartedRef.current = project.id;
    let cancelled = false;
    (async () => {
      try {
        const p = await api.runLifePipeline(project.id);
        if (!cancelled) setProject(p);
      } catch {
        /* ignore — may already be running */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, project]);

  useJobPoll(project?.job_status === "running", refresh, 3000);

  async function runAll() {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const p =
        mode === "book"
          ? await api.runBookPipeline(project.id)
          : mode === "life"
            ? await api.runLifePipeline(project.id)
            : await api.runPipeline(project.id);
      setProject(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runOne(step: StepName) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const p =
        mode === "book"
          ? await api.runBookStep(project.id, step)
          : mode === "life"
            ? await api.runLifeStep(project.id, step)
            : await api.runStep(project.id, step);
      setProject(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (!project) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-[var(--ink-muted)]">
        {error || "加载中…"}
      </div>
    );
  }

  const running = busy || project.job_status === "running";
  const video = project.video;
  const stepList = mode === "life" ? LIFE_PIPELINE_STEPS : PIPELINE_STEPS;
  const doneCount = stepList.filter(
    (s) => project.steps[s.id]?.status === "completed"
  ).length;

  let headline = project.story?.title || "";
  if (!headline) {
    if ("book_title" in project) headline = project.book_title;
    else if ("premise" in project) headline = project.premise || "人生副本";
    else headline = project.theme;
  }

  const meta =
    mode === "book"
      ? {
          backHref: "/book",
          backLabel: "← 再剪一本书",
          storyLabel: "讲述骨架 · 书中大道理",
          durationHint: " · 成片约 3 分钟 · 前 8 秒开场动效",
          showCover: true,
        }
      : mode === "life"
        ? {
            backHref: "/life",
            backLabel: "← 再开一条人生",
            storyLabel: "平行人生 · 假如故事",
            durationHint: " · 成片约 30 秒（试用）",
            showCover: true,
          }
        : {
            backHref: "/pictale",
            backLabel: "← 新主题",
            storyLabel: "故事",
            durationHint: "",
            showCover: false,
          };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <Link href={meta.backHref} className="text-sm text-[var(--accent)]">
            {meta.backLabel}
          </Link>
          <h1 className="font-display mt-2 text-3xl text-[var(--ink)]">{headline}</h1>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            {mode === "book" && "book_title" in project
              ? `《${project.book_title}》 · `
              : ""}
            {mode === "life" && "vibe" in project && project.vibe
              ? `${project.vibe} · `
              : ""}
            {doneCount}/{stepList.length} 步完成
            {project.job_status === "running"
              ? ` · ${currentStepLabel(project.current_step, stepList)}`
              : ""}
            {meta.durationHint}
          </p>
        </div>
        <button
          type="button"
          className="btn-primary shrink-0"
          disabled={running}
          onClick={runAll}
        >
          {running ? "制作中…" : "一键生成"}
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {project.job_error && (
        <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {project.job_error}
        </p>
      )}

      <ol className="mb-8 space-y-2">
        {stepList.map((s) => {
          const st = project.steps[s.id]?.status ?? "pending";
          return (
            <li
              key={s.id}
              className="flex items-center justify-between rounded-2xl bg-white/60 px-4 py-3"
            >
              <span className="font-medium text-[var(--ink)]">{s.label}</span>
              <span className="flex items-center gap-3">
                <span className="text-sm text-[var(--ink-muted)]">{statusZh(st)}</span>
                <button
                  type="button"
                  className="text-sm text-[var(--accent)] underline disabled:opacity-40"
                  disabled={running}
                  onClick={() => runOne(s.id)}
                >
                  重做
                </button>
              </span>
            </li>
          );
        })}
      </ol>

      {project.story && (
        <section className="mb-6 rounded-[24px] bg-white/70 p-5">
          <h2 className="font-display text-xl">{meta.storyLabel}</h2>
          <p className="mt-2 text-[var(--ink-muted)]">{project.story.summary}</p>
          {project.story.lessons && project.story.lessons.length > 0 && (
            <p className="mt-2 text-sm text-[var(--accent)]">
              {mode === "life" ? "人生节点：" : "爽点："}
              {project.story.lessons.join(" · ")}
            </p>
          )}
          <div className="mt-3 space-y-2 text-sm leading-relaxed">
            {project.story.paragraphs.map((p) => (
              <p key={p.index}>{p.text}</p>
            ))}
          </div>
        </section>
      )}

      {project.storyboard?.shots.some((s) => s.image_asset_id) && (
        <section className="mb-6">
          <h2 className="font-display mb-3 text-xl">
            配图
            {mode === "life"
              ? `（${project.storyboard.shots.length} 镜）`
              : ""}
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {project.storyboard.shots.map((shot) => {
              const asset = shot.image_asset_id
                ? project.assets[shot.image_asset_id]
                : null;
              return (
                <div key={shot.index} className="overflow-hidden rounded-xl bg-white/70">
                  {asset ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={assetUrl(asset.url)}
                      alt=""
                      className="aspect-[9/16] w-full object-cover"
                    />
                  ) : (
                    <div className="aspect-[9/16] bg-[var(--sand)]" />
                  )}
                  {mode === "life" && shot.on_screen_text && (
                    <p className="px-2 py-1.5 text-center text-xs text-[var(--ink-muted)]">
                      {shot.on_screen_text}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {(project.tts || project.bgm) && (
        <section className="mb-6 space-y-3 rounded-[24px] bg-white/70 p-5">
          <h2 className="font-display text-xl">声音</h2>
          {project.tts && (
            <div>
              <p className="mb-1 text-sm text-[var(--ink-muted)]">配音</p>
              <audio controls className="w-full" src={assetUrl(project.tts.asset.url)} />
            </div>
          )}
          {project.bgm && (
            <div>
              <p className="mb-1 text-sm text-[var(--ink-muted)]">配乐</p>
              <audio controls className="w-full" src={assetUrl(project.bgm.asset.url)} />
            </div>
          )}
        </section>
      )}

      {video && (
        <section className="rounded-[24px] bg-white/70 p-5">
          <h2 className="font-display mb-3 text-xl">成片</h2>
          <video
            controls
            playsInline
            className="mx-auto max-h-[70vh] w-full max-w-sm rounded-xl bg-black object-contain"
            src={assetUrl(video.asset.url)}
          />
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              href={assetUrl(video.asset.url)}
              download={video.asset.filename}
              className="btn-primary inline-flex"
            >
              下载视频
            </a>
            {meta.showCover &&
              "cover_asset_id" in project &&
              project.cover_asset_id &&
              project.assets[project.cover_asset_id] && (
                <a
                  href={assetUrl(project.assets[project.cover_asset_id].url)}
                  download={project.assets[project.cover_asset_id].filename}
                  className="btn-secondary inline-flex"
                >
                  下载封面
                </a>
              )}
          </div>
          {meta.showCover && project.story?.cover_hook && (
            <p className="mt-3 text-sm text-[var(--ink-muted)]">
              封面钩子：{project.story.cover_hook}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function statusZh(s: string): string {
  switch (s) {
    case "completed":
      return "完成";
    case "running":
      return "进行中";
    case "failed":
      return "失败";
    default:
      return "等待";
  }
}

function currentStepLabel(
  current: string | null | undefined,
  stepList: { id: string; label: string }[]
): string {
  const step = stepList.find((s) => s.id === current);
  return step ? `正在${step.label}…` : "制作中…";
}
