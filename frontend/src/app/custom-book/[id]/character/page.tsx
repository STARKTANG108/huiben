"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, assetUrl } from "@/lib/api";
import { useJobPoll } from "@/lib/useJobPoll";
import type { CustomBookOrder } from "@/lib/types";

const VIEW_LABEL: Record<string, string> = {
  front: "正面",
  side: "侧面",
  full: "全身",
  happy: "开心",
  crying: "哭泣",
};

export default function CharacterConfirmPage() {
  const { id: orderId } = useParams<{ id: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<CustomBookOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [promptDraft, setPromptDraft] = useState("");

  const refresh = useCallback(async () => {
    if (!orderId) return;
    const data = await api.getCustomBook(orderId);
    setOrder(data);
    if (data.character?.character_prompt) {
      setPromptDraft(data.character.character_prompt);
    }
  }, [orderId]);

  useEffect(() => {
    if (!orderId) return;
    refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [orderId, refresh]);

  // Only poll while character sheets are still generating
  useJobPoll(
    !!order &&
      (order.status === "preparing" ||
        order.status === "draft" ||
        (order.status === "character_pending" && !order.character_assets.length)),
    refresh,
    3000,
  );

  async function onConfirm() {
    if (!orderId) return;
    setBusy(true);
    setError(null);
    try {
      await api.confirmCustomBookCharacter(orderId);
      router.push(`/custom-book/${orderId}/review`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  async function onRegen() {
    if (!orderId) return;
    setBusy(true);
    setError(null);
    try {
      await api.regenerateCustomBookCharacter(orderId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRetryPrepare() {
    if (!orderId) return;
    setBusy(true);
    setError(null);
    try {
      await api.prepareCustomBook(orderId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSavePrompt() {
    if (!orderId || !promptDraft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateCustomBookCharacterPrompt(orderId, promptDraft.trim());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const preparing =
    order?.status === "preparing" ||
    order?.status === "draft" ||
    order?.status === "story_ready";
  const pending = order?.status === "character_pending";
  const primary =
    order?.character_assets.find((a) => a.view_type === "front") ||
    order?.character_assets[0];
  const full = order?.character_assets.find((a) => a.view_type === "full");

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/custom-book" className="text-sm text-[var(--accent)]">
          ← 订单列表
        </Link>
        <p className="text-xs text-[var(--ink-muted)]">
          {order ? `${order.child_name} · ${order.theme}` : "加载中…"}
        </p>
      </div>

      <header className="mb-8 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)] sm:text-5xl">
          确认这个角色是否像孩子？
        </h1>
        <p className="mt-3 text-[var(--ink-muted)]">
          这是整本绘本的角色锁定关卡。确认后才会开始生成 8 页故事图。
        </p>
      </header>

      {error && (
        <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {order?.error && (
        <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {order.error}
        </p>
      )}

      {order?.status === "failed" && (
        <div className="mb-8 flex justify-center">
          <button
            type="button"
            className="btn-primary px-8"
            disabled={busy}
            onClick={onRetryPrepare}
          >
            {busy ? "重试中…" : "重新生成脚本与角色"}
          </button>
        </div>
      )}

      {preparing && (
        <div className="mb-8 rounded-[28px] bg-white/70 px-6 py-10 text-center shadow-sm">
          <p className="font-display text-2xl text-[var(--ink)]">正在生成角色设计图…</p>
          <p className="mt-2 text-sm text-[var(--ink-muted)]">
            DeepSeek 写脚本与角色档案 → Flux 生成正面 / 侧面 / 全身 / 表情
          </p>
        </div>
      )}

      {order && (pending || order.character_assets.length > 0) && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="relative overflow-hidden rounded-[28px] bg-white/80 shadow-sm">
              {primary && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={assetUrl(primary.url)}
                  alt="角色正面"
                  className="aspect-[3/4] w-full object-cover"
                />
              )}
              {primary && (
                <a
                  className="absolute right-2 top-2 rounded-full bg-black/55 px-3 py-1 text-xs text-white"
                  href={assetUrl(primary.url)}
                  download={`${order.child_name}_front.png`}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载
                </a>
              )}
              <p className="px-4 py-3 text-center text-sm font-semibold">
                {VIEW_LABEL[primary?.view_type || "front"] || "角色"}
              </p>
            </div>
            <div className="relative overflow-hidden rounded-[28px] bg-white/80 shadow-sm">
              {full && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={assetUrl(full.url)}
                  alt="角色全身"
                  className="aspect-[3/4] w-full object-cover"
                />
              )}
              {full && (
                <a
                  className="absolute right-2 top-2 rounded-full bg-black/55 px-3 py-1 text-xs text-white"
                  href={assetUrl(full.url)}
                  download={`${order.child_name}_full.png`}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载
                </a>
              )}
              <p className="px-4 py-3 text-center text-sm font-semibold">全身</p>
            </div>
          </div>

          <div className="mb-6 grid grid-cols-3 gap-3">
            {order.character_assets
              .filter((a) => !["front", "full"].includes(a.view_type))
              .map((a) => (
                <div
                  key={a.view_type}
                  className="relative overflow-hidden rounded-2xl bg-white/70 shadow-sm"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={assetUrl(a.url)}
                    alt={a.view_type}
                    className="aspect-square w-full object-cover"
                  />
                  <a
                    className="absolute right-1 top-1 rounded-full bg-black/55 px-2 py-0.5 text-[10px] text-white"
                    href={assetUrl(a.url)}
                    download={`${order.child_name}_${a.view_type}.png`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    下载
                  </a>
                  <p className="py-2 text-center text-xs">
                    {VIEW_LABEL[a.view_type] || a.view_type}
                  </p>
                </div>
              ))}
          </div>

          <section className="mb-8">
            <p className="mb-3 text-sm font-semibold text-[var(--ink-muted)]">
              对照原照片
            </p>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {order.photos.map((p) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={p.id}
                  src={assetUrl(p.url)}
                  alt="原照片"
                  className="h-28 w-28 shrink-0 rounded-2xl object-cover"
                />
              ))}
            </div>
          </section>

          {pending && (
            <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button
                type="button"
                className="btn-primary px-8"
                disabled={busy}
                onClick={onConfirm}
              >
                ✅ 确认角色
              </button>
              <button
                type="button"
                className="btn-secondary px-8"
                disabled={busy}
                onClick={onRegen}
              >
                ❌ 重新生成
              </button>
            </div>
          )}

          {order.status !== "character_pending" &&
            order.status !== "preparing" &&
            order.status !== "draft" &&
            order.status !== "failed" && (
              <div className="mb-8 flex justify-center">
                <Link
                  href={`/custom-book/${orderId}/review`}
                  className="btn-primary px-8"
                >
                  进入绘本审核 →
                </Link>
              </div>
            )}

          <div className="rounded-[24px] bg-white/60 p-4">
            <button
              type="button"
              className="text-xs text-[var(--ink-muted)] underline"
              onClick={() => setShowAdmin((v) => !v)}
            >
              管理员：编辑 character_prompt
            </button>
            {showAdmin && (
              <div className="mt-3 space-y-3">
                <textarea
                  className="input min-h-28 font-mono text-xs"
                  value={promptDraft}
                  onChange={(e) => setPromptDraft(e.target.value)}
                />
                <p className="text-xs text-[var(--ink-muted)]">
                  普通用户只能点「重新生成」。改 prompt 后请再点重新生成角色图。
                </p>
                <button
                  type="button"
                  className="btn-secondary text-sm"
                  disabled={busy}
                  onClick={onSavePrompt}
                >
                  保存 Prompt
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}
