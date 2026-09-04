"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { InterpretationPanel, TermHelp } from "@/components/term-help";

type Candidate = {
  geography: "JP";
  historical_month: string;
  total_similarity: number;
  state_similarity: number;
  trajectory_similarity: number;
  subsequent_six_month_cpi_change: number;
};

type CrossCountryResponse = {
  target_month?: string;
  claim_status: "retrospective_diagnostic_only";
  readiness: "fail";
  readiness_reasons: string[];
  comparable_subthemes?: string[];
  expectation_context?: {
    included_in_analog_ranking: boolean;
    reason: string;
    china: { latest_month: string; latest_value: number; respondents: string; unit: string } | null;
    japan: { latest_month: string; latest_value: number; respondents: string; unit: string } | null;
  };
  structural_comparability?: {
    score: number | null;
    coverage: string;
    confidence: "low";
    included_in_surface_similarity: boolean;
    components: Array<{
      id: string; score: number | null; status: string; reason?: string;
      china_percent_gdp?: number; japan_percent_gdp?: number;
      china_five_year_change_pp?: number; japan_five_year_change_pp?: number;
    }>;
  };
  policy_evidence?: {
    version: string;
    score_allowed: boolean;
    approval_rule: string;
    scoring_gate: { approved_cn: number; approved_jp: number; minimum_approved_events_per_country: number; passed: boolean };
    events: Array<{
      id: string; geography: "CN" | "JP"; event_date: string; category: string;
      title: string; coding_reason: string; source_url: string; source_provider: string;
      review_status: "approved" | "awaiting_second_review";
    }>;
  };
  candidates: Candidate[];
};

export function CrossCountryEvidence() {
  const [data, setData] = useState<CrossCountryResponse | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${baseUrl}/v1/research/cn-jp-inflation-similarity`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Cross-country API unavailable");
        return response.json() as Promise<CrossCountryResponse>;
      })
      .then(setData)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setOffline(true);
      });
    return () => controller.abort();
  }, []);

  return (
    <section className="cross-country-section" aria-labelledby="cross-country-title">
      <div className="evidence-divider">
        <span>证据层 B <TermHelp term="证据等级B">有官方数据和可复算方法，但缺少严格历史版本或前瞻验证，只能用于辅助研究。</TermHelp></span>
        <i />
        <strong>回顾性跨国比较</strong>
      </div>
      <header className="cross-country-intro panel">
        <div>
          <p className="eyebrow">Retrospective comparison · 日本参考国</p>
          <h2 id="cross-country-title">相似时期可以参考，但不是回测预测</h2>
          <p>日本长历史来自当前接续后的终值表，不包含每个月当时可见的历史版本。因此它只能回答“形态像什么”，不能证明“接下来会怎样”。</p>
        </div>
        <div className="evidence-grade"><span>证据等级</span><strong>B</strong><small>禁止并入预测概率</small></div>
      </header>

      {offline && <div className="research-state error">跨国比较 API 未连接。</div>}
      {!offline && !data && <div className="research-state">正在读取日本长期历史…</div>}
      {data && (
        <>
          <div className="retrospective-warning">
            <strong>终值历史 · 非严格 vintage <TermHelp term="vintage">数据在某个历史时点实际可见的版本。非严格 vintage 表示目前使用的是后来修订后的历史序列。</TermHelp></strong>
            <ul>{data.readiness_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </div>
          <div className="jp-candidate-grid">
            {data.candidates.map((candidate, index) => (
              <article className="jp-candidate panel" key={candidate.historical_month}>
                <div className="candidate-heading"><span>0{index + 1} · 日本</span><strong>{candidate.total_similarity.toFixed(1)}</strong></div>
                <h3>{candidate.historical_month.slice(0, 7)}</h3>
                <dl>
                  <div><dt>状态相似 <TermHelp term="状态相似">当前指标位置与历史时点有多接近。</TermHelp></dt><dd>{candidate.state_similarity.toFixed(1)}</dd></div>
                  <div><dt>轨迹相似 <TermHelp term="轨迹相似">过去六个月的变化方向和速度有多接近。</TermHelp></dt><dd>{candidate.trajectory_similarity.toFixed(1)}</dd></div>
                </dl>
                <div className="jp-path">
                  <span>事后六个月路径</span>
                  <strong>{candidate.subsequent_six_month_cpi_change > 0 ? "+" : ""}{candidate.subsequent_six_month_cpi_change.toFixed(3)}</strong>
                  <small>个百分点；只作多路径参考</small>
                </div>
              </article>
            ))}
          </div>
          {data.structural_comparability && (
            <section className="structure-panel panel">
              <div className="structure-score">
                <span>结构可比性 <TermHelp term="结构可比性">衡量人口、预期口径、信用和政策制度等慢变量是否相近，不等于经济走势相同。</TermHelp></span>
                <strong>{data.structural_comparability.score?.toFixed(1) ?? "—"}</strong>
                <small>覆盖 {data.structural_comparability.coverage} · 低置信</small>
              </div>
              <div>
                <h3>结构分数不参与表面相似度</h3>
                <p>人口趋势、预期测量方式和同口径年度信贷结构已评分；政策制度仍缺数据。结构分数只作解释，不重排历史候选。</p>
                <ul className="structure-components">
                  {data.structural_comparability.components.map((component) => (
                    <li key={component.id}>
                      <span>{structureLabels[component.id] ?? component.id}</span>
                      <strong>{component.score === null ? "缺失" : component.score.toFixed(1)}</strong>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          {data.structural_comparability && (
            <InterpretationPanel>
              <StructureInterpretation data={data.structural_comparability} />
            </InterpretationPanel>
          )}
          {data.expectation_context?.japan && (
            <p className="expectation-note">新增日本企业一年期总体物价预期：{data.expectation_context.japan.latest_value.toFixed(1)}%（{data.expectation_context.japan.latest_month.slice(0, 7)}）。因调查对象与中国居民预期不同且历史始于 2014 年，本轮不纳入历史候选排名。</p>
          )}
          {data.policy_evidence && (
            <section className="policy-evidence panel" aria-labelledby="policy-evidence-title">
              <div className="policy-evidence-heading">
                <div><span>政策事件账本 <TermHelp term="政策事件账本">把重要制度变化逐条记录，并保留来源、编码理由和审批状态。</TermHelp></span><h3 id="policy-evidence-title">先审计，再评分</h3></div>
                <strong>{data.policy_evidence.score_allowed ? "可评分" : "评分锁定"}</strong>
              </div>
              <p>每个事件需两名不同角色复核；当前中日已批准 {data.policy_evidence.scoring_gate.approved_cn}/{data.policy_evidence.scoring_gate.approved_jp} 条，未达到每国至少 {data.policy_evidence.scoring_gate.minimum_approved_events_per_country} 条的门槛。</p>
              <div className="policy-timeline">
                {data.policy_evidence.events.map((event) => (
                  <article key={event.id}>
                    <time>{event.event_date}</time>
                    <span>{event.geography === "CN" ? "中国" : "日本"} · {policyCategoryLabels[event.category] ?? event.category}</span>
                    <h4>{event.title}{policyTermHelp[event.id]}</h4>
                    <p>{event.coding_reason}</p>
                    <a href={event.source_url} target="_blank" rel="noreferrer">{event.source_provider}原文 ↗</a>
                    <small>{event.review_status === "approved" ? "双人已批准" : "等待第二复核人"}</small>
                  </article>
                ))}
              </div>
            </section>
          )}
          <p className="cross-country-footnote">当前中国锚点：{data.target_month?.slice(0, 7)} · 可比子主题：商品、服务、生产者价格 · 结果状态：未通过预测使用门槛</p>
        </>
      )}
    </section>
  );
}

const structureLabels: Record<string, string> = {
  working_age_population_trend: "劳动年龄人口趋势",
  inflation_expectation_measure: "通胀预期测量方式",
  credit_regime: "信用环境",
  policy_institution_regime: "政策与制度环境",
};

const policyCategoryLabels: Record<string, string> = {
  interest_rate_framework: "利率框架",
  policy_transmission: "政策传导",
  operating_target: "操作目标",
  yield_curve_framework: "收益率曲线框架",
};

const policyTermHelp: Record<string, ReactNode> = {
  "CN-2019-LPR-REFORM": <TermHelp term="LPR">贷款市场报价利率，是中国银行贷款定价的重要参考基准。</TermHelp>,
  "JP-2013-QQE": <TermHelp term="QQE">量化与质化货币宽松：既扩大央行资产购买规模，也改变购买资产的期限和类型。</TermHelp>,
  "JP-2016-YCC": <TermHelp term="YCC">收益率曲线控制：央行直接引导短期与长期利率处于目标附近。</TermHelp>,
};

function StructureInterpretation({ data }: { data: NonNullable<CrossCountryResponse["structural_comparability"]> }) {
  const credit = data.components.find((component) => component.id === "credit_regime");
  return <>
    <p>结构总分 {data.score?.toFixed(1) ?? "—"} 只覆盖 {data.coverage} 个维度，所以仍是低置信参考。</p>
    {credit?.china_percent_gdp !== undefined && <p>2024年信贷占GDP：中国 {credit.china_percent_gdp.toFixed(1)}%，日本 {credit.japan_percent_gdp?.toFixed(1)}%；但近五年中国增加 {credit.china_five_year_change_pp?.toFixed(1)} 个百分点，日本增加 {credit.japan_five_year_change_pp?.toFixed(1)} 个百分点。含义是“存量接近、扩张速度不同”，不能简化为两国处于同一周期。</p>}
  </>;
}
