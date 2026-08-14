"use client";

import { PIPELINE_STEPS, type Project, type StepName } from "@/lib/types";

interface StepNavProps {
  project: Project;
  active: StepName;
  onSelect: (step: StepName) => void;
}

export function StepNav({ project, active, onSelect }: StepNavProps) {
  return (
    <nav className="flex flex-col gap-1">
      {PIPELINE_STEPS.map((s, i) => {
        const state = project.steps[s.id];
        const status = state?.status ?? "pending";
        const isActive = active === s.id;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            className={`group flex items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${
              isActive
                ? "bg-[var(--ink)] text-[var(--cream)] shadow-md"
                : "bg-white/50 text-[var(--ink)] hover:bg-white/80"
            }`}
          >
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                isActive
                  ? "bg-[var(--accent)] text-white"
                  : status === "completed"
                    ? "bg-[var(--leaf)] text-white"
                    : status === "running"
                      ? "bg-[var(--sun)] text-[var(--ink)] animate-pulse"
                      : status === "failed"
                        ? "bg-red-400 text-white"
                        : "bg-[var(--sand)] text-[var(--ink-muted)]"
              }`}
            >
              {i + 1}
            </span>
            <span className="flex flex-col">
              <span className="font-display text-lg leading-tight">{s.label}</span>
              <span
                className={`text-xs ${
                  isActive ? "text-white/70" : "text-[var(--ink-muted)]"
                }`}
              >
                {statusLabel(status)}
              </span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "已完成";
    case "running":
      return "生成中…";
    case "failed":
      return "失败";
    default:
      return "待生成";
  }
}
