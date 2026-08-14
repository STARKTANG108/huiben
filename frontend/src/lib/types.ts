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

export const PIPELINE_STEPS: { id: StepName; label: string }[] = [
  { id: "story", label: "故事" },
  { id: "script", label: "脚本" },
  { id: "storyboard", label: "分镜" },
  { id: "images", label: "画面" },
  { id: "tts", label: "配音" },
  { id: "bgm", label: "配乐" },
  { id: "video", label: "成片" },
];
