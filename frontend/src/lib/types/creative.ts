/**
 * Domain types for AI Creative Director.
 * Aligns with supabase/migrations/001_init_creative_director.sql
 */

/** Pipeline status for a creative project. */
export type ProjectStatus =
  | "draft"
  | "analyzing"
  | "concepts"
  | "storyboard"
  | "generating"
  | "ready"
  | "failed";

/** Ad style presets (Phase 2 form). */
export type AdStyle =
  | "apple_minimal"
  | "luxury"
  | "ecommerce_viral"
  | "lifestyle";

export interface CreativeUser {
  id: string;
  email: string | null;
  created_at: string;
}

export interface CreativeProject {
  id: string;
  user_id: string | null;
  product_name: string;
  product_category: string | null;
  style: AdStyle | string | null;
  status: ProjectStatus;
  product_image_url: string | null;
  analysis_json: Record<string, unknown> | null;
  concepts_json: unknown[] | null;
  created_at: string;
}

export interface CreativeShot {
  id: string;
  project_id: string;
  shot_number: number;
  duration: number;
  scene: string | null;
  camera: string | null;
  /** Voice-over / on-screen copy */
  script: string | null;
  image_prompt: string | null;
  image_url: string | null;
  video_url: string | null;
  created_at: string;
}

export type AssetType =
  | "product_image"
  | "shot_image"
  | "shot_video"
  | "final_video"
  | "other";

export interface CreativeAsset {
  id: string;
  project_id: string;
  type: AssetType | string;
  url: string;
  meta_json: Record<string, unknown> | null;
  created_at: string;
}
