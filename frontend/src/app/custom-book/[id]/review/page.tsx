"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, assetUrl } from "@/lib/api";
import { useJobPoll } from "@/lib/useJobPoll";
import type { CustomBookOrder } from "@/lib/types";

function downloadImage(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.target = "_blank";
  a.rel = "noreferrer";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function CustomBookReviewPage() {
  const { id: orderId } = useParams<{ id: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<CustomBookOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyPage, setBusyPage] = useState<number | null>(null);
  const [textDrafts, setTextDrafts] = useState<Record<number, string>>({});
  // 用户正在编辑（未保存）的页码：轮询刷新时不要用服务端旧值覆盖输入框
  const dirtyPagesRef = useRef<Set<number>>(new Set());

  const refresh = useCallback(async () => {
    if (!orderId) return;
    const data = await api.getCustomBook(orderId);
    setOrder(data);
    // 只对「未在编辑」的页面同步服务端文字，避免轮询打断输入
    setTextDrafts((prev) => {
      const drafts: Record<number, string> = {};
      data.pages.forEach((p) => {
        drafts[p.page_no] =
          dirtyPagesRef.current.has(p.page_no) && prev[p.page_no] !== undefined
            ? prev[p.page_no]
            : p.text;
      });
      return drafts;
    });
    if (
      data.status === "character_pending" ||
      data.status === "preparing" ||
      data.status === "draft"
    ) {
      router.replace(`/custom-book/${orderId}/character`);
    }
  }, [orderId, router]);

  useEffect(() => {
    if (!orderId) return;
    refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [orderId, refresh]);

  // 仅在生成绘本页时轮询
  useJobPoll(!!order && order.status === "pages_generating", refresh, 3000);

  async function onGeneratePages() {
    if (!orderId) return;
    setError(null);
    try {
      await api.generateCustomBookPages(orderId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function onRegen(pageNo: number) {
    if (!orderId) return;
    setBusyPage(pageNo);
    setError(null);
    try {
      await api.regenerateCustomBookPage(orderId, pageNo);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyPage(null);
    }
  }

  async function onSaveText(pageNo: number) {
    if (!orderId) return;
    const text = (textDrafts[pageNo] || "").trim();
    if (!text) return;
    setBusyPage(pageNo);
    try {
      await api.updateCustomBookPageText(orderId, pageNo, text);
      dirtyPagesRef.current.delete(pageNo);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyPage(null);
    }
  }

  const generating = order?.status === "pages_generating";
  const canGenerate =
    order?.status === "character_confirmed" ||
    (order?.status === "pages_review" &&
      order.pages.some((p) => !p.image_url || p.status === "failed"));
  const readyCount =
    order?.pages.filter((p) => p.status === "ready" || p.status === "locked")
      .length || 0;
  const allReady = !!order && order.pages.length === 8 && readyCount === 8;
  const canMakePdf = readyCount === 8;

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Link href="/custom-book" className="text-sm text-[var(--accent)]">
          ← 订单列表
        </Link>
        <div className="flex gap-2">
          <Link
            href={orderId ? `/custom-book/${orderId}/character` : "#"}
            className="btn-secondary text-sm"
          >
            角色
          </Link>
          {canMakePdf && (
            <Link
              href={orderId ? `/custom-book/${orderId}/pdf` : "#"}
              className="btn-primary text-sm"
            >
              生成绘本 PDF
            </Link>
          )}
        </div>
      </div>

      <header className="mb-8 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)]">
          {order?.title || "绘本审核"}
        </h1>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">
          已完成 {readyCount}/8 页 · 单页失败会跳过继续 · 全部完成后生成 PDF
        </p>
      </header>

      {error && (
        <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {order?.error && (
        <p className="mb-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {order.error}
        </p>
      )}

      {(canGenerate || generating) && (
        <div className="mb-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            className="btn-primary"
            disabled={generating}
            onClick={onGeneratePages}
          >
            {generating
              ? "Flux 逐页生成中（失败会跳过）…"
              : readyCount > 0
                ? "继续生成未完成页"
                : "开始生成 8 页绘本"}
          </button>
          {canMakePdf && (
            <Link
              href={orderId ? `/custom-book/${orderId}/pdf` : "#"}
              className="btn-secondary"
            >
              8 页已齐 → 去生成 PDF
            </Link>
          )}
        </div>
      )}

      {allReady && (
        <div className="mb-8 rounded-[24px] bg-emerald-50 px-5 py-4 text-center text-sm text-[var(--leaf)]">
          全部页面已生成。请填写父母寄语并合成 PDF。
          <Link
            href={orderId ? `/custom-book/${orderId}/pdf` : "#"}
            className="ml-2 font-semibold underline"
          >
            立即生成 PDF
          </Link>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        {(order?.pages || []).map((page) => (
          <article
            key={page.page_no}
            className="overflow-hidden rounded-[24px] bg-white/75 shadow-sm"
          >
            <div className="relative aspect-[3/4] bg-[var(--sand)]/40">
              {page.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={assetUrl(page.image_url)}
                  alt={`第${page.page_no}页`}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-[var(--ink-muted)]">
                  {page.status === "generating"
                    ? "生成中…"
                    : page.status === "failed"
                      ? "生成失败"
                      : "待生成"}
                </div>
              )}
              {page.image_url && (
                <button
                  type="button"
                  className="absolute right-2 top-2 rounded-full bg-black/55 px-3 py-1 text-xs text-white"
                  onClick={() =>
                    downloadImage(
                      assetUrl(page.image_url!),
                      `${order?.title || "page"}_${page.page_no}.png`
                    )
                  }
                >
                  下载
                </button>
              )}
            </div>
            <div className="space-y-3 p-4">
              <p className="text-xs font-semibold text-[var(--accent)]">
                第 {page.page_no} 页 · {page.emotion}
                {page.status === "failed" ? " · 失败可重试" : ""}
              </p>
              <textarea
                className="input min-h-20 text-sm"
                value={textDrafts[page.page_no] ?? page.text}
                onChange={(e) => {
                  dirtyPagesRef.current.add(page.page_no);
                  setTextDrafts((d) => ({
                    ...d,
                    [page.page_no]: e.target.value,
                  }));
                }}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={busyPage === page.page_no}
                  onClick={() => onSaveText(page.page_no)}
                >
                  保存文字
                </button>
                {page.image_url && (
                  <button
                    type="button"
                    className="btn-secondary text-xs"
                    onClick={() =>
                      downloadImage(
                        assetUrl(page.image_url!),
                        `${order?.title || "page"}_${page.page_no}.png`
                      )
                    }
                  >
                    下载图片
                  </button>
                )}
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={
                    busyPage === page.page_no ||
                    (page.status !== "failed" &&
                      page.regen_count >= 1 &&
                      !!page.image_url)
                  }
                  onClick={() => onRegen(page.page_no)}
                >
                  {page.status === "failed"
                    ? busyPage === page.page_no
                      ? "重试中…"
                      : "重试本页"
                    : page.regen_count >= 1
                      ? "已达重生上限"
                      : busyPage === page.page_no
                        ? "重生中…"
                        : page.image_url
                          ? "重新生成本页"
                          : "生成本页"}
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
