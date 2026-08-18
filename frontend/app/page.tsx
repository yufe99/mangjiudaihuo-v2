"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { isAuthed, projectApi, Project } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    setLoading(true);
    try {
      const list = await projectApi.list();
      setProjects(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">我的项目</h1>
            <p className="text-sm text-slate-500 mt-1">创建 AI 漫剧或带货系列</p>
          </div>
          <Link
            href="/new"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            + 新建项目
          </Link>
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center text-slate-500 py-16">加载中...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-5xl mb-4">🎬</div>
            <p className="text-slate-500 mb-4">还没有项目</p>
            <Link
              href="/new"
              className="text-indigo-600 font-medium hover:underline"
            >
              创建第一个项目 →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition group"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium px-2 py-1 bg-indigo-50 text-indigo-700 rounded-full">
                    {p.type === "daihuo" ? "带货" : "漫剧"}
                  </span>
                  <span className="text-xs text-slate-400">
                    {p.episode_count} 集
                  </span>
                </div>
                <h2 className="font-semibold text-slate-900 group-hover:text-indigo-600">
                  {p.name}
                </h2>
                <p className="text-sm text-slate-500 mt-1 line-clamp-2">
                  {p.topic || "—"}
                </p>
                <div className="mt-4 flex gap-2 text-[11px]">
                  {p.characters_status === "done" && (
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded-full">角色✓</span>
                  )}
                  {p.storyboard_status === "done" && (
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded-full">分镜✓</span>
                  )}
                  {p.video_status === "done" && (
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded-full">视频✓</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}