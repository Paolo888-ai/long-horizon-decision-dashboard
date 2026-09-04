"use client";

import { useCallback, useEffect, useState } from "react";

import { InterpretationPanel, TermHelp } from "@/components/term-help";

type Comparison = {
  subtheme: string;
  current_signal: number;
  historical_signal: number;
  absolute_gap: number;
};

type EvidenceCard = {
  rank: number;
  historical_period: string;
  scores: { total: number; state: number; trajectory: number; structure: null };
  main_similarities: Comparison[];
  main_differences: Comparison[];
  subsequent_path: { six_month_average_cpi_change: number };
  comparability_warning: string;
};

type EvidenceResponse = {
  mode: "backtest_evidence_card";
  status: string;
  confidence: "low";
  target_cutoff?: string;
  requested_cutoff?: string | null;
  available_cutoffs: string[];
  path_distribution?: {
    minimum_change: number;
    median_change: number;
    maximum_change: number;
    range: number;
  };
  neighbor_stability?: { mean_consecutive_jaccard: number; interpretation: string };
  refusal_reasons: string[];
  cards: EvidenceCard[];
  warning: string;
};

type LoadState =
  | { status: "loading" }
  | { status: "offline" }
  | { status: "ready"; data: EvidenceResponse };

const labels: Record<string, string> = {
  consumer_goods_prices: "消费品价格",
  services_prices: "服务价格",
  producer_prices: "生产者价格",
  household_price_expectations: "居民物价预期",
};

export function SimilarityEvidence() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [cutoff, setCutoff] = useState("");
  const load = useCallback((selected?: string) => {
    const controller = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    const query = selected ? `?cutoff=${selected}` : "";
    fetch(`${baseUrl}/v1/backtests/cn-similarity/evidence-card${query}`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error("Evidence API unavailable");
        return response.json() as Promise<EvidenceResponse>;
      })
      .then((data) => {
        setState({ status: "ready", data });
        if (!selected && data.target_cutoff) setCutoff(data.target_cutoff.slice(0, 7));
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "offline" });
      });
    return controller;
  }, []);

  useEffect(() => {
    const controller = load();
    return () => controller.abort();
  }, [load]);

  if (state.status === "loading") {
    return <div className="research-state">正在重建严格历史证据卡…</div>;
  }
  if (state.status === "offline") {
    return <div className="research-state error">证据卡API未连接，请先启动本地API。</div>;
  }

  const { data } = state;
  return (
    <>
      <section className="research-hero panel">
        <div>
          <p className="eyebrow">Backtest evidence · 仅供研究</p>
          <h1>历史相似，不等于历史重演</h1>
          <p>{data.warning}</p>
        </div>
        <div className="confidence-lock">
          <span>置信度上限 <TermHelp term="置信度">表示证据能支持结论的强弱，不是成功概率。这里为低，意味着只能把结果当作线索。</TermHelp></span><strong>低</strong><small>高置信类比已拒绝</small>
        </div>
      </section>

      <section className="research-controls panel">
        <label htmlFor="cutoff">回测月份 <TermHelp term="cutoff">数据截止线：只允许使用这个月当时已经公开的数据，防止偷看未来。</TermHelp></label>
        <select
          id="cutoff"
          value={cutoff}
          onChange={(event) => {
            const value = event.target.value;
            setCutoff(value);
            setState({ status: "loading" });
            load(value);
          }}
        >
          {data.available_cutoffs.map((value) => <option key={value}>{value}</option>)}
        </select>
        <span>只展示当时可见特征；后续路径仅用于事后回测。</span>
      </section>

      <section className="refusal-box">
        <div><span className="lock-dot" />高置信类比已拒绝</div>
        <ul>{data.refusal_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
      </section>

      {data.path_distribution && data.neighbor_stability && (
        <section className="evidence-metrics panel">
          <div><span>历史路径范围 <TermHelp term="历史路径范围">相似时期之后结果的最大值与最小值之差；越大说明历史后续越分散。</TermHelp></span><strong>{data.path_distribution.range.toFixed(3)}</strong><small>个百分点</small></div>
          <div><span>路径中位变化 <TermHelp term="中位数">把所有结果排序后位于中间的值，比平均数更不容易被极端值带偏。</TermHelp></span><strong>{data.path_distribution.median_change.toFixed(3)}</strong><small>未来6个月</small></div>
          <div><span>榜单稳定性 <TermHelp term="Jaccard稳定性">比较相邻两个月的相似期名单有多少重合。接近1较稳定，接近0变化较大。</TermHelp></span><strong>{data.neighbor_stability.mean_consecutive_jaccard.toFixed(3)}</strong><small>连续月份Jaccard</small></div>
        </section>
      )}

      {data.path_distribution && data.neighbor_stability && (
        <InterpretationPanel>
          <p>历史相似期之后的路径跨度为 {data.path_distribution.range.toFixed(3)} 个百分点，中位变化为 {formatSigned(data.path_distribution.median_change)} 个百分点。</p>
          <p>{data.neighbor_stability.mean_consecutive_jaccard < 0.5 ? "榜单稳定性低于0.5，说明只改变一个月，候选时期就可能明显变化。" : "榜单在相邻月份有一定延续性，但仍需结合差异项判断。"} 这些数字描述历史样本，不代表未来六个月必然同方向变化。</p>
        </InterpretationPanel>
      )}

      <section className="evidence-list">
        {data.cards.map((card) => <HistoryEvidenceCard key={card.rank} card={card} />)}
      </section>
    </>
  );
}

function HistoryEvidenceCard({ card }: { card: EvidenceCard }) {
  return (
    <details className="history-card panel" open={card.rank === 1}>
      <summary>
        <span className="rank">0{card.rank}</span>
        <div><small>中国 · 通胀环境</small><h2>{card.historical_period}</h2></div>
        <div className="similarity-score"><strong>{card.scores.total.toFixed(1)}</strong><span>表面相似度 <TermHelp term="表面相似度">只比较已纳入的数据形态；高分不代表制度背景相同，也不是未来重演概率。</TermHelp></span></div>
      </summary>
      <div className="score-strip">
        <span>状态 <TermHelp term="状态相似">比较当前时点各指标所处的位置是否接近。</TermHelp> {card.scores.state.toFixed(1)}</span>
        <span>轨迹 <TermHelp term="轨迹相似">比较此前一段时间上升、下降和变化速度是否接近。</TermHelp> {card.scores.trajectory.toFixed(1)}</span>
        <span className="missing">结构 <TermHelp term="结构比较">比较人口、信用和政策制度等慢变量；此卡尚未纳入。</TermHelp> 未评分</span>
      </div>
      <div className="comparison-grid">
        <ComparisonList title="主要相似" rows={card.main_similarities} />
        <ComparisonList title="关键差异" rows={card.main_differences} />
        <div><h3>历史后续路径</h3><p className="path-number">{card.subsequent_path.six_month_average_cpi_change > 0 ? "+" : ""}{card.subsequent_path.six_month_average_cpi_change.toFixed(3)}</p><small>之后6个月平均CPI相对变化</small></div>
      </div>
      <p className="card-warning">{card.comparability_warning} 不可据此直接推断当前未来路径。</p>
    </details>
  );
}

function formatSigned(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
}

function ComparisonList({ title, rows }: { title: string; rows: Comparison[] }) {
  return <div><h3>{title}</h3><ul className="comparison-list">{rows.map((row) => <li key={row.subtheme}><span>{labels[row.subtheme]}</span><strong>差 {row.absolute_gap.toFixed(1)}</strong></li>)}</ul></div>;
}
