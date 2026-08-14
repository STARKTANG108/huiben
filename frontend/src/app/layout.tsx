import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pictale · 儿童绘本视频",
  description: "输入主题，生成故事、分镜、配音与约一分钟成片",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
