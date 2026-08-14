import Link from "next/link";

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="absolute right-4 top-4 z-10 sm:right-8 sm:top-8">
        <Link href="/settings" className="btn-secondary text-sm">
          模型配置
        </Link>
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] opacity-90"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23e07a4b' fill-opacity='0.06'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        }}
      />
      <div className="relative mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-4 py-16">
        <header className="mb-12 text-center">
          <p className="font-display text-5xl tracking-tight text-[var(--ink)] sm:text-6xl">
            Pictale
          </p>
          <p className="mt-4 text-lg text-[var(--ink-muted)]">选择一个创作板块</p>
        </header>

        <div className="grid gap-5 sm:grid-cols-2">
          <Link
            href="/creative"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white sm:col-span-2"
          >
            <p className="font-display text-2xl text-[var(--ink)]">
              AI Creative Director
              <span className="ml-3 rounded-full bg-[var(--sand)] px-2.5 py-0.5 align-middle text-xs font-semibold text-[var(--ink-muted)]">
                开发中
              </span>
            </p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              Upload a product photo → cinematic ad concepts, storyboards &amp;
              spots
            </p>
          </Link>
          <Link
            href="/custom-book"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white sm:col-span-2"
          >
            <p className="font-display text-2xl text-[var(--ink)]">儿童定制绘本</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              半自动生产后台 · 角色确认 · Flux 8 页绘本 · PDF
            </p>
          </Link>
          <Link
            href="/pictale"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white"
          >
            <p className="font-display text-2xl text-[var(--ink)]">儿童绘本视频</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              主题 → 故事 → 分镜 → 配音配乐 → 约一分钟成片
            </p>
          </Link>
          <Link
            href="/life"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white"
          >
            <p className="font-display text-2xl text-[var(--ink)]">人生副本</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              《1000种人生》· 假如另一条路 · 约 30 秒试用
            </p>
          </Link>
          <Link
            href="/book"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white"
          >
            <p className="font-display text-2xl text-[var(--ink)]">书籍剪辑</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              《一生》式讲故事 → 首尾帧开场动效 → MiniMax 配音 → 约 3 分钟
            </p>
          </Link>
          <Link
            href="/cut"
            className="rounded-[28px] bg-white/75 p-8 shadow-sm transition hover:bg-white"
          >
            <p className="font-display text-2xl text-[var(--ink)]">混剪视频</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">
              一句话 brief → 分镜静帧 → 预览成片
            </p>
          </Link>
        </div>
      </div>
    </main>
  );
}
