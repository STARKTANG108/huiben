import Link from "next/link";

/**
 * Phase 2 placeholder — create-project form lands here next.
 */
export default function CreativeNewPlaceholderPage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,#1a2230_0%,#0a0c10_70%)]"
      />
      <div className="relative z-10 max-w-md">
        <p className="font-creative-display text-3xl text-[var(--cd-ink)] sm:text-4xl">
          Create Advertisement
        </p>
        <p className="mt-4 text-sm leading-relaxed text-[var(--cd-muted)] sm:text-base">
          该创作板块正在开发中（Phase 2），敬请期待。
          <br className="hidden sm:block" />
          Project creation (product upload, style, category) ships in Phase 2.
        </p>
        <Link
          href="/creative"
          className="mt-8 inline-flex text-sm tracking-wide text-[var(--cd-accent)] transition hover:text-[var(--cd-ink)]"
        >
          ← Back to AI Creative Director
        </Link>
      </div>
    </main>
  );
}
