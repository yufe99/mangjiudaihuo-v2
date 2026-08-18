"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { projectApi } from "@/lib/api";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [type, setType] = useState<"manju" | "daihuo">("manju");
  const [style, setStyle] = useState("现代都市");
  const [topic, setTopic] = useState("");
  const [productUrl, setProductUrl] = useState("");
  const [productDetail, setProductDetail] = useState("");
  const [episodeCount, setEpisodeCount] = useState(3);
  const [secondsPerEpisode, setSecondsPerEpisode] = useState(15);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const styles = [
    "现代都市", "穿越", "国风", "仙侠", "古风宫斗", "职场精英",
    "美妆时尚", "短剧带货", "悬疑复仇", "甜宠",
  ];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("请填写项目名称");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const project = await projectApi.create({
        name: name.trim(),
        type,
        style,
        topic: topic.trim(),
        product_url: productUrl.trim(),
        product_detail: productDetail.trim(),
        episode_count: episodeCount,
        seconds_per_episode: secondsPerEpisode,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">新建项目</h1>

        <form onSubmit={handleSubmit} className="space-y-5 bg-white rounded-2xl border border-slate-200 p-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">项目名称 *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="例如:宫廷逆袭系列"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">类型</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setType("manju")}
                className={`px-4 py-3 rounded-xl border text-sm font-medium transition ${
                  type === "manju"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300"
                }`}
              >
                🎭 漫剧
              </button>
              <button
                type="button"
                onClick={() => setType("daihuo")}
                className={`px-4 py-3 rounded-xl border text-sm font-medium transition ${
                  type === "daihuo"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300"
                }`}
              >
                🛒 带货
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">风格</label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              {styles.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">主题 / 一句话剧情</label>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="例如:一个现代销售总监穿越到古代宫廷,用营销思维一路升职"
            />
          </div>

          {type === "daihuo" && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">商品链接(可选)</label>
                <input
                  value={productUrl}
                  onChange={(e) => setProductUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  placeholder="淘宝 / 天猫 / 抖音链接"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">商品卖点(可选)</label>
                <textarea
                  value={productDetail}
                  onChange={(e) => setProductDetail(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  placeholder="商品的核心卖点,AI 会织入剧本"
                />
              </div>
            </>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">集数</label>
              <input
                type="number"
                min={1}
                max={10}
                value={episodeCount}
                onChange={(e) => setEpisodeCount(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">每集秒数</label>
              <input
                type="number"
                min={5}
                max={60}
                value={secondsPerEpisode}
                onChange={(e) => setSecondsPerEpisode(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
              />
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition"
          >
            {loading ? "创建中..." : "创建项目"}
          </button>
        </form>
      </main>
    </div>
  );
}