/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // 允许 Cloudflare Tunnel 等外部域名访问 (开发模式)
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    "visitor-theme-varying-attending.trycloudflare.com",
    "reverse-king-dimension-precisely.trycloudflare.com",
    ".trycloudflare.com",  // 任意 trycloudflare 子域名
  ],
};

export default nextConfig;