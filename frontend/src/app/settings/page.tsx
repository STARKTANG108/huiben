"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type RuntimeSettings } from "@/lib/api";

type FormState = {
  text_preset: string;
  text_base_url: string;
  text_api_key: string;
  text_model: string;
  image_preset: string;
  image_base_url: string;
  image_api_key: string;
  image_model: string;
  tts_preset: string;
  tts_base_url: string;
  tts_api_key: string;
  tts_model: string;
  tts_voice: string;
  book_tts_voice: string;
  minimax_api_key: string;
  toapis_api_key: string;
};

const EMPTY: FormState = {
  text_preset: "mock",
  text_base_url: "",
  text_api_key: "",
  text_model: "",
  image_preset: "minimax",
  image_base_url: "",
  image_api_key: "",
  image_model: "",
  tts_preset: "minimax",
  tts_base_url: "",
  tts_api_key: "",
  tts_model: "",
  tts_voice: "Chinese (Mandarin)_Warm_Girl",
  book_tts_voice: "Chinese (Mandarin)_Male_Announcer",
  minimax_api_key: "",
  toapis_api_key: "",
};

const FALLBACK_MINIMAX_VOICES = [
  { id: "Chinese (Mandarin)_Male_Announcer", label: "播报男声（说书推荐）", group: "说书男声" },
  { id: "Chinese (Mandarin)_Radio_Host", label: "电台男主播", group: "说书男声" },
  { id: "Chinese (Mandarin)_Gentleman", label: "温润男声", group: "说书男声" },
  { id: "Chinese (Mandarin)_Lyrical_Voice", label: "抒情男声", group: "说书男声" },
  { id: "male-qn-jingying", label: "精英青年", group: "说书男声" },
  { id: "male-qn-qingse", label: "青涩青年", group: "说书男声" },
  { id: "male-qn-badao", label: "霸道青年", group: "说书男声" },
  { id: "male-qn-daxuesheng", label: "青年大学生", group: "说书男声" },
  { id: "Chinese (Mandarin)_Warm_Girl", label: "温暖少女（绘本推荐）", group: "女声" },
  { id: "Chinese (Mandarin)_Sweet_Lady", label: "甜美女声", group: "女声" },
  { id: "Chinese (Mandarin)_Gentle_Senior", label: "温柔学姐", group: "女声" },
  { id: "female-yujie", label: "御姐", group: "女声" },
  { id: "female-tianmei", label: "甜美", group: "女声" },
  { id: "female-shaonv", label: "少女", group: "女声" },
];

const FALLBACK_PRESETS: RuntimeSettings["presets"] = {
  text: {
    mock: {
      label: "本地演示（无需 Key）",
      base_url: "",
      model: "",
      hint: "不调用外部模型，用模板故事",
    },
    deepseek: {
      label: "DeepSeek",
      base_url: "https://api.deepseek.com",
      model: "deepseek-v4-flash",
      hint: "故事 / 脚本 / 分镜 · platform.deepseek.com 申请 Key",
    },
    gemini: {
      label: "Google Gemini（免费额度）",
      base_url: "https://generativelanguage.googleapis.com/v1beta/openai/",
      model: "gemini-2.0-flash",
      hint: "到 Google AI Studio 免费申请 API Key",
    },
    groq: {
      label: "Groq（免费额度）",
      base_url: "https://api.groq.com/openai/v1",
      model: "llama-3.3-70b-versatile",
      hint: "到 console.groq.com 免费申请 API Key",
    },
    custom: {
      label: "自定义（填 URL + Key）",
      base_url: "https://api.openai.com/v1",
      model: "gpt-4o-mini",
      hint: "任意 OpenAI 兼容接口（硅基流动 / 通义等）",
    },
  },
  image: {
    mock: {
      label: "本地占位图",
      base_url: "",
      model: "",
      hint: "彩色占位图，不花钱",
    },
    minimax: {
      label: "MiniMax 生图（绘本）",
      base_url: "https://api.minimaxi.com",
      model: "image-01",
      hint: "绘本画面 · platform.minimaxi.com · 填下方 MiniMax Key",
    },
    pollinations: {
      label: "Pollinations（免费生图）",
      base_url: "https://image.pollinations.ai",
      model: "flux",
      hint: "无需 Key，联网即可生成",
    },
    custom: {
      label: "自定义生图 API（suxi 等）",
      base_url: "https://new.suxi.ai/v1",
      model: "jimeng-3.0",
      hint: "OpenAI Images 兼容接口",
    },
  },
  tts: {
    mock: {
      label: "本地蜂鸣占位",
      base_url: "",
      model: "",
      hint: "测试用，不是人声",
    },
    minimax: {
      label: "MiniMax 配音（绘本）",
      base_url: "https://api.minimaxi.com",
      model: "speech-2.8-hd",
      hint: "绘本旁白 · 与生图共用 MiniMax Key",
    },
    edge: {
      label: "Edge TTS（免费真人声）",
      base_url: "",
      model: "",
      hint: "微软 Edge 语音，无需 Key",
    },
    custom: {
      label: "自定义 TTS API",
      base_url: "https://api.openai.com/v1",
      model: "tts-1",
      hint: "OpenAI TTS 兼容接口，需填 Key",
    },
  },
};

