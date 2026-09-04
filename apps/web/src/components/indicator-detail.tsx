"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Point = {
  month: string;
  source_observation_date: string;
  level: number | null;
  robust_z: number | null;
  momentum_3m: number | null;
  change_12m: number | null;
  freshness_weight: number;
  is_carried_forward: boolean;
};

type Detail = {
  indicator: { id: string; name_zh: string; name_en?: string; geography: string; unit?: string; frequency: string; quality_grade: string };
  source_provider: string;
  source_dataset: string;
  source_url: string;
  attribution_text?: string;
  latest_vintage_at?: string;
  feature_cutoff?: string;
  history: Point[];
};

export function IndicatorDetail({ indicatorId }: { indicatorId: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${base}/v1/indicators/${encodeURIComponent(indicatorId)}`)
      .then((response) => {
        if (!response.ok) throw new Error("not found");
        return response.json() as Promise<Detail>;
      })
      .then(setDetail)
      .catch(() => setError(true));
  }, [indicatorId]);

  const chart = useMemo(() => {
    const points = (detail?.history ?? []).filter((row) => row.level !== null);
    if (points.length < 2) return "";
    const values = points.map((row) => row.level as number);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return points.map((row, index) => {
      const x = (index / (points.length - 1)) * 100;
      const y = 92 - (((row.level as number) - min) / span) * 84;
      return `${x},${y}`;
    }).join(" ");
  }, [detail]);

  if (error) return <main className="detail-shell"><Link href="/">← 返回看板</Link><h1>指标暂不可用</h1><p>请确认数据 API 已启动，且指标编号存在。</p></main>;
  if (!detail) return <main className="detail-shell"><p>正在读取指标详情…</p></main>;
  const latest = [...detail.history].reverse().find((row) => row.level !== null);

  return (
    <main className="detail-shell">
      <Link href="/">← 返回看板</Link>
      <header className="detail-header">
        <div><p className="eyebrow">{detail.indicator.geography} · {detail.indicator.frequency}频 · 质量 {detail.indicator.quality_grade}</p><h1>{detail.indicator.name_zh}</h1><p>{detail.indicator.name_en}</p></div>
        <div className="detail-latest"><span>最新特征值</span><strong>{latest?.level?.toLocaleString() ?? "—"}</strong><small>{detail.indicator.unit}</small></div>
      </header>
      <section className="panel detail-chart">
        <h2>最近 120 个月</h2>
        {chart ? <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="指标历史折线"><polyline points={chart} /></svg> : <p>尚无足够真实数据生成曲线。</p>}
      </section>
      <section className="detail-grid">
        <article className="panel"><h2>数据血缘</h2><dl><dt>官方来源</dt><dd><a href={detail.source_url} target="_blank" rel="noreferrer">{detail.source_provider}</a></dd><dt>数据集</dt><dd>{detail.source_dataset}</dd><dt>本次采集</dt><dd>{detail.latest_vintage_at?.slice(0, 19) ?? "尚未采集"}</dd><dt>特征截止</dt><dd>{detail.feature_cutoff?.slice(0, 19) ?? "尚未生成"}</dd></dl><p>{detail.attribution_text}</p></article>
        <article className="panel"><h2>特征解释</h2><p>3个月动量：当前值减去三个月前；12个月变化：当前值减去一年前；稳健 Z 分数：相对自身历史中位数的位置；新鲜度：随数据年龄衰减。</p>{latest?.is_carried_forward && <p className="warning-note">当前月份使用上一期数据结转，并非当月新发布值。</p>}</article>
      </section>
    </main>
  );
}
