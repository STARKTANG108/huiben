"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, assetUrl } from "@/lib/api";
import type { CustomBookOrder } from "@/lib/types";

export default function CustomBookPdfPage() {
  const { id: orderId } = useParams<{ id: string }>();
  const [order, setOrder] = useState<CustomBookOrder | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!orderId) return;
    const data = await api.getCustomBook(orderId);
    setOrder(data);
    setMessage(data.parent_message || "");
  }, [orderId]);

  useEffect(() => {
    if (!orderId) return;
    refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [orderId, refresh]);

  async function onSaveMessage() {
    if (!orderId || !message.trim()) {
      setError("请填写父母寄语");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateCustomBookParentMessage(orderId, message.trim());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onCreatePdf() {
    if (!orderId) return;
    if (!message.trim()) {
      setError("请先填写并保存父母寄语");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateCustomBookParentMessage(orderId, message.trim());
      const updated = await api.createCustomBookPdf(orderId);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-12">
      <div className="mb-8 flex items-center justify-between">
        <Link
          href={orderId ? `/custom-book/${orderId}/review` : "/custom-book"}
          className="text-sm text-[var(--accent)]"
        >
          ← 返回审核
        </Link>
      </div>

      <header className="mb-8 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)]">生成 PDF</h1>
        <p className="mt-3 text-sm text-[var(--ink-muted)]">
          封面 + 8 页故事 + 父母寄语
        </p>
      </header>

      {error && (
        <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="space-y-4 rounded-[28px] bg-white/70 p-6 shadow-sm">
        <label className="block">
          <span className="label">父母寄语</span>
          <textarea
            className="input min-h-32"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="写给孩子的话…"
            maxLength={800}
          />
        </label>
        <button
          type="button"
          className="btn-secondary w-full"
          disabled={busy}
          onClick={onSaveMessage}
        >
          保存寄语
        </button>
        <button
          type="button"
          className="btn-primary w-full"
          disabled={busy}
          onClick={onCreatePdf}
        >
          {busy ? "生成中…" : "合成绘本 PDF"}
        </button>

        {order?.pdf_url && (
          <a
            className="btn-secondary block w-full text-center"
            href={assetUrl(order.pdf_url)}
            target="_blank"
            rel="noreferrer"
          >
            下载 PDF
          </a>
        )}
      </div>
    </main>
  );
}
