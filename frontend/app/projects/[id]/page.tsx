"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  isAuthed,
  projectApi,
  Project,
  scriptApi,
  ScriptData,
} from "@/lib/api";

// Simple backend API helpers (not in lib/api.ts since these are new in v2.1)
async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const token = localStorage.getItem("mjdh_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
  const r = await fetch(`${API}/api/v1${path}`, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 204) return undefined as T;
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail ?? `HTTP ${r.status}`);
  return data as T;
}

async function apiGet<T>(path: string): Promise<T> {
  const token = localStorage.getItem("mjdh_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
  const r = await fetch(`${API}/api/v1${path}`, { headers });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail ?? `HTTP ${r.status}`);
  }
  return (await r.json()) as T;
}

interface Character { id: number; name: string; status: string; anchor_image_url: string; error_message: string; }
interface Shot { index: number; title: string; prompt: string; narration: string; characters: string[]; duration: number; }

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [script, setScript] = useState<ScriptData | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [episodes, setEpisodes] = useState<{ id: number; index: number; title: string; storyboard_json: any }[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    try {
      const p = await projectApi.get(projectId);
      setProject(p);
      try { setScript(await scriptApi.get(projectId)); } catch {}
      try {
        setCharacters(await apiGet<Character[]>(`/projects/${projectId}/characters`));
      } catch {}
      try {
        // List episodes (use storyboard JSON if available)
        const all = (p as any).episodes || [];
        setEpisodes(all);
      } catch {}
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, router]);

  useEffect(() => { load(); }, [load]);

  async function generateScript() {
    setBusy("script"); setError("");
    try {
      const s = await scriptApi.generate(projectId);
      setScript(s);
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(null);
    }
  }

  async function generateCharacters() {
    setBusy("characters"); setError("");
    try {
      await apiPost(`/projects/${projectId}/characters/generate`);
      setCharacters(await apiGet<Character[]>(`/projects/${projectId}/characters`));
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(null);
    }
  }

  async function generateStoryboard(episodeId: number) {
    setBusy(`sb-${episodeId}`); setError("");
    try {
      await apiPost(`/projects/${projectId}/episodes/${episodeId}/storyboard/generate`);
      const p = await projectApi.get(projectId);
      setProject(p);
      setEpisodes(((p as any).episodes) || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(null);
    }
  }

  async function generateVideos(episodeId: number) {
    setBusy(`vid-${episodeId}`); setError("");
    try {
      const r = await apiPost<{ results: any[] }>(
        `/projects/${projectId}/episodes/${episodeId}/generate-videos`
      );
      const failed = r.results.filter((x) => x.status === "failed");
      if (failed.length) {
        setError(`${failed.length}/${r.results.length} 镜头失败:${failed[0].error ?? "unknown"}`);
      }
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(null);
    }
  }

  async function generateTTS(episodeId: number) {
    setBusy(`tts-${episodeId}`); setError("");
    try {
      await apiPost(`/tts/episodes/${episodeId}/synthesize-all`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "TTS 失败");
    } finally {
      setBusy(null);
    }
  }

  async function mergeEpisode(episodeId: number) {
    setBusy(`merge-${episodeId}`); setError("");
    try {
      await apiPost(`/projects/${projectId}/episodes/${episodeId}/merge`);
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "合成失败");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return <div className="min-h-screen bg-slate-50"><Navbar /><div className="text-center py-20 text-slate-500">加载中...</div></div>;
  }
  if (!project) {
    return (
      <div className="min-h-screen bg-slate-50"><Navbar />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <p className="text-slate-600 mb-4">{error || "项目不存在"}</p>
          <button onClick={() => router.push("/")} className="text-indigo-600 hover:underline">返回项目列表</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {project.type === "daihuo" ? "带货" : "漫剧"} · {project.style} · {project.episode_count} 集
            </p>
          </div>
          <button onClick={() => router.push("/")} className="text-sm text-slate-500 hover:text-slate-700">
            ← 返回
          </button>
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">{error}</div>
        )}

        {/* ① Script */}
        <Section title="① 剧本" done={!!script}>
          {!script ? (
            <Placeholder>
              点击「生成剧本」,AI 会根据主题 / 风格 / 集数一次性生成系列剧本。
              <br />
              <span className="text-xs text-slate-400 mt-2 block">
                没配置 API key 时自动使用本地预览模式(模板剧本)
              </span>
            </Placeholder>
          ) : (
            <ScriptView script={script} />
          )}
          <button
            onClick={generateScript}
            disabled={busy === "script"}
            className="mt-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {busy === "script" ? "生成中..." : script ? "重新生成" : "生成剧本"}
          </button>
        </Section>

        {/* ② Characters */}
        <Section title="② 角色锚点图" done={characters.length > 0 && characters.every((c) => c.status === "done")} disabled={!script}>
          {!script ? (
            <Placeholder>请先生成剧本(①)</Placeholder>
          ) : characters.length === 0 ? (
            <Placeholder>
              为每个角色生成 1 张锚点图。后续所有镜头都会复用这些锚点,保证跨集角色一致。
            </Placeholder>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {characters.map((c) => (
                <div key={c.id} className="border border-slate-200 rounded-xl p-3">
                  <div className="aspect-square bg-slate-100 rounded-lg mb-2 overflow-hidden flex items-center justify-center">
                    {c.anchor_image_url ? (
                      <img src={c.anchor_image_url} alt={c.name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-3xl text-slate-300">🎭</span>
                    )}
                  </div>
                  <div className="text-sm font-medium text-slate-800">{c.name}</div>
                  <div className={`text-[11px] mt-1 ${
                    c.status === "done" ? "text-green-600" :
                    c.status === "failed" ? "text-red-600" :
                    "text-slate-500"
                  }`}>
                    {c.status === "done" ? "✓ 已生成" :
                     c.status === "failed" ? "✗ 失败" :
                     c.status === "generating" ? "⏳ 生成中" : "待生成"}
                  </div>
                </div>
              ))}
            </div>
          )}
          <button
            onClick={generateCharacters}
            disabled={busy === "characters" || !script}
            className="mt-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {busy === "characters" ? "生成中..." : characters.length > 0 ? "重新生成全部" : "生成角色锚点图"}
          </button>
        </Section>

        {/* ③ Episodes (Storyboard + Video per episode) */}
        <Section title="③ 分镜与视频" done={false} disabled={!script}>
          {episodes.length === 0 ? (
            <Placeholder>先生成剧本(①)后这里会出现各集。</Placeholder>
          ) : (
            <div className="space-y-4">
              {episodes.map((ep) => (
                <EpisodeCard
                  key={ep.id}
                  episode={ep}
                  busy={busy}
                  onGenerateStoryboard={() => generateStoryboard(ep.id)}
                  onGenerateVideos={() => generateVideos(ep.id)}
                  onGenerateTTS={() => generateTTS(ep.id)}
                  onMerge={() => mergeEpisode(ep.id)}
                />
              ))}
            </div>
          )}
        </Section>

        {/* ④ Final composite */}
        <Section title="④ 合成全集" done={!!project.final_video_path} disabled={!script}>
          {!script ? (
            <Placeholder>先生成剧本(①)与各集视频(③)。</Placeholder>
          ) : project.final_video_path ? (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-green-700 font-medium mb-2">✓ 全集已合成</div>
              <video src={`/api/v1/static?path=${encodeURIComponent(project.final_video_path)}`} controls className="w-full rounded-lg" />
              <a href={project.final_video_path} download className="text-sm text-indigo-600 hover:underline mt-2 inline-block">
                下载视频
              </a>
            </div>
          ) : (
            <Placeholder>
              各集视频生成后,点这里合成完整短剧。
            </Placeholder>
          )}
        </Section>
      </main>
    </div>
  );
}

function Section({
  title, done, disabled, children,
}: { title: string; done: boolean; disabled?: boolean; children: React.ReactNode }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 p-6 mb-6 ${disabled ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-2 mb-4">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${done ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-400"}`}>
          {done ? "✓" : "•"}
        </div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-slate-500 py-4 text-center">{children}</p>;
}

function ScriptView({ script }: { script: ScriptData }) {
  return (
    <div className="space-y-4">
      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3">
        <p className="text-sm text-slate-700"><span className="font-semibold text-indigo-700">Logline: </span>{script.logline}</p>
      </div>
      <div>
        <h3 className="text-xs font-semibold text-slate-600 mb-2">角色</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {script.characters.map((c) => (
            <div key={c.name} className="border border-slate-200 rounded-lg p-2">
              <div className="font-medium text-sm text-slate-800">{c.name}</div>
              <div className="text-xs text-slate-500">{c.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function EpisodeCard({
  episode, busy, onGenerateStoryboard, onGenerateVideos, onGenerateTTS, onMerge,
}: {
  episode: { id: number; index: number; title: string; storyboard_json: any };
  busy: string | null;
  onGenerateStoryboard: () => void;
  onGenerateVideos: () => void;
  onGenerateTTS: () => void;
  onMerge: () => void;
}) {
  const sb = episode.storyboard_json;
  const shots: Shot[] = (sb && sb.shots) || [];
  const allVideosDone = shots.length > 0 && shots.every((_, i) => (sb?.results?.[i]?.video_path));
  return (
    <div className="border border-slate-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-800">EP{episode.index}: {episode.title || `第 ${episode.index} 集`}</h3>
        <div className="flex gap-2">
          <button onClick={onGenerateStoryboard} disabled={busy === `sb-${episode.id}`}
            className="text-xs bg-slate-100 hover:bg-slate-200 disabled:opacity-50 px-3 py-1.5 rounded">
            {busy === `sb-${episode.id}` ? "分镜中..." : shots.length > 0 ? "重新分镜" : "③ 生成分镜"}
          </button>
          {shots.length > 0 && (
            <>
              <button onClick={onGenerateTTS} disabled={busy === `tts-${episode.id}`}
                className="text-xs bg-slate-100 hover:bg-slate-200 disabled:opacity-50 px-3 py-1.5 rounded">
                {busy === `tts-${episode.id}` ? "配音中..." : "配音"}
              </button>
              <button onClick={onGenerateVideos} disabled={busy === `vid-${episode.id}`}
                className="text-xs bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-3 py-1.5 rounded">
                {busy === `vid-${episode.id}` ? "生成中..." : "③ 生成视频"}
              </button>
              <button onClick={onMerge} disabled={busy === `merge-${episode.id}`}
                className="text-xs bg-slate-100 hover:bg-slate-200 disabled:opacity-50 px-3 py-1.5 rounded">
                {busy === `merge-${episode.id}` ? "合成中..." : "④ 合成"}
              </button>
            </>
          )}
        </div>
      </div>
      {shots.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {shots.map((s) => (
            <div key={s.index} className="bg-slate-50 rounded-lg p-2 text-xs">
              <div className="font-medium text-slate-800 mb-1">#{s.index} {s.title}</div>
              <div className="text-slate-600 line-clamp-2">{s.narration}</div>
              <div className="mt-1 text-slate-400">{s.duration}s · {s.characters?.join(", ") || "无"}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-400">尚未生成分镜。点「生成分镜」让 LLM 拆 3-5 个镜头。</p>
      )}
    </div>
  );
}