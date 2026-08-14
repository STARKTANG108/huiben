import Link from "next/link";
import { HomeForm } from "@/components/HomeForm";

export default function PictalePage() {
  return (
    <main className="relative overflow-hidden">
      <div className="absolute right-4 top-4 z-10 flex gap-2 sm:right-8 sm:top-8">
        <Link href="/" className="btn-secondary text-sm">
          首页
        </Link>
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
            绘本视频
          </p>
          <p className="mt-4 text-lg text-[var(--ink-muted)] sm:text-xl">
            输入主题，一键做出一分钟绘本视频
          </p>
        </header>
        <HomeForm />
      </div>
    </main>
  );
}
