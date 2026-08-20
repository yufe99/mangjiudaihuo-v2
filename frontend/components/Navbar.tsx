"use client";

import Link from "next/link";

interface NavbarProps {
  email?: string;
  onLogout?: () => void;
}

export default function Navbar({ email, onLogout }: NavbarProps) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 bg-indigo-600 text-white rounded-lg flex items-center justify-center font-bold">
            漫
          </span>
          <span className="font-semibold text-slate-900">漫剧带货平台</span>
        </Link>

        <nav className="flex items-center gap-2">
          {email && (
            <span className="text-xs text-slate-500 hidden sm:inline mr-2">
              {email}
            </span>
          )}
          <Link
            href="/"
            className="text-sm text-slate-600 hover:text-indigo-600 px-3 py-1.5 rounded"
          >
            创作
          </Link>
          <Link
            href="/settings"
            className="text-sm text-slate-600 hover:text-indigo-600 px-3 py-1.5 rounded"
          >
            API 设置
          </Link>
          {onLogout && (
            <button
              onClick={onLogout}
              className="text-sm text-slate-500 hover:text-red-600 px-3 py-1.5 rounded"
            >
              退出
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}