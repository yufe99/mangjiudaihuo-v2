"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { isAuthed, projectApi, Project, scriptApi, ScriptData } from "@/lib/api";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [script, setScript] = useState<ScriptData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    try {
      const p = await projectApi.get(projectId);
      setProject(p);
      // Try loading script if already generated
      try {
        const s = await scriptApi.get(projectId);
        setScript(s);
      } catch {
        // 404 → not generated yet, fine
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleGenerateScript() {
    setGenerating(true);
    setError("");
    try {
      const s = await scriptApi.generate(projectId);
      setScript(s);
      // Refresh project to update status
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <div className="text-center py-20 text-slate-500">加载中...</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <p className="text-slate-600 mb-4">{error || "项目不存在"}</p>
          <button onClick={() => router.push("/")} className="text-indigo-600 hover:underline">
            返回项目列表
          </button>
        </div>
      </div>
    );
  }

  const steps = [
    { n: 1, name: "剧本", done: !!script },
    { n: 2, name: "角色", done: false },
    { n: 3, name: "分镜", done: false },
    { n: 4, name: "视频", done: false },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {project.type === "daihuo" ? "带货" : "漫剧"} · {project.style} · {project.episode_count} 集
            </p>
          </div>
          <button
            onClick={() => router.push("/")}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            ← 返回
          </button>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center gap-2 mb-8 bg-white rounded-xl border border-slate-200 p-4">
          {steps.map((s, i) => (
            <div key={s.n} className="flex items-center flex-1">
              <div className={`flex items-center gap-2 ${s.done ? "text-green-600" : "text-slate-400"}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                  s.done ? "bg-green-100" : "bg-slate-100"
                }`}>
                  {s.done ? "✓" : s.n}
                </div>
                <span className="text-sm font-medium">{s.name}</span>
              </div>
              {i < steps.length - 1 && <div className="flex-1 h-px bg-slate-200 mx-2" />}
            </div>
          ))}
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
            {error}
          </div>
        )}

        {/* Step 1: Script */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">① 剧本</h2>
            <button
              onClick={handleGenerateScript}
              disabled={generating}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
            >
              {generating ? "生成中..." : script ? "重新生成" : "生成剧本"}
            </button>
          </div>

          {!script ? (
            <p className="text-sm text-slate-500 py-6 text-center">
              点击「生成剧本」,AI 会根据主题 / 风格 / 集数一次性生成系列剧本(分集大纲 + 角色设定 + 资产清单)。
              <br />
              <span className="text-xs text-slate-400 mt-2 block">
                没配置 API key 时自动使用本地预览模式(模板剧本)
              </span>
            </p>
          ) : (
            <div className="space-y-5">
              <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
                <p className="text-sm text-slate-700">
                  <span className="font-semibold text-indigo-700">Logline: </span>
                  {script.logline}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2">角色</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {script.characters.map((c) => (
                    <div key={c.name} className="border border-slate-200 rounded-xl p-3">
                      <div className="font-medium text-slate-800">{c.name}</div>
                      <div className="text-xs text-slate-500 mt-1">{c.description}</div>
                      <div className="text-xs text-slate-400 mt-1">{c.appearance}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2">资产</h3>
                <div className="flex flex-wrap gap-2">
                  {script.assets.map((a, i) => (
                    <span key={i} className="text-xs px-3 py-1 bg-slate-100 text-slate-600 rounded-full">
                      {a.type === "scene" ? "🏞" : a.type === "prop" ? "🎭" : "🛒"} {a.name}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2">分集大纲</h3>
                <div className="space-y-2">
                  {script.episodes.map((ep) => (
                    <div key={ep.index} className="border border-slate-200 rounded-xl p-3">
                      <div className="font-medium text-slate-800">
                        EP{ep.index}: {ep.title}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">{ep.outline}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="text-xs text-slate-400">
                步骤②③④ 将在后续版本中实现(角色锚点图 → 分镜 → 视频生成)。
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}