"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { InterpretationPanel, TermHelp } from "@/components/term-help";

type ResearchSummary = {
  structural_comparability?: { score: number | null; coverage: string; confidence: string };
  policy_evidence?: { score_allowed: boolean; events: Array<{ id: string }> };
  candidates: Array<{ historical_month: string; total_similarity: number }>;
};

export function ResearchProgress() {
  const [data, setData] = useState<ResearchSummary | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${baseUrl}/v1/research/cn-jp-inflation-similarity`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<ResearchSummary> : null)
      .then((payload) => payload && setData(payload))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  if (!data?.structural_comparability) return null;
  const top = data.candidates[0];
  return (
    <section className="panel research-progress">
      <div className="section-heading">
        <div><p className="eyebrow">真实研究进展</p><h2>中日历史比较已经进入首页</h2></div>
        <Link className="research-entry" href="/research/similarity">查看完整证据 →</Link>
      </div>
      <div className="research-progress-grid">
        <div><span>结构可比性 <TermHelp term="结构可比性">比较人口、预期口径、信用与政策制度等慢变量。</TermHelp></span><strong>{data.structural_comparability.score?.toFixed(1) ?? "—"}</strong><small>覆盖 {data.structural_comparability.coverage} · 低置信</small></div>
        <div><span>最相似日本时期 <TermHelp term="历史相似期">数据形态最接近的历史月份，只提供参考路径，不代表会重演。</TermHelp></span><strong>{top?.historical_month.slice(0, 7) ?? "—"}</strong><small>表面相似度 {top?.total_similarity.toFixed(1) ?? "—"}</small></div>
        <div><span>政策证据 <TermHelp term="评分锁定">政策事件需双人复核，未达到审批门槛前不生成分数。</TermHelp></span><strong>{data.policy_evidence?.events.length ?? 0} 条</strong><small>{data.policy_evidence?.score_allowed ? "允许评分" : "评分仍锁定"}</small></div>
      </div>
      <InterpretationPanel>
        <p>真实研究目前支持“查看历史形态与结构差异”，尚不支持把结果转换为人生决策概率。</p>
        <p>首页其他周期状态和未来情景仍是产品样例；它们会在各维度通过滚动回测后逐项替换。</p>
      </InterpretationPanel>
    </section>
  );
}
