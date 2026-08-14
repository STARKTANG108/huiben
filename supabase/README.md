# AI Creative Director — Supabase

## Setup

1. Create a project at [supabase.com](https://supabase.com).
2. Copy URL + anon key + service role key into `frontend/.env.local` (see `frontend/.env.local.example`).
3. Open **SQL Editor** and run [`migrations/001_init_creative_director.sql`](migrations/001_init_creative_director.sql).
4. In **Storage**, create public (or private + signed URL) buckets:
   - `product-images`
   - `shot-images`
   - `ad-videos`

## Health check

With the Next.js app running:

```bash
curl http://localhost:3000/api/creative/health
```

Expect `"supabase": { "configured": true }` when env vars are set.
