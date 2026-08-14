"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, assetUrl } from "@/lib/api";
import type { XhsProject } from "@/lib/types";
import { useJobPoll } from "@/lib/useJobPoll";

export default function XhsProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [id, setId] = useState<string | null>(null);
  const [project, setProject] = useState<XhsProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    params.then((p) => setId(p.id));
  }, [params]);

  const refresh = useCallback(async () => {
    if (!id) return;
    const p = await api.getXhs(id);
    setProject(p);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    refresh().catch((e) => setError(String(e.message || e)));
  }, [id, refresh]);

  useJobPoll(project?.job_status === "running", refresh, 3000);

  async function copyText(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  }

  if (!project) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-[var(--ink-muted)]">
        {error || "加载中…"}
      </div>
    );
  }

  const done = project.cards.filter((c) => c.image_asset_id).length;
  const pack = [project.post_title, "", project.post_body].filter(Boolean).join("\n");

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/xiaohonglvshu" className="text-sm text-[var(--accent)]">
            ← 再丢一条链接
          </Link>
          <h1 className="font-display mt-2 text-3xl text-[var(--ink)]">
            {project.post_title || project.source_title || "内容可视化"}
          </h1>
          <p className="mt-1 break-all text-sm text-[var(--ink-muted)]">{project.url}</p>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            {project.job_status === "running"
              ? `处理中 ${done}/${project.cards.length || "…"}…`
              : project.job_status === "completed"
                ? `已完成 ${project.cards.length} 张图`
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

      {(project.post_title || project.post_body) && (
        <section className="mb-8 space-y-5 rounded-[24px] bg-white/70 p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-xl text-[var(--ink)]">标题与正文</h2>
            <button
              type="button"
              className="text-sm text-[var(--accent)] underline"
              onClick={() => copyText("全文", pack)}
            >
              {copied === "全文" ? "已复制" : "一键复制"}
            </button>
          </div>
          {project.post_title && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <p className="text-xs font-semibold text-[var(--ink-muted)]">标题</p>
                <button
                  type="button"
                  className="text-xs text-[var(--accent)] underline"
                  onClick={() => copyText("标题", project.post_title)}
                >
                  {copied === "标题" ? "已复制" : "复制"}
                </button>
              </div>
              <p className="text-lg text-[var(--ink)]">{project.post_title}</p>
            </div>
          )}
          {project.post_body && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <p className="text-xs font-semibold text-[var(--ink-muted)]">正文</p>
                <button
                  type="button"
                  className="text-xs text-[var(--accent)] underline"
                  onClick={() => copyText("正文", project.post_body)}
                >
                  {copied === "正文" ? "已复制" : "复制"}
                </button>
              </div>
              <pre className="whitespace-pre-wrap rounded-2xl bg-[var(--sand)]/60 p-4 text-sm leading-relaxed text-[var(--ink)]">
                {project.post_body}
              </pre>
            </div>
          )}
          {project.summary && (
            <p className="text-xs leading-relaxed text-[var(--ink-muted)]">
              提炼摘要：{project.summary}
            </p>
          )}
        </section>
      )}

      <h2 className="font-display mb-4 text-xl text-[var(--ink)]">内容可视化图（≤3）</h2>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {project.cards.map((card) => {
          const asset = card.image_asset_id
            ? project.assets[card.image_asset_id]
            : null;
          return (
            <article
              key={card.index}
              className="overflow-hidden rounded-[24px] bg-white/70 shadow-sm"
            >
              {asset ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={assetUrl(asset.url)}
                  alt={card.title}
                  className="aspect-[3/4] w-full object-cover"
                />
              ) : (
                <div className="flex aspect-[3/4] items-center justify-center bg-[var(--sand)] text-sm text-[var(--ink-muted)]">
                  {project.job_status === "running" ? "生图中…" : "等待中"}
                </div>
              )}
              <div className="space-y-2 p-4">
                {card.hook && (
                  <p className="text-sm font-semibold text-[var(--accent)]">{card.hook}</p>
                )}
                <h3 className="font-display text-lg text-[var(--ink)]">{card.title}</h3>
                <ul className="space-y-1 text-sm text-[var(--ink-muted)]">
                  {card.points.map((p, i) => (
                    <li key={i}>
                      {i + 1}. {p}
                    </li>
                  ))}
                </ul>
                {asset && (
                  <a
                    href={assetUrl(asset.url)}
                    download={asset.filename}
                    className="inline-block pt-1 text-sm text-[var(--accent)] underline"
                  >
                    下载图片
                  </a>
                )}
              </div>
            </article>
          );
        })}
      </div>

      {!project.post_body && project.job_status === "running" && (
        <p className="mt-6 text-[var(--ink-muted)]">正在读取链接并提炼…</p>
      )}
    </main>
  );
}
