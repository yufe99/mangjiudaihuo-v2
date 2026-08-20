"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { isAuthed, setToken, getToken } from "@/lib/api";

// 工具函数:从 token 解析 email 显示
function useUserEmail() {
  const [email, setEmail] = useState<string>("");
  useEffect(() => {
    const tok = getToken();
    if (!tok) return;
    try {
      const payload = JSON.parse(atob(tok.split(".")[1]));
      setEmail(payload.sub || "");
    } catch {}
  }, []);
  return email;
}

interface ProductForm {
  name: string;
  price: string;
  selling_points: string; // 用换行/逗号分隔都行
  target_audience: string;
  style: string;
  episode_count: number;
  seconds_per_episode: number;
}

interface RunResult {
  project_id: number;
  project_name: string;
  characters: { name: string; status: string }[];
  episodes: any[];
  final_videos: { episode_id: number; index: number; path: string }[];
  project_final_video: string | null;
  used_provider?: string;
}

export default function HomePage() {
  const router = useRouter();
  const email = useUserEmail();
  const [form, setForm] = useState<ProductForm>({
    name: "",
    price: "",
    selling_points: "",
    target_audience: "",
    style: "美妆时尚",
    episode_count: 3,
    seconds_per_episode: 8,
  });
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<RunResult | null>(null);

  useEffect(() => {
    if (!isAuthed()) {
      router.replace("/login");
    }
  }, [router]);

  async function logout() {
    setToken("");
    router.replace("/login");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.name.trim()) {
      setError("请填商品名");
      return;
    }
    if (!form.selling_points.trim()) {
      setError("至少填 1 个卖点");
      return;
    }
    setRunning(true);
    setProgress("正在创建项目...");
    setResult(null);
    try {
      const points = form.selling_points
        .split(/[\n,]/g)
        .map((p) => p.trim())
        .filter(Boolean);
      const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const token = getToken();
      // 1. create product
      setProgress("① 创建带货项目...");
      const r1 = await fetch(`${API}/api/v1/products/from-manual`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: form.name.trim(),
          price: form.price ? Number(form.price) : null,
          selling_points: points,
          target_audience: form.target_audience.trim(),
          style: form.style,
          episode_count: form.episode_count,
          seconds_per_episode: form.seconds_per_episode,
        }),
      });
      if (!r1.ok) throw new Error((await r1.json()).detail ?? r1.statusText);
      const project = await r1.json();

      // 2. run-all
      setProgress("② 一键跑全流程(剧本→角色→分镜→视频→配音→合成)...");
      const r2 = await fetch(`${API}/api/v1/projects/${project.project_id}/run-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r2.ok) throw new Error((await r2.json()).detail ?? r2.statusText);
      const runRes = await r2.json();
      if (runRes.error) throw new Error(runRes.error);

      setProgress("✓ 完成");
      setResult(runRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar email={email} onLogout={logout} />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">AI 带货短剧生成</h1>
          <p className="text-sm text-slate-500 mb-6">
            填商品信息 → 点按钮 → 拿到带货视频
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 商品名 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                商品名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                placeholder="例如:胶原蛋白口服液"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              />
            </div>

            {/* 价格 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                价格 (可选)
              </label>
              <input
                type="number"
                placeholder="例如:199"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              />
            </div>

            {/* 卖点 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                卖点 <span className="text-red-500">*</span>
                <span className="text-xs text-slate-400 font-normal ml-2">
                  每行 1 条,或用逗号分隔(至少 1 条)
                </span>
              </label>
              <textarea
                placeholder={"法国进口原料\n7天见效\n0添加蔗糖"}
                value={form.selling_points}
                onChange={(e) => setForm({ ...form, selling_points: e.target.value })}
                rows={4}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              />
            </div>

            {/* 目标人群 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                目标人群 (可选)
              </label>
              <input
                type="text"
                placeholder="例如:25-35 岁都市女性"
                value={form.target_audience}
                onChange={(e) => setForm({ ...form, target_audience: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              />
            </div>

            {/* 风格 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                风格
              </label>
              <select
                value={form.style}
                onChange={(e) => setForm({ ...form, style: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              >
                <option value="美妆时尚">美妆时尚</option>
                <option value="家居好物">家居好物</option>
                <option value="数码电子">数码电子</option>
                <option value="食品饮料">食品饮料</option>
                <option value="母婴亲子">母婴亲子</option>
                <option value="运动健身">运动健身</option>
                <option value="职场精英">职场精英</option>
              </select>
            </div>

            {/* 集数 + 时长 */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  集数 (2-8)
                </label>
                <input
                  type="number"
                  min={2}
                  max={8}
                  value={form.episode_count}
                  onChange={(e) =>
                    setForm({ ...form, episode_count: Math.max(2, Math.min(8, Number(e.target.value))) })
                  }
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  disabled={running}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  每集秒数 (5-30)
                </label>
                <input
                  type="number"
                  min={5}
                  max={30}
                  value={form.seconds_per_episode}
                  onChange={(e) =>
                    setForm({ ...form, seconds_per_episode: Math.max(5, Math.min(30, Number(e.target.value))) })
                  }
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  disabled={running}
                />
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}

            {progress && (
              <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 text-sm text-indigo-700">
                {progress}
              </div>
            )}

            <button
              type="submit"
              disabled={running}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-3 rounded-lg text-base transition"
            >
              {running ? "生成中(约 30-90 秒)..." : "🎬 生成带货短剧"}
            </button>

            <p className="text-xs text-slate-400 text-center">
              没填 API key 时用本地预览模式(模板)。要真 AI:
              <Link href="/settings" className="text-indigo-600 hover:underline ml-1">
                去设置 →
              </Link>
            </p>
          </form>
        </div>

        {/* 结果区 */}
        {result && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">
              生成完成!
            </h2>

            {/* 角色 */}
            {result.characters?.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-slate-600 mb-2">角色</h3>
                <div className="flex flex-wrap gap-2">
                  {result.characters.map((c, i) => (
                    <span
                      key={i}
                      className={`px-2 py-1 rounded text-xs ${
                        c.status === "done"
                          ? "bg-green-100 text-green-700"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {c.status === "done" ? "✓" : "○"} {c.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 视频下载 */}
            {result.final_videos?.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-slate-600 mb-2">
                  下载视频
                </h3>
                <div className="space-y-2">
                  {result.final_videos.map((v) => (
                    <a
                      key={v.episode_id}
                      href={`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/api/v1/projects/${result.project_id}/download/episode-${v.index}`}
                      target="_blank"
                      className="flex items-center justify-between px-4 py-3 border border-slate-200 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition"
                    >
                      <span className="text-sm font-medium text-slate-800">
                        📹 第 {v.index} 集
                      </span>
                      <span className="text-xs text-indigo-600">下载 MP4 →</span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* 剧本 */}
            <details className="mt-2">
              <summary className="text-sm text-slate-500 cursor-pointer">
                查看剧本 JSON
              </summary>
              <pre className="mt-2 p-3 bg-slate-50 rounded text-xs overflow-auto max-h-64">
                {JSON.stringify(
                  {
                    project: result.project_id,
                    name: result.project_name,
                    episodes: result.episodes?.map((e) => ({
                      index: e.index,
                      title: e.title,
                      shots: e.storyboard?.shots?.length ?? 0,
                    })),
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </div>
        )}
      </main>
    </div>
  );
}