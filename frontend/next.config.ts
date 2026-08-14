import type { NextConfig } from "next";
import path from "path";

// 后端上游地址：Docker Compose 里设为 http://backend:8000；
// 本地开发默认 127.0.0.1:8000（rewrites 会把 /api/* 代理过去，前端保持同源）。
const backendUpstream = (
  process.env.BACKEND_UPSTREAM || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  // 产出 standalone 包，便于 Docker / 平台一键部署
  output: "standalone",
  turbopack: {
    root: path.join(__dirname),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUpstream}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
