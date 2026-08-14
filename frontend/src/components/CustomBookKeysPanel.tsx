"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type RuntimeSettings } from "@/lib/api";

type Props = {
  compact?: boolean;
};

function fluxConfigured(s: RuntimeSettings): boolean {
  if (s.replicate_api_token_set) return true;
  if ((s.replicate_api_token || "").includes("••")) return true;
  if (s.image_preset === "flux" && s.image_api_key_set) return true;
  return false;
}

export function CustomBookKeysPanel({ compact = false }: Props) {
  const [deepseekKey, setDeepseekKey] = useState("");
  const [catsToken, setCatsToken] = useState("");
  const [textSet, setTextSet] = useState(false);
  const [fluxSet, setFluxSet] = useState(false);
  const [textHint, setTextHint] = useState("");
  const [fluxHint, setFluxHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const applySettings = useCallback((s: RuntimeSettings) => {
    setTextSet(!!s.text_api_key_set);
    setFluxSet(fluxConfigured(s));
    setTextHint(s.text_api_key || "");
    setFluxHint(
      s.replicate_api_token ||
        (s.image_preset === "flux" ? s.image_api_key || "" : "") ||
        ""
    );
  }, []);

  const refresh = useCallback(async () => {
    const s = await api.getSettings();
    applySettings(s);
    return s;
  }, [applySettings]);

  useEffect(() => {
    refresh().catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [refresh]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      // 只写 DeepSeek 文本配置 + CatsAPI Token；
      // 不改全局生图 preset（custom-book 的 Flux 只认 replicate_api_token，
      // 避免把绘本视频/书籍等其他流水线的生图配置静默覆盖成 Flux）。
      const payload: Record<string, string> = {
        text_preset: "deepseek",
        text_base_url: "https://api.deepseek.com",
        text_model: "deepseek-v4-flash",
      };
      if (deepseekKey.trim()) {
        payload.text_api_key = deepseekKey.trim();
      }
      const token = catsToken.trim();
      if (token) {
        payload.replicate_api_token = token;
      }
      if (!token && !fluxSet) {
        setErr("请填写 CatsAPI Token（cats-…）");
        setBusy(false);
        return;
      }
      const refreshed = await api.saveSettings(payload);
      applySettings(refreshed);
      setDeepseekKey("");
      setCatsToken("");
      setMsg(
        fluxConfigured(refreshed)
          ? "API Key 已保存（Flux 已配置）"
          : "已保存，但 Flux 仍显示未配置，请重试"
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={onSave}
      className={`rounded-[28px] bg-white/75 p-5 shadow-sm ${compact ? "" : "mb-8"}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl text-[var(--ink)]">API Key</h2>
          <p className="mt-1 text-xs text-[var(--ink-muted)]">
            DeepSeek 写脚本 · CatsAPI flux2Pro 生图
          </p>
        </div>
        <button
          type="button"
          className="text-xs text-[var(--accent)] underline"
          onClick={() =>
            refresh()
              .then(() => setMsg("已刷新配置状态"))
              .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
          }
        >
          刷新状态
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-xs font-semibold">
        <span
          className={`rounded-full px-3 py-1 ${
            textSet
              ? "bg-emerald-100 text-[var(--leaf)]"
              : "bg-red-50 text-red-600"
          }`}
        >
          DeepSeek：{textSet ? `已配置 ${textHint}` : "未配置"}
        </span>
        <span
          className={`rounded-full px-3 py-1 ${
            fluxSet
              ? "bg-emerald-100 text-[var(--leaf)]"
              : "bg-red-50 text-red-600"
          }`}
        >
          CatsAPI Flux：{fluxSet ? `已配置 ${fluxHint}` : "未配置"}
        </span>
      </div>

      <div className="space-y-3">
        <label className="block">
          <span className="label">DeepSeek API Key</span>
          <input
            className="input"
            type="password"
            autoComplete="off"
            placeholder={textSet ? "已保存，留空则不修改" : "sk-…"}
            value={deepseekKey}
            onChange={(e) => setDeepseekKey(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="label">CatsAPI Token（flux2Pro）</span>
          <input
            className="input"
            type="password"
            autoComplete="off"
            placeholder={fluxSet ? "已保存，留空则不修改" : "cats-…"}
            value={catsToken}
            onChange={(e) => setCatsToken(e.target.value)}
          />
        </label>
      </div>

      {err && (
        <p className="mt-3 rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>
      )}
      {msg && (
        <p className="mt-3 rounded-2xl bg-emerald-50 px-3 py-2 text-sm text-[var(--leaf)]">
          {msg}
        </p>
      )}

      <button type="submit" className="btn-secondary mt-4 w-full text-sm" disabled={busy}>
        {busy ? "保存中…" : "保存 API Key"}
      </button>
    </form>
  );
}