export default function SettingsPage() {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [presets, setPresets] = useState<RuntimeSettings["presets"] | null>(
    FALLBACK_PRESETS
  );
  const [minimaxVoices, setMinimaxVoices] = useState<
    { id: string; label: string; group?: string }[]
  >(FALLBACK_MINIMAX_VOICES);
  const [keySet, setKeySet] = useState({
    text: false,
    image: false,
    tts: false,
    minimax: false,
    toapis: false,
  });
  const [keyHint, setKeyHint] = useState({
    text: "",
    image: "",
    tts: "",
    minimax: "",
    toapis: "",
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setPresets(s.presets);
        if (s.minimax_voices?.length) {
          setMinimaxVoices(s.minimax_voices);
        }
        setKeySet({
          text: !!s.text_api_key_set,
          image: !!s.image_api_key_set,
          tts: !!s.tts_api_key_set,
          minimax: !!s.minimax_api_key_set,
          toapis: !!s.toapis_api_key_set,
        });
        setKeyHint({
          text: s.text_api_key || "",
          image: s.image_api_key || "",
          tts: s.tts_api_key || "",
          minimax: s.minimax_api_key || "",
          toapis: s.toapis_api_key || "",
        });
        setForm({
          text_preset: s.text_preset,
          text_base_url: s.text_base_url,
          text_api_key: "",
          text_model: s.text_model,
          image_preset: s.image_preset,
          image_base_url: s.image_base_url,
          image_api_key: "",
          image_model: s.image_model,
          tts_preset: s.tts_preset,
          tts_base_url: s.tts_base_url,
          tts_api_key: "",
          tts_model: s.tts_model,
          tts_voice: s.tts_voice || "Chinese (Mandarin)_Warm_Girl",
          book_tts_voice:
            s.book_tts_voice || "Chinese (Mandarin)_Male_Announcer",
          minimax_api_key: "",
          toapis_api_key: "",
        });
      })
      .catch((e) => {
        setPresets((p) => p || FALLBACK_PRESETS);
        setErr(
          `${String(e.message || e)}（后端未响应时选项仍可显示；Key 状态需后端恢复后刷新）`
        );
      });
  }, []);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function applyTextPreset(id: string) {
    const p = presets?.text[id];
    setForm((f) => ({
      ...f,
      text_preset: id,
      text_base_url: p?.base_url ?? f.text_base_url,
      text_model: p?.model ?? f.text_model,
    }));
  }

  function applyImagePreset(id: string) {
    const p = presets?.image[id];
    setForm((f) => ({
      ...f,
      image_preset: id,
      image_base_url: p?.base_url ?? f.image_base_url,
      image_model: p?.model ?? f.image_model,
    }));
  }

  function applyTtsPreset(id: string) {
    const p = presets?.tts[id];
    setForm((f) => ({
      ...f,
      tts_preset: id,
      tts_base_url: p?.base_url ?? f.tts_base_url,
      tts_model: p?.model ?? f.tts_model,
      tts_voice:
        id === "minimax"
          ? "Chinese (Mandarin)_Warm_Girl"
          : id === "edge"
            ? "zh-CN-XiaoxiaoNeural"
            : f.tts_voice,
    }));
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const payload: Record<string, string> = { ...form };
      // Don't overwrite keys with empty unless user typed something
      if (!payload.text_api_key) delete payload.text_api_key;
      if (!payload.image_api_key) delete payload.image_api_key;
      if (!payload.tts_api_key) delete payload.tts_api_key;
      if (!payload.minimax_api_key) delete payload.minimax_api_key;
      if (!payload.toapis_api_key) delete payload.toapis_api_key;
      await api.saveSettings(payload);
      const refreshed = await api.getSettings();
      setKeySet({
        text: !!refreshed.text_api_key_set,
        image: !!refreshed.image_api_key_set,
        tts: !!refreshed.tts_api_key_set,
        minimax: !!refreshed.minimax_api_key_set,
        toapis: !!refreshed.toapis_api_key_set,
      });
      setKeyHint({
        text: refreshed.text_api_key || "",
        image: refreshed.image_api_key || "",
        tts: refreshed.tts_api_key || "",
        minimax: refreshed.minimax_api_key || "",
        toapis: refreshed.toapis_api_key || "",
      });
      setMsg("已保存。返回首页即可开始制作。");
      setForm((f) => ({
        ...f,
        text_api_key: "",
        image_api_key: "",
        tts_api_key: "",
        minimax_api_key: "",
        toapis_api_key: "",
        image_preset: refreshed.image_preset,
        image_base_url: refreshed.image_base_url,
        image_model: refreshed.image_model,
        tts_preset: refreshed.tts_preset,
        tts_base_url: refreshed.tts_base_url,
        tts_model: refreshed.tts_model,
        tts_voice: refreshed.tts_voice,
        book_tts_voice:
          refreshed.book_tts_voice || "Chinese (Mandarin)_Male_Announcer",
      }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl text-[var(--ink)]">模型配置</h1>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            文本用 DeepSeek；生图 / 配音 / 书籍配乐用 MiniMax；开场视频用 ToAPIs veo3.1-fast。
          </p>
        </div>
        <Link href="/" className="btn-secondary text-sm">
          返回首页
        </Link>
      </div>

      <form onSubmit={onSave} className="space-y-8">
        {/* Text */}
        <section className="rounded-[24px] bg-white/70 p-6 shadow-sm">
          <h2 className="font-display text-xl text-[var(--ink)]">1. 写故事（文本）</h2>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            故事 / 脚本 / 分镜共用这一套
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {presets &&
              Object.entries(presets.text).map(([id, p]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => applyTextPreset(id)}
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    form.text_preset === id
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--sand)] text-[var(--ink)]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
          </div>
          {presets?.text[form.text_preset]?.hint && (
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              {presets.text[form.text_preset].hint}
            </p>
          )}
          {(form.text_preset === "gemini" ||
            form.text_preset === "groq" ||
            form.text_preset === "deepseek" ||
            form.text_preset === "custom") && (
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="label">
                  DeepSeek / 文本 API Key
                  {keySet.text ? (
                    <span className="ml-2 font-normal text-[var(--leaf)]">
                      已保存 {keyHint.text}
                    </span>
                  ) : (
                    <span className="ml-2 font-normal text-red-500">未配置</span>
                  )}
                </span>
                <input
                  className="input"
                  type="password"
                  placeholder="只填文本模型的 Key，不要填生图 Key"
                  value={form.text_api_key}
                  onChange={(e) => setField("text_api_key", e.target.value)}
                  autoComplete="off"
                />
              </label>
              {(form.text_preset === "custom" ||
                form.text_preset === "gemini" ||
                form.text_preset === "groq" ||
                form.text_preset === "deepseek") && (
                <>
                  <label className="block">
                    <span className="label">Base URL</span>
                    <input
                      className="input"
                      value={form.text_base_url}
                      onChange={(e) => setField("text_base_url", e.target.value)}
                      placeholder="https://..."
                    />
                  </label>
                  <label className="block">
                    <span className="label">模型名</span>
                    <input
                      className="input"
                      value={form.text_model}
                      onChange={(e) => setField("text_model", e.target.value)}
                    />
                  </label>
                </>
              )}
            </div>
          )}
        </section>

        {/* Image */}
        <section className="rounded-[24px] bg-white/70 p-6 shadow-sm">
          <h2 className="font-display text-xl text-[var(--ink)]">2. 画画面（生图）</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {presets &&
              Object.entries(presets.image).map(([id, p]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => applyImagePreset(id)}
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    form.image_preset === id
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--sand)] text-[var(--ink)]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
          </div>
          {presets?.image[form.image_preset]?.hint && (
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              {presets.image[form.image_preset].hint}
            </p>
          )}
          <label className="mt-4 block">
              <span className="label">
                MiniMax API Key（绘本 / 书籍生图 + 配音 + 配乐 + 开场视频）
                {keySet.minimax ? (
                  <span className="ml-2 font-normal text-[var(--leaf)]">
                    已保存 {keyHint.minimax}
                  </span>
                ) : (
                  <span className="ml-2 font-normal text-red-500">未配置</span>
                )}
              </span>
              <input
                className="input"
                type="password"
                placeholder="platform.minimaxi.com 的 API Key"
                value={form.minimax_api_key}
                onChange={(e) => setField("minimax_api_key", e.target.value)}
                autoComplete="off"
              />
            </label>
          <label className="mt-4 block">
              <span className="label">
                ToAPIs API Key（书籍开场视频 veo3.1-fast）
                {keySet.toapis ? (
                  <span className="ml-2 font-normal text-[var(--leaf)]">
                    已保存 {keyHint.toapis}
                  </span>
                ) : (
                  <span className="ml-2 font-normal text-red-500">未配置</span>
                )}
              </span>
              <input
                className="input"
                type="password"
                placeholder="toapis.com 的 API Key（sk-…）"
                value={form.toapis_api_key}
                onChange={(e) => setField("toapis_api_key", e.target.value)}
                autoComplete="off"
              />
            </label>
          {form.image_preset === "custom" && (
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="label">Base URL</span>
                <input
                  className="input"
                  value={form.image_base_url}
                  onChange={(e) => setField("image_base_url", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="label">
                  suxi / 生图 API Key
                  {keySet.image ? (
                    <span className="ml-2 font-normal text-[var(--leaf)]">
                      已保存 {keyHint.image}
                    </span>
                  ) : (
                    <span className="ml-2 font-normal text-red-500">未配置</span>
                  )}
                </span>
                <input
                  className="input"
                  type="password"
                  placeholder="备用；自定义生图 API Key"
                  value={form.image_api_key}
                  onChange={(e) => setField("image_api_key", e.target.value)}
                  autoComplete="off"
                />
              </label>
              <label className="block">
                <span className="label">模型名</span>
                <input
                  className="input"
                  value={form.image_model}
                  onChange={(e) => setField("image_model", e.target.value)}
                />
              </label>
            </div>
          )}
        </section>

        {/* TTS */}
        <section className="rounded-[24px] bg-white/70 p-6 shadow-sm">
          <h2 className="font-display text-xl text-[var(--ink)]">3. 配音</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {presets &&
              Object.entries(presets.tts).map(([id, p]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => applyTtsPreset(id)}
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    form.tts_preset === id
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--sand)] text-[var(--ink)]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
          </div>
          {presets?.tts[form.tts_preset]?.hint && (
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              {presets.tts[form.tts_preset].hint}
            </p>
          )}
          {form.tts_preset === "minimax" && (
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="label">绘本音色</span>
                <select
                  className="input"
                  value={form.tts_voice}
                  onChange={(e) => setField("tts_voice", e.target.value)}
                >
                  {(["说书男声", "女声"] as const).map((group) => (
                    <optgroup key={group} label={group}>
                      {minimaxVoices
                        .filter((v) => (v.group || "女声") === group)
                        .map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.label}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="label">书籍说书音色</span>
                <select
                  className="input"
                  value={form.book_tts_voice}
                  onChange={(e) => setField("book_tts_voice", e.target.value)}
                >
                  {(["说书男声", "女声"] as const).map((group) => (
                    <optgroup key={group} label={group}>
                      {minimaxVoices
                        .filter((v) => (v.group || "女声") === group)
                        .map((v) => (
                          <option key={`book-${v.id}`} value={v.id}>
                            {v.label}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
                <p className="mt-1 text-xs text-[var(--ink-muted)]">
                  说书推荐：播报男声 / 电台男主播 / 温润男声 / 抒情男声 / 精英青年
                </p>
              </label>
            </div>
          )}
          {form.tts_preset === "edge" && (
            <label className="mt-4 block">
              <span className="label">音色</span>
              <select
                className="input"
                value={form.tts_voice}
                onChange={(e) => setField("tts_voice", e.target.value)}
              >
                <option value="zh-CN-XiaoxiaoNeural">晓晓（女声，温柔）</option>
                <option value="zh-CN-YunxiNeural">云希（男声）</option>
                <option value="zh-CN-XiaoyiNeural">晓伊（女声）</option>
              </select>
            </label>
          )}
          {form.tts_preset === "custom" && (
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="label">Base URL</span>
                <input
                  className="input"
                  value={form.tts_base_url}
                  onChange={(e) => setField("tts_base_url", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="label">API Key</span>
                <input
                  className="input"
                  type="password"
                  value={form.tts_api_key}
                  onChange={(e) => setField("tts_api_key", e.target.value)}
                  autoComplete="off"
                />
              </label>
              <label className="block">
                <span className="label">模型名</span>
                <input
                  className="input"
                  value={form.tts_model}
                  onChange={(e) => setField("tts_model", e.target.value)}
                />
              </label>
            </div>
          )}
        </section>

        {msg && (
          <p className="rounded-xl bg-green-50 px-4 py-3 text-sm text-green-800">{msg}</p>
        )}
        {err && (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{err}</p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full py-3">
          {busy ? "保存中…" : "保存配置"}
        </button>
      </form>
    </main>
  );
}
