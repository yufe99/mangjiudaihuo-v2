"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { isAuthed, settingsApi, SettingsData } from "@/lib/api";

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [toapisKey, setToapisKey] = useState("");
  const [toapisModel, setToapisModel] = useState("seedance-2-mini");
  const [billingMode, setBillingMode] = useState<"byok" | "credit">("byok");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const s = await settingsApi.get();
        setSettings(s);
        setBillingMode(s.billing_mode as "byok" | "credit");
        const toapis = s.provider_configs?.["toapis"] ?? {};
        setToapisModel(toapis.model || "seedance-2-mini");
        if (toapis.api_key && toapis.api_key !== "****") {
          setToapisKey(toapis.api_key);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess(false);
    try {
      const provider_configs: Record<string, { model?: string; api_key?: string }> = {};
      // Preserve existing masked values; only overwrite key if user typed new one
      if (toapisKey && !toapisKey.includes("*")) {
        provider_configs.toapis = { api_key: toapisKey, model: toapisModel };
      } else {
        provider_configs.toapis = { model: toapisModel };
      }
      await settingsApi.update({
        billing_mode: billingMode,
        provider_configs: provider_configs as Record<string, Record<string, string>>,
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
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

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">设置</h1>

        <form onSubmit={handleSave} className="space-y-6 bg-white rounded-2xl border border-slate-200 p-6">
          {/* Billing mode */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">计费模式</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setBillingMode("byok")}
                className={`px-4 py-3 rounded-xl border text-sm font-medium transition ${
                  billingMode === "byok"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600"
                }`}
              >
                🔑 自带 API Key (BYOK)
                <div className="text-[11px] font-normal mt-1 text-slate-500">用自己的 toapis/yijia 账号,平台不抽成</div>
              </button>
              <button
                type="button"
                onClick={() => setBillingMode("credit")}
                className={`px-4 py-3 rounded-xl border text-sm font-medium transition ${
                  billingMode === "credit"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600"
                }`}
              >
                ⚡ 平台积分
                <div className="text-[11px] font-normal mt-1 text-slate-500">充值后平台代理调 API(预留)</div>
              </button>
            </div>
          </div>

          {/* ToAPIs config */}
          <div className="border-t border-slate-100 pt-6">
            <h2 className="font-semibold text-slate-800 mb-3">ToAPIs 网关</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
                <input
                  type="password"
                  value={toapisKey}
                  onChange={(e) => setToapisKey(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  placeholder="sk-... (留空则使用平台配置或本地预览模式)"
                  autoComplete="off"
                />
                <p className="text-xs text-slate-400 mt-1">
                  key 只保存在你自己的账号设置里,不会展示完整内容。
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">视频模型</label>
                <input
                  value={toapisModel}
                  onChange={(e) => setToapisModel(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  placeholder="seedance-2-mini"
                />
                <p className="text-xs text-slate-400 mt-1">
                  可选: seedance-2-mini / seedance-2-fast / grok-video-1.5 / sora-2 等
                </p>
              </div>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          {success && (
            <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              已保存 ✓
            </div>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition"
          >
            {saving ? "保存中..." : "保存设置"}
          </button>
        </form>
      </main>
    </div>
  );
}