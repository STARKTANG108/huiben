"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, assetUrl } from "@/lib/api";
import type { CutProject } from "@/lib/types";
import { useJobPoll } from "@/lib/useJobPoll";

const STAGE_LABEL: Record<string, string> = {
  scaffold: "脚手架",
  plan: "分镜规划",
  clipseek: "素材检索",
  images: "静帧生图",
  render: "合成预览",
  done: "完成",
};

export default function CutProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [id, setId] = useState<string | null>(null);
  const [project, setProject] = useState<CutProject | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    params.then((p) => setId(p.id));
  }, [params]);

  const refresh = useCallback(async () => {
    if (!id) return;
    const p = await api.getCut(id);
    setProject(p);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    refresh().catch((e) => setError(String(e.message || e)));
  }, [id, refresh]);

  useJobPoll(project?.job_status === "running", refresh, 3000);

  if (!project) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-[var(--ink-muted)]">
        {error || "加载中…"}
      </div>
    );
  }

  const video = project.video_asset_id
    ? project.assets[project.video_asset_id]
    : null;
  const stageLabel = STAGE_LABEL[project.stage] || project.stage || "处理中";
  const doneScenes = project.scenes.filter((s) => s.image_asset_id).length;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/cut" className="text-sm text-[var(--accent)]">
            ← 再写一条 brief
          </Link>
          <h1 className="font-display mt-2 text-3xl text-[var(--ink)]">混剪预览</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ink-muted)]">
            {project.brief}
          </p>
          <p className="mt-2 text-sm text-[var(--ink-muted)]">
            {project.workflow} · {project.duration}s · {project.format}
            {" · "}
            {project.job_status === "running"
              ? `${stageLabel}${project.scenes.length ? ` · 画面 ${doneScenes}/${project.scenes.length}` : ""}`
              : project.job_status === "completed"
                ? `已完成${project.render_engine ? ` · ${project.render_engine}` : ""}`
                : project.job_status}
          </p>
        </div>
        <Link href="/settings" className="btn-secondary text-sm">
          模型配置
        </Link>
      </div>

      {project.job_error && (
        <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {project.job_error}
        </p>
      )}

      {project.doctor_hint && project.job_status !== "completed" && (
        <p className="mb-4 rounded-xl bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-900">
          {project.doctor_hint}
        </p>
      )}

      {video && (
        <section className="mb-8 overflow-hidden rounded-[24px] bg-black shadow-sm">
          <video
            className="mx-auto max-h-[70vh] w-full"
            src={assetUrl(video.url)}
            controls
            playsInline
          />
          <div className="flex justify-between gap-3 bg-white/95 px-4 py-3">
            <p className="text-sm text-[var(--ink-muted)]">预览成片</p>
            <a
              href={assetUrl(video.url)}
              download={video.filename}
              className="text-sm text-[var(--accent)] underline"
            >
              下载 MP4
            </a>
          </div>
        </section>
      )}

      {project.scenes.length > 0 && (
        <section className="mb-8">
          <h2 className="font-display mb-4 text-xl text-[var(--ink)]">分镜静帧</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {project.scenes.map((scene) => {
              const asset = scene.image_asset_id
                ? project.assets[scene.image_asset_id]
                : null;
              return (
                <article
                  key={scene.id}
                  className="overflow-hidden rounded-[20px] bg-white/70 shadow-sm"
                >
                  {asset ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={assetUrl(asset.url)}
                      alt={scene.caption || scene.purpose}
                      className="aspect-[9/16] w-full object-cover"
                    />
                  ) : (
                    <div className="flex aspect-[9/16] items-center justify-center bg-[var(--sand)] text-sm text-[var(--ink-muted)]">
                      {project.job_status === "running" ? "生图中…" : "等待中"}
                    </div>
                  )}
                  <div className="space-y-1 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
                      {scene.purpose || scene.id}
                    </p>
                    <p className="text-sm text-[var(--ink)]">{scene.caption || scene.visual}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {project.clipseek.length > 0 && (
        <section className="mb-8">
          <h2 className="font-display mb-3 text-xl text-[var(--ink)]">ClipSeek 参考素材</h2>
          <p className="mb-3 text-xs text-[var(--ink-muted)]">
            仅作检索线索；商用请自行核验授权页
          </p>
          <ul className="space-y-2 rounded-[20px] bg-white/70 p-4 text-sm shadow-sm">
            {project.clipseek.map((hit) => (
              <li key={hit.id} className="flex flex-wrap items-baseline gap-2">
                <span className="text-[var(--ink)]">{hit.title || hit.id}</span>
                <span className="text-xs text-[var(--ink-muted)]">{hit.provider}</span>
                {hit.source_page && (
                  <a
                    href={hit.source_page}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-[var(--accent)] underline"
                  >
                    来源
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {!video && project.job_status === "running" && (
        <p className="text-[var(--ink-muted)]">正在规划分镜并生成预览…</p>
      )}
    </main>
  );
}
