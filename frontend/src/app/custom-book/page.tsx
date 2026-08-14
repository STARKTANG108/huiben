"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CustomBookKeysPanel } from "@/components/CustomBookKeysPanel";
import { api } from "@/lib/api";
import type { CustomBookOrderListItem } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  preparing: "生成角色中…",
  story_ready: "脚本完成",
  character_pending: "待确认角色",
  character_confirmed: "角色已确认",
  pages_generating: "绘本生成中…",
  pages_review: "待审核",
  pdf_ready: "PDF 已就绪",
  done: "完成",
  failed: "失败",
};

function nextPath(item: CustomBookOrderListItem): string {
  if (
    item.status === "character_pending" ||
    item.status === "preparing" ||
    item.status === "draft" ||
    item.status === "failed" ||
    item.status === "story_ready"
  ) {
    return `/custom-book/${item.id}/character`;
  }
  if (item.status === "pdf_ready" || item.status === "done") {
    return `/custom-book/${item.id}/pdf`;
  }
  return `/custom-book/${item.id}/review`;
}

export default function CustomBookListPage() {
  const [items, setItems] = useState<CustomBookOrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listCustomBooks()
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <div className="mb-8 flex items-center justify-between">
        <Link href="/" className="text-sm text-[var(--accent)]">
          ← 返回首页
        </Link>
        <div className="flex gap-2">
          <Link href="/settings" className="btn-secondary text-sm">
            全局模型配置
          </Link>
          <Link href="/custom-book/new" className="btn-primary text-sm">
            新建订单
          </Link>
        </div>
      </div>

      <header className="mb-8 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)]">儿童定制绘本</h1>
        <p className="mt-3 text-[var(--ink-muted)]">
          半自动生产 · 角色确认优先 · Flux 角色锁定
        </p>
      </header>

      <CustomBookKeysPanel />

      {error && (
        <p className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {loading ? (
        <div className="rounded-[28px] bg-white/70 p-10 text-center text-[var(--ink-muted)]">
          加载订单中…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-[28px] bg-white/70 p-10 text-center text-[var(--ink-muted)]">
          还没有订单。
          <Link href="/custom-book/new" className="ml-2 text-[var(--accent)]">
            创建第一本
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={nextPath(item)}
                className="flex items-center justify-between rounded-[24px] bg-white/75 px-5 py-4 shadow-sm transition hover:bg-white"
              >
                <div>
                  <p className="font-semibold text-[var(--ink)]">
                    {item.child_name} · {item.age}岁
                  </p>
                  <p className="mt-1 text-sm text-[var(--ink-muted)]">
                    {item.title || item.theme}
                  </p>
                </div>
                <span className="text-xs font-semibold text-[var(--accent)]">
                  {STATUS_LABEL[item.status] || item.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
