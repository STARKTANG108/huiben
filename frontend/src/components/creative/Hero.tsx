import Link from "next/link";
import { ArrowRight } from "lucide-react";

/**
 * Full-viewport hero for AI Creative Director.
 * One composition: brand → headline → support → CTA over cinematic backdrop.
 */
export function CreativeHero() {
  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      {/* Atmospheric backdrop — charcoal + warm gold wash (not purple / cream) */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_90%_70%_at_70%_20%,#1a2230_0%,transparent_55%),radial-gradient(ellipse_60%_50%_at_15%_80%,#2a2218_0%,transparent_50%),linear-gradient(165deg,#080a0e_0%,#0e1218_45%,#0a0c10_100%)]" />
        <div className="cd-glow absolute -left-[10%] top-[10%] h-[55vh] w-[55vw] rounded-full bg-[radial-gradient(circle,rgba(196,165,116,0.22)_0%,transparent_68%)] blur-3xl" />
        <div className="absolute bottom-0 right-0 h-[45vh] w-[50vw] bg-[radial-gradient(ellipse_at_bottom_right,rgba(90,110,130,0.25)_0%,transparent_60%)]" />
        <div
          className="cd-grain absolute inset-[-20%] opacity-[0.07] mix-blend-overlay"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
          }}
        />
        <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/50 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/60 to-transparent" />
      </div>

      <header className="relative z-10 flex items-center justify-between px-5 py-5 sm:px-10">
        <Link
          href="/"
          className="text-xs tracking-[0.18em] text-[var(--cd-muted)] transition hover:text-[var(--cd-ink)]"
        >
          PICTALE
        </Link>
        <span className="text-xs tracking-[0.2em] text-[var(--cd-accent)]">
          MVP
        </span>
      </header>

      <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center px-5 pb-20 pt-8 sm:px-10">
        <p className="cd-animate-fade-up font-creative-display text-4xl leading-none tracking-tight text-[var(--cd-ink)] sm:text-6xl md:text-7xl">
          AI Creative Director
        </p>

        <h1 className="cd-animate-fade-up-delay-1 mt-8 max-w-2xl text-xl font-medium leading-snug text-[var(--cd-ink)] sm:text-2xl md:text-3xl">
          Upload your product, create cinematic ads with AI
        </h1>

        <p className="cd-animate-fade-up-delay-2 mt-5 max-w-md text-sm leading-relaxed text-[var(--cd-muted)] sm:text-base">
          From a single product photo to concepts, storyboards, and a finished
          spot — directed automatically.
        </p>

        <div className="cd-animate-fade-up-delay-3 mt-10">
          <Link
            href="/creative/new"
            className="group inline-flex h-12 items-center justify-center gap-2 rounded-md bg-[var(--cd-ink)] px-7 text-base font-medium text-[var(--cd-bg)] transition hover:bg-white"
          >
            Create Advertisement
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
