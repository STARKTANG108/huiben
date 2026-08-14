-- AI Creative Director — initial schema
-- Run this in Supabase Dashboard → SQL Editor (or via supabase CLI).
--
-- Storage buckets (create manually in Dashboard → Storage):
--   product-images  — uploaded product photos
--   shot-images     — generated storyboard frames
--   ad-videos       — Remotion / final MP4 outputs
-- Phase 1 intentionally does NOT insert into storage.buckets (avoids permission failures).

-- ---------------------------------------------------------------------------
-- users (MVP placeholder; can later map to auth.users)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.users IS 'App users for Creative Director. Align with Supabase Auth later if needed.';

-- ---------------------------------------------------------------------------
-- projects
-- status: draft | analyzing | concepts | storyboard | generating | ready | failed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.users (id) ON DELETE SET NULL,
  product_name TEXT NOT NULL,
  product_category TEXT,
  style TEXT,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN (
      'draft',
      'analyzing',
      'concepts',
      'storyboard',
      'generating',
      'ready',
      'failed'
    )),
  product_image_url TEXT,
  analysis_json JSONB,
  concepts_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS projects_user_id_idx ON public.projects (user_id);
CREATE INDEX IF NOT EXISTS projects_status_idx ON public.projects (status);
CREATE INDEX IF NOT EXISTS projects_created_at_idx ON public.projects (created_at DESC);

COMMENT ON COLUMN public.projects.status IS 'draft | analyzing | concepts | storyboard | generating | ready | failed';
COMMENT ON COLUMN public.projects.analysis_json IS 'Output of product analysis agent';
COMMENT ON COLUMN public.projects.concepts_json IS 'Array of ad concept proposals';

-- ---------------------------------------------------------------------------
-- shots (fixed 4 shots per project in product flow; schema allows flexibility)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.shots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES public.projects (id) ON DELETE CASCADE,
  shot_number INTEGER NOT NULL CHECK (shot_number >= 1),
  duration INTEGER NOT NULL DEFAULT 8 CHECK (duration > 0),
  scene TEXT,
  camera TEXT,
  script TEXT,
  image_prompt TEXT,
  image_url TEXT,
  video_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, shot_number)
);

CREATE INDEX IF NOT EXISTS shots_project_id_idx ON public.shots (project_id);

COMMENT ON COLUMN public.shots.script IS 'Voice-over / on-screen advertising copy';
COMMENT ON COLUMN public.shots.image_prompt IS 'Prompt used to generate the shot still';

-- ---------------------------------------------------------------------------
-- assets (generic media references for a project)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES public.projects (id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  url TEXT NOT NULL,
  meta_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS assets_project_id_idx ON public.assets (project_id);
CREATE INDEX IF NOT EXISTS assets_type_idx ON public.assets (type);

COMMENT ON COLUMN public.assets.type IS 'product_image | shot_image | shot_video | final_video | other';

-- ---------------------------------------------------------------------------
-- Optional: enable RLS later when Auth is wired. Left open for local MVP.
-- ---------------------------------------------------------------------------
-- ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.shots ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
