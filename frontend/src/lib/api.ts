import type {
  BookProject,
  Project,
  StepName,
  StoryParagraph,
} from "./types";

// 同源部署：不配置 NEXT_PUBLIC_API_BASE 时，请求走 Next.js rewrites 代理到后端
// （见 next.config.ts 的 /api/:path* → BACKEND_UPSTREAM），本地开发仍可显式指定。
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function assetUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export type RuntimeSettings = {
  text_preset: string;
  text_base_url: string;
  text_api_key: string;
  text_api_key_set?: boolean;
  text_model: string;
  image_preset: string;
  image_base_url: string;
  image_api_key: string;
  image_api_key_set?: boolean;
  image_model: string;
  tts_preset: string;
  tts_base_url: string;
  tts_api_key: string;
  tts_api_key_set?: boolean;
  tts_model: string;
  tts_voice: string;
  book_tts_voice?: string;
  minimax_api_key?: string;
  minimax_api_key_set?: boolean;
  toapis_api_key?: string;
  toapis_api_key_set?: boolean;
  minimax_voices?: { id: string; label: string; group?: string }[];
  presets: {
    text: Record<string, { label: string; base_url: string; model: string; hint: string }>;
    image: Record<string, { label: string; base_url: string; model: string; hint: string }>;
    tts: Record<string, { label: string; base_url: string; model: string; hint: string }>;
  };
};

export const api = {
  // ---- 儿童绘本视频 ----
  createProject(data: {
    theme: string;
    age_range: string;
    style: string;
  }): Promise<Project> {
    return request("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getProject(id: string): Promise<Project> {
    return request(`/api/projects/${id}`);
  },

  updateStory(
    id: string,
    data: {
      title?: string;
      summary?: string;
      paragraphs?: StoryParagraph[];
    }
  ): Promise<Project> {
    return request(`/api/projects/${id}/story`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  runStep(id: string, step: StepName): Promise<Project> {
    return request(`/api/projects/${id}/steps/${step}`, { method: "POST" });
  },

  runPipeline(id: string, from_step?: StepName): Promise<Project> {
    return request(`/api/projects/${id}/run`, {
      method: "POST",
      body: JSON.stringify(from_step ? { from_step } : {}),
    });
  },

  // ---- 书籍剪辑 ----
  createBook(data: {
    book_title: string;
    theme?: string;
    notes?: string;
    key_lessons?: string;
  }): Promise<BookProject> {
    return request("/api/book", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getBook(id: string): Promise<BookProject> {
    return request(`/api/book/${id}`);
  },

  runBookStep(id: string, step: StepName): Promise<BookProject> {
    return request(`/api/book/${id}/steps/${step}`, { method: "POST" });
  },

  runBookPipeline(id: string, from_step?: StepName): Promise<BookProject> {
    return request(`/api/book/${id}/run`, {
      method: "POST",
      body: JSON.stringify(from_step ? { from_step } : {}),
    });
  },

  // ---- 模型配置 ----
  getSettings(): Promise<RuntimeSettings> {
    return request("/api/settings");
  },

  saveSettings(data: Record<string, string>): Promise<RuntimeSettings> {
    return request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
};
