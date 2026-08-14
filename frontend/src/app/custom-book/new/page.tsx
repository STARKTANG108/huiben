"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { CustomBookKeysPanel } from "@/components/CustomBookKeysPanel";
import { api } from "@/lib/api";

const MAX_PHOTOS = 5;
const MIN_PHOTOS = 3;

function fileKey(f: File): string {
  return `${f.name}:${f.size}:${f.lastModified}`;
}

export default function CustomBookNewPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [childName, setChildName] = useState("");
  const [age, setAge] = useState(3);
  const [gender, setGender] = useState<"boy" | "girl">("boy");
  const [theme, setTheme] = useState("");
  const [emotionGoal, setEmotionGoal] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previewUrls = useMemo(
    () => photos.map((f) => URL.createObjectURL(f)),
    [photos]
  );

  useEffect(() => {
    return () => {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [previewUrls]);

  function onPickPhotos(list: FileList | null) {
    if (!list || list.length === 0) return;
    const incoming = Array.from(list).filter((f) => f.type.startsWith("image/"));
    setPhotos((prev) => {
      const seen = new Set(prev.map(fileKey));
      const merged = [...prev];
      for (const f of incoming) {
        const key = fileKey(f);
        if (seen.has(key)) continue;
        if (merged.length >= MAX_PHOTOS) break;
        seen.add(key);
        merged.push(f);
      }
      return merged;
    });
    // 允许再次选择同一批文件继续追加
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function removePhoto(index: number) {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (photos.length < MIN_PHOTOS) {
      setError(`请至少上传 ${MIN_PHOTOS} 张孩子照片（当前 ${photos.length} 张）`);
      return;
    }
    if (!childName.trim() || !theme.trim()) {
      setError("请填写昵称与主题");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("child_name", childName.trim());
      form.append("age", String(age));
      form.append("gender", gender);
      form.append("theme", theme.trim());
      form.append("emotion_goal", emotionGoal.trim());
      form.append("auto_prepare", "true");
      photos.forEach((f) => form.append("photos", f));
      const order = await api.createCustomBook(form);
      router.push(`/custom-book/${order.id}/character`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-12">
      <div className="mb-8">
        <Link href="/custom-book" className="text-sm text-[var(--accent)]">
          ← 订单列表
        </Link>
      </div>

      <header className="mb-8 text-center">
        <h1 className="font-display text-4xl text-[var(--ink)]">新建绘本订单</h1>
        <p className="mt-3 text-sm text-[var(--ink-muted)]">
          上传照片后将自动生成故事与角色设计图（不批量生绘本页）
        </p>
      </header>

      <div className="mb-6">
        <CustomBookKeysPanel compact />
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-[28px] bg-white/70 p-6 shadow-sm"
      >
        <label className="block">
          <span className="label">孩子昵称</span>
          <input
            className="input"
            value={childName}
            onChange={(e) => setChildName(e.target.value)}
            placeholder="豆豆"
            required
            maxLength={40}
          />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="label">年龄</span>
            <input
              className="input"
              type="number"
              min={1}
              max={12}
              value={age}
              onChange={(e) => {
                const v = Number(e.target.value);
                setAge(Number.isFinite(v) ? Math.min(12, Math.max(1, v || 1)) : 1);
              }}
              required
            />
          </label>
          <label className="block">
            <span className="label">性别</span>
            <select
              className="input"
              value={gender}
              onChange={(e) => setGender(e.target.value as "boy" | "girl")}
            >
              <option value="boy">男孩</option>
              <option value="girl">女孩</option>
            </select>
          </label>
        </div>

        <label className="block">
          <span className="label">绘本主题</span>
          <input
            className="input"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="第一次上幼儿园"
            required
            maxLength={120}
          />
        </label>

        <label className="block">
          <span className="label">希望解决的问题 / 情绪目标</span>
          <input
            className="input"
            value={emotionGoal}
            onChange={(e) => setEmotionGoal(e.target.value)}
            placeholder="缓解分离焦虑"
            maxLength={200}
          />
        </label>

        <div className="block">
          <span className="label">
            孩子照片（{MIN_PHOTOS}–{MAX_PHOTOS} 张，可分多次添加）
          </span>
          <input
            ref={fileInputRef}
            className="input"
            type="file"
            accept="image/*"
            multiple
            disabled={photos.length >= MAX_PHOTOS}
            onChange={(e) => onPickPhotos(e.target.files)}
          />
          <p className="mt-1 text-xs text-[var(--ink-muted)]">
            已选 {photos.length}/{MAX_PHOTOS} 张
            {photos.length < MIN_PHOTOS
              ? ` · 还差 ${MIN_PHOTOS - photos.length} 张`
              : photos.length >= MAX_PHOTOS
                ? " · 已达上限"
                : " · 可继续追加"}
          </p>

          {photos.length > 0 && (
            <ul className="mt-3 grid grid-cols-3 gap-2">
              {photos.map((f, i) => (
                <li
                  key={fileKey(f)}
                  className="relative overflow-hidden rounded-2xl bg-[var(--sand)]/40"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={previewUrls[i]}
                    alt={f.name}
                    className="aspect-square w-full object-cover"
                  />
                  <button
                    type="button"
                    className="absolute right-1 top-1 rounded-full bg-black/55 px-2 py-0.5 text-xs text-white"
                    onClick={() => removePhoto(i)}
                  >
                    删除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {error && (
          <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "创建中…" : "创建并生成角色"}
        </button>
      </form>
    </main>
  );
}
