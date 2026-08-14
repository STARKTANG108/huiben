import type {
  BookProject,
  CutProject,
  CustomBookOrder,
  CustomBookOrderListItem,
  LifeOptions,
  LifeProject,
  OutfitProject,
  Project,
  StepName,
  StoryParagraph,
  XhsProject,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8000";

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
  replicate_api_token?: string;
  replicate_api_token_set?: boolean;
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

  getSettings(): Promise<RuntimeSettings> {
    return request("/api/settings");
  },

  saveSettings(data: Record<string, string>): Promise<RuntimeSettings> {
    return request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  createOutfit(data: {
    season: string;
    city: string;
    vibe: string;
    scene?: string;
    notes?: string;
  }): Promise<OutfitProject> {
    return request("/api/outfits", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getOutfit(id: string): Promise<OutfitProject> {
    return request(`/api/outfits/${id}`);
  },

  createXhs(data: {
    url: string;
    notes?: string;
    max_cards?: number;
    style?: string;
    layout?: string;
  }): Promise<XhsProject> {
    return request("/api/xhs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getXhs(id: string): Promise<XhsProject> {
    return request(`/api/xhs/${id}`);
  },

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

  createLife(data: {
    premise?: string;
    vibe?: string;
    notes?: string;
    title?: string;
    story_text?: string;
    target_sec?: number;
    tts_voice?: string;
    bgm_track_id?: string;
  }): Promise<LifeProject> {
    return request("/api/life", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getLifeOptions(): Promise<LifeOptions> {
    return request("/api/life/options");
  },

  getLife(id: string): Promise<LifeProject> {
    return request(`/api/life/${id}`);
  },

  runLifeStep(id: string, step: StepName): Promise<LifeProject> {
    return request(`/api/life/${id}/steps/${step}`, { method: "POST" });
  },

  runLifePipeline(id: string, from_step?: StepName): Promise<LifeProject> {
    return request(`/api/life/${id}/run`, {
      method: "POST",
      body: JSON.stringify(from_step ? { from_step } : {}),
    });
  },

  createCut(data: {
    brief: string;
    workflow?: string;
    duration?: number;
    format?: string;
    notes?: string;
  }): Promise<CutProject> {
    return request("/api/cut", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getCut(id: string): Promise<CutProject> {
    return request(`/api/cut/${id}`);
  },

  listCustomBooks(): Promise<CustomBookOrderListItem[]> {
    return request("/api/custom-book/orders");
  },

  getCustomBook(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}`);
  },

  async createCustomBook(form: FormData): Promise<CustomBookOrder> {
    const res = await fetch(`${API_BASE}/api/custom-book/orders`, {
      method: "POST",
      body: form,
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
    return res.json() as Promise<CustomBookOrder>;
  },

  prepareCustomBook(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/prepare`, { method: "POST" });
  },

  regenerateCustomBookCharacter(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/character/regenerate`, {
      method: "POST",
    });
  },

  confirmCustomBookCharacter(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/character/confirm`, {
      method: "POST",
    });
  },

  updateCustomBookCharacterPrompt(
    id: string,
    character_prompt: string
  ): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/character/prompt`, {
      method: "PATCH",
      body: JSON.stringify({ character_prompt }),
    });
  },

  generateCustomBookPages(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/pages/generate`, {
      method: "POST",
    });
  },

  regenerateCustomBookPage(id: string, pageNo: number): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/pages/${pageNo}/regenerate`, {
      method: "POST",
    });
  },

  updateCustomBookPageText(
    id: string,
    pageNo: number,
    text: string
  ): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/pages/${pageNo}/text`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    });
  },

  updateCustomBookParentMessage(
    id: string,
    parent_message: string
  ): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/parent-message`, {
      method: "PATCH",
      body: JSON.stringify({ parent_message }),
    });
  },

  createCustomBookPdf(id: string): Promise<CustomBookOrder> {
    return request(`/api/custom-book/orders/${id}/pdf`, { method: "POST" });
  },
};
