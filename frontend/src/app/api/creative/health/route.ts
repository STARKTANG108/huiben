import { NextResponse } from "next/server";
import { isSupabaseConfigured } from "@/lib/supabase/env";

/**
 * Lightweight health check for Creative Director env wiring.
 * Does not query tables (safe when Supabase project is not yet provisioned).
 */
export async function GET() {
  const configured = isSupabaseConfigured();

  return NextResponse.json({
    ok: true,
    product: "ai-creative-director",
    supabase: {
      configured,
      hasServiceRole: Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY),
    },
  });
}
