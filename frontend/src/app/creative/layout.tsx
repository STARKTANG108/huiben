import type { Metadata } from "next";
import "./creative.css";

export const metadata: Metadata = {
  title: "AI Creative Director",
  description:
    "Upload your product, create cinematic ads with AI. Automatic concepts, storyboards, and finished spots.",
};

export default function CreativeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <div className="creative-root">{children}</div>;
}
