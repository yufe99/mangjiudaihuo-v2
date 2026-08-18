import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "漫剧带货平台",
  description: "AI 漫剧/带货 系列生产平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}