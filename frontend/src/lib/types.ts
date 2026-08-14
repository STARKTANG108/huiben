export type StepName =
  | "story"
  | "script"
  | "storyboard"
  | "images"
  | "tts"
  | "bgm"
  | "video";

export type StepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface StoryParagraph {
  index: number;
  text: string;
}

export interface Story {
  title: string;
  summary: string;
  age_range: string;
  paragraphs: StoryParagraph[];
  mood: string;
  provider: string;
  cover_hook?: string;
  visual_style_en?: string;
  cover_prompt_en?: string;
  lessons?: string[];
}

export interface ScriptLine {
  index: number;
  text: string;
  estimated_sec: number;
  caption?: string;
}

export interface Script {
  lines: ScriptLine[];
  total_sec: number;
  provider: string;
}

export interface Shot {
  index: number;
  visual_prompt: string;
  narration: string;
  duration_sec: number;
  camera: string;
  mood: string;
  image_asset_id: string | null;
  characters_in_shot?: string[];
  shot_kind?: string;
  on_screen_text?: string;
}

export interface Storyboard {
  shots: Shot[];
  total_sec: number;
  provider: string;
}

export interface AssetRef {
  id: string;
  kind: string;
  filename: string;
  mime_type: string;
  url: string;
  meta: Record<string, unknown>;
}

export interface TTSResult {
  asset: AssetRef;
  duration_sec: number;
  provider: string;
}

export interface BGMResult {
  asset: AssetRef;
  duration_sec: number;
  mood: string;
  provider: string;
}

export interface VideoResult {
  asset: AssetRef;
  duration_sec: number;
  provider: string;
}

export interface StepState {
  name: StepName;
  status: StepStatus;
  error: string | null;
  updated_at: string | null;
}

export interface Project {
  id: string;
  theme: string;
  age_range: string;
  style: string;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  current_step: StepName | null;
  steps: Record<string, StepState>;
  story: Story | null;
  script: Script | null;
  storyboard: Storyboard | null;
  tts: TTSResult | null;
  bgm: BGMResult | null;
  video: VideoResult | null;
  assets: Record<string, AssetRef>;
}

export interface BookProject {
  id: string;
  book_title: string;
  theme: string;
  notes: string;
  key_lessons: string;
  target_sec: number;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  current_step: StepName | null;
  steps: Record<string, StepState>;
  story: Story | null;
  script: Script | null;
  storyboard: Storyboard | null;
  tts: TTSResult | null;
  bgm: BGMResult | null;
  video: VideoResult | null;
  assets: Record<string, AssetRef>;
  cover_asset_id?: string | null;
}

export interface LifeProject {
  id: string;
  premise: string;
  vibe: string;
  notes: string;
  story_text?: string;
  title?: string;
  target_sec: number;
  tts_voice?: string;
  bgm_track_id?: string;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  current_step: StepName | null;
  steps: Record<string, StepState>;
  story: Story | null;
  script: Script | null;
  storyboard: Storyboard | null;
  tts: TTSResult | null;
  bgm: BGMResult | null;
  video: VideoResult | null;
  assets: Record<string, AssetRef>;
  cover_asset_id?: string | null;
}

export interface LifeOptions {
  durations: { sec: number; label: string }[];
  bgm_tracks: { id: string; title: string }[];
  voices: { id: string; label: string; group?: string }[];
  defaults: {
    target_sec: number;
    tts_voice: string;
    bgm_track_id: string;
  };
}

export interface OutfitLook {
  index: number;
  day_label: string;
  title: string;
  outfit_cn: string;
  image_prompt: string;
  image_asset_id: string | null;
}

export interface OutfitAsset {
  id: string;
  kind: string;
  filename: string;
  mime_type: string;
  url: string;
  meta: Record<string, unknown>;
}

export interface OutfitProject {
  id: string;
  season: string;
  city: string;
  vibe: string;
  scene?: string;
  notes: string;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  looks: OutfitLook[];
  assets: Record<string, OutfitAsset>;
}

export interface XhsCard {
  index: number;
  hook: string;
  title: string;
  points: string[];
  footer: string;
  image_asset_id: string | null;
}

export interface XhsAsset {
  id: string;
  kind: string;
  filename: string;
  mime_type: string;
  url: string;
  meta: Record<string, unknown>;
}

export interface XhsProject {
  id: string;
  url: string;
  notes: string;
  max_cards: number;
  style: string;
  layout: string;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  source_title: string;
  source_excerpt: string;
  summary: string;
  post_title: string;
  post_body: string;
  cards: XhsCard[];
  assets: Record<string, XhsAsset>;
}

export interface CutScene {
  id: string;
  purpose: string;
  visual: string;
  caption: string;
  image_prompt: string;
  duration_sec: number;
  image_asset_id: string | null;
}

export interface CutClipSeekHit {
  id: string;
  title: string;
  provider: string;
  source_page: string | null;
  thumbnail: string | null;
  media_type: string;
}

export interface CutAsset {
  id: string;
  kind: string;
  filename: string;
  mime_type: string;
  url: string;
  meta: Record<string, unknown>;
}

export interface CutProject {
  id: string;
  brief: string;
  workflow: string;
  duration: number;
  format: string;
  notes: string;
  created_at: string;
  updated_at: string;
  job_status: JobStatus;
  job_error: string | null;
  stage: string;
  ir: Record<string, unknown>;
  scenes: CutScene[];
  clipseek: CutClipSeekHit[];
  video_asset_id: string | null;
  render_engine: string;
  doctor_hint: string;
  assets: Record<string, CutAsset>;
}

export const PIPELINE_STEPS: { id: StepName; label: string }[] = [
  { id: "story", label: "故事" },
  { id: "script", label: "脚本" },
  { id: "storyboard", label: "分镜" },
  { id: "images", label: "画面" },
  { id: "tts", label: "配音" },
  { id: "bgm", label: "配乐" },
  { id: "video", label: "成片" },
];

/** 人生副本：先配音，再按配音时长出图，最后配乐+字幕成片 */
export const LIFE_PIPELINE_STEPS: { id: StepName; label: string }[] = [
  { id: "story", label: "故事" },
  { id: "script", label: "脚本" },
  { id: "storyboard", label: "分镜" },
  { id: "tts", label: "配音" },
  { id: "images", label: "画面" },
  { id: "bgm", label: "配乐" },
  { id: "video", label: "成片" },
];

export type CustomBookStatus =
  | "draft"
  | "preparing"
  | "story_ready"
  | "character_pending"
  | "character_confirmed"
  | "pages_generating"
  | "pages_review"
  | "pdf_ready"
  | "done"
  | "failed";

export interface CustomBookOrderListItem {
  id: string;
  child_name: string;
  age: number;
  theme: string;
  status: CustomBookStatus;
  title: string;
  updated_at: string;
}

export interface CustomBookOrder {
  id: string;
  child_name: string;
  age: number;
  gender: string;
  theme: string;
  emotion_goal: string;
  parent_message: string;
  status: CustomBookStatus;
  title: string;
  story: {
    title: string;
    character_description: string;
    pages: { page: number; text: string; scene_prompt: string; emotion: string }[];
  } | null;
  character: {
    name: string;
    age: number;
    face_shape: string;
    hair: string;
    eyes: string;
    skin: string;
    special_features: string;
    clothing_style: string;
    character_prompt: string;
    status: string;
    confirmed_at: string | null;
  } | null;
  character_assets: { view_type: string; url: string; generation: number }[];
  photos: { id: string; url: string; sort_order: number; quality_score: number }[];
  pages: {
    page_no: number;
    text: string;
    scene_prompt: string;
    emotion: string;
    image_url: string | null;
    status: string;
    regen_count: number;
    version: number;
  }[];
  pdf_url: string | null;
  character_regen_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}
