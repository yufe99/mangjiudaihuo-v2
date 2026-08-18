import Link from "next/link";

export default function Navbar() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg text-slate-900">
          <span className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white text-sm">漫</span>
          漫剧带货平台
        </Link>
        <nav className="flex items-center gap-4 text-sm text-slate-600">
          <Link href="/" className="hover:text-indigo-600">项目</Link>
          <Link href="/settings" className="hover:text-indigo-600">设置</Link>
        </nav>
      </div>
    </header>
  );
}