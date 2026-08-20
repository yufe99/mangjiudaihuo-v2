"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getToken, setToken } from "@/lib/api";

interface ProviderConfig {
  api_key: string;
  base_url: string;
  model: string;
}

interface SettingsForm {
  toapis: ProviderConfig;
  yijia: ProviderConfig;
  billing_mode: "byok" | "credit";
}

const DEFAULT_FORM: SettingsForm = {
  toapis: { api_key: "", base_url: "https://toapis.com/v1", model: "" },
  yijia: { api_key: "", base_url: "https://ai.yijiarj.cn/v1", model: "" },
  billing_mode: "byok",
};

// Fallback API base (used if NEXT_PUBLIC_API_BASE not set in env at build time).
// In dev tunnel mode this is overwritten by env. If user runs frontend locally,
// this defaults to localhost:8000.
const API_FALLBACK = "http://localhost:8000";

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

// Helper: timeout-wrapped fetch so it never hangs forever
async function fetchWithTimeout(
  input: RequestInfo,
  init: RequestInit = {},
  timeoutMs = 8000,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export default function SettingsPage() {
  const router = useRouter();
  const email = useUserEmail();
  const [form, setForm] = useState<SettingsForm>(DEFAULT_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [apiBase, setApiBase] = useState<string>(
    process.env.NEXT_PUBLIC_API_BASE ?? API_FALLBACK,
  );

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [router]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const tok = getToken();
      const r = await fetchWithTimeout(
        `${apiBase}/api/v1/settings`,
        { headers: { Authorization: `Bearer ${tok}` } },
        8000,
      );
      if (!r.ok) {
        if (r.status === 404) {
          setForm(DEFAULT_FORM);
          return;
        }
        const errBody = await r.text().catch(() => r.statusText);
        throw new Error(`HTTP ${r.status}: ${errBody.slice(0, 200)}`);
      }
      const data = await r.json();
      const pc = data.provider_configs ?? {};
      setForm({
        toapis: {
          api_key: pc.toapis?.api_key ?? "",
          base_url: pc.toapis?.base_url ?? DEFAULT_FORM.toapis.base_url,
          model: pc.toapis?.model ?? "",
        },
        yijia: {
          api_key: pc.yijia?.api_key ?? "",
          base_url: pc.yijia?.base_url ?? DEFAULT_FORM.yijia.base_url,
          model: pc.yijia?.model ?? "",
        },
        billing_mode: data.billing_mode ?? "byok",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "加载失败";
      setError(
        `无法连接到后端 (${apiBase})。${msg}。\n如果你在 Cloudflare Tunnel 模式下,把此页重新打开并设置 NEXT_PUBLIC_API_BASE 后端地址。`,
      );
      setForm(DEFAULT_FORM);
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const tok = getToken();
      const r = await fetchWithTimeout(
        `${apiBase}/api/v1/settings`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${tok}`,
          },
          body: JSON.stringify({
            provider_configs: {
              toapis: {
                api_key: form.toapis.api_key.trim(),
                base_url: form.toapis.base_url.trim(),
                model: form.toapis.model.trim(),
              },
              yijia: {
                api_key: form.yijia.api_key.trim(),
                base_url: form.yijia.base_url.trim(),
                model: form.yijia.model.trim(),
              },
            },
            billing_mode: form.billing_mode,
          }),
        },
        8000,
      );
      if (!r.ok) {
        const errBody = await r.text().catch(() => r.statusText);
        throw new Error(`HTTP ${r.status}: ${errBody.slice(0, 200)}`);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  function logout() {
    setToken("");
    router.replace("/login");
  }

  function reloadWithNewApi() {
    const newBase = prompt(
      "后端 API 地址 (例如 https://relatives-andrews-pixels-heights.trycloudflare.com):",
      apiBase,
    );
    if (newBase && newBase !== apiBase) {
      setApiBase(newBase.trim());
      // load() will re-run via useEffect when apiBase changes — but
      // since we don't depend on it, just trigger manually:
      setLoading(true);
      setError("");
      load();
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar email={email} onLogout={logout} />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">API 设置</h1>
        <p className="text-sm text-slate-500 mb-6">
          配置你自己的 AI API key,生成真视频/真图片。没填就走本地预览模式。
        </p>

        {loading ? (
          <div className="space-y-3">
            <div className="bg-white rounded-2xl border border-slate-200 p-6 text-sm text-slate-500">
              加载中...
            </div>
            <button
              onClick={reloadWithNewApi}
              className="w-full bg-white border border-slate-200 hover:border-indigo-500 text-slate-700 py-2 rounded-lg text-sm"
            >
              加载不出来?点这里手动指定后端地址
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* 调试条 */}
            <div className="text-xs text-slate-400 flex items-center justify-between bg-slate-50 px-3 py-2 rounded">
              <span>后端地址: <code className="text-slate-600">{apiBase}</code></span>
              <button
                onClick={reloadWithNewApi}
                className="text-indigo-600 hover:underline"
              >
                改地址
              </button>
            </div>

            {/* 模式选择 */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-base font-semibold text-slate-900 mb-3">
                计费模式
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setForm({ ...form, billing_mode: "byok" })}
                  className={`px-4 py-3 border-2 rounded-xl text-sm transition ${
                    form.billing_mode === "byok"
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-slate-200 text-slate-600"
                  }`}
                >
                  <div className="font-medium mb-1">🪪 自带 key (BYOK)</div>
                  <div className="text-xs text-slate-500">填你自己的 API,平台不抽成</div>
                </button>
                <button
                  onClick={() => setForm({ ...form, billing_mode: "credit" })}
                  className={`px-4 py-3 border-2 rounded-xl text-sm transition ${
                    form.billing_mode === "credit"
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-slate-200 text-slate-600"
                  }`}
                >
                  <div className="font-medium mb-1">💰 平台积分</div>
                  <div className="text-xs text-slate-500">用平台余额(预留,暂未开通)</div>
                </button>
              </div>
            </div>

            {/* ToAPIs */}
            <ProviderCard
              title="ToAPIs 网关"
              description="推荐用这个,一个 key 涵盖文本/图像/视频多个模型。"
              baseUrl={form.toapis.base_url}
              onBaseUrlChange={(v) =>
                setForm({ ...form, toapis: { ...form.toapis, base_url: v } })
              }
              apiKey={form.toapis.api_key}
              onApiKeyChange={(v) =>
                setForm({ ...form, toapis: { ...form.toapis, api_key: v } })
              }
              model={form.toapis.model}
              onModelChange={(v) =>
                setForm({ ...form, toapis: { ...form.toapis, model: v } })
              }
              apiKeyExample="sk-xxxxxxxxxxxxxxxx (在 toapis.com/dashboard 申请)"
              modelExample="deepseek-v4-flash / gpt-image-2 / seedance-2-mini"
            />

            {/* Yijia */}
            <ProviderCard
              title="易加 AI 网关 (备用)"
              description="可选。不填也能跑(toapis 失败时系统会自动 fallback)。"
              baseUrl={form.yijia.base_url}
              onBaseUrlChange={(v) =>
                setForm({ ...form, yijia: { ...form.yijia, base_url: v } })
              }
              apiKey={form.yijia.api_key}
              onApiKeyChange={(v) =>
                setForm({ ...form, yijia: { ...form.yijia, api_key: v } })
              }
              model={form.yijia.model}
              onModelChange={(v) =>
                setForm({ ...form, yijia: { ...form.yijia, model: v } })
              }
              apiKeyExample="xxxxxxxxxxxx (在 ai.yijiarj.cn 申请)"
              modelExample="image2 / image2-2k"
            />

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-600 whitespace-pre-line">
                {error}
              </div>
            )}
            {saved && (
              <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-700">
                ✓ 已保存
              </div>
            )}

            <button
              onClick={save}
              disabled={saving}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-3 rounded-lg text-sm transition"
            >
              {saving ? "保存中..." : "保存设置"}
            </button>

            <p className="text-xs text-slate-400 text-center">
              API key 仅存在你自己账号的数据库里,不会出现在仓库或日志中。
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function ProviderCard(props: {
  title: string;
  description: string;
  baseUrl: string;
  onBaseUrlChange: (v: string) => void;
  apiKey: string;
  onApiKeyChange: (v: string) => void;
  model: string;
  onModelChange: (v: string) => void;
  apiKeyExample: string;
  modelExample: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <h2 className="text-base font-semibold text-slate-900 mb-1">{props.title}</h2>
      <p className="text-xs text-slate-500 mb-4">{props.description}</p>
      <div className="space-y-4">
        <Field
          label="Base URL"
          help="API 网关地址,通常不用改"
          value={props.baseUrl}
          onChange={props.onBaseUrlChange}
        />
        <Field
          label="API Key"
          help="你的网关密钥"
          required
          type="password"
          value={props.apiKey}
          onChange={props.onApiKeyChange}
          placeholder={props.apiKeyExample}
        />
        <Field
          label="默认模型 (可选)"
          help="留空用网关默认模型"
          value={props.model}
          onChange={props.onModelChange}
          placeholder={props.modelExample}
        />
      </div>
    </div>
  );
}

function Field(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  help?: string;
  required?: boolean;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {props.label}
        {props.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        placeholder={props.placeholder}
        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      {props.help && <p className="text-xs text-slate-400 mt-1">{props.help}</p>}
    </div>
  );
}