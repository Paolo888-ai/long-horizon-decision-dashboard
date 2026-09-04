"use client";

import { useEffect, useState } from "react";

import { TermHelp } from "@/components/term-help";

type QualityReport = {
  generated_at: string;
  active_indicator_count: number;
  indicators_with_observations: number;
  coverage_percent: number;
  observation_vintage_count: number;
  raw_asset_count: number;
  feature_row_count: number;
  indicators_with_features: number;
  high_frequency_coverage: Record<string, { defined: number; observed: number; percent: number }>;
  high_frequency_history_months: Record<string, number>;
  experimental_scoring_ready: boolean;
  readiness_reasons: string[];
  status: "pass" | "incomplete";
};

type LoadState =
  | { status: "loading" }
  | { status: "offline" }
  | { status: "ready"; report: QualityReport };

export function DataStatus() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${baseUrl}/v1/data-quality`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Data quality API unavailable");
        return response.json() as Promise<QualityReport>;
      })
      .then((report) => setState({ status: "ready", report }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "offline" });
      });
    return () => controller.abort();
  }, []);

  if (state.status === "loading") {
    return <p className="data-status-note">正在读取本地数据质量状态…</p>;
  }
  if (state.status === "offline") {
    return (
      <p className="data-status-note">
        数据 API 未连接。看板继续显示样例状态；启动 API 后可查看真实采集覆盖。
      </p>
    );
  }

  const { report } = state;
  return (
    <section className="panel data-status" aria-label="真实数据接入状态">
      <div className="section-heading">
        <h2>真实数据接入 <TermHelp term="真实数据接入">统计已经从官方或可审计来源采集并保存的指标，不包含首页样例值。</TermHelp></h2>
        <span className={report.status === "pass" ? "status-pass" : "status-incomplete"}>
          {report.status === "pass" ? "种子质量门通过" : "覆盖尚不完整"}
        </span>
      </div>
      <div className="data-metrics">
        <div><strong>{report.indicators_with_observations}/{report.active_indicator_count}</strong><span>有真实观测</span></div>
        <div><strong>{report.coverage_percent}%</strong><span>种子覆盖率 <TermHelp term="种子覆盖率">MVP 指标字典中已有真实观测的指标比例。</TermHelp></span></div>
        <div><strong>{report.indicators_with_features}</strong><span>已生成月频特征</span></div>
        <div><strong>{report.feature_row_count.toLocaleString()}</strong><span>特征记录</span></div>
      </div>
      <div className="coverage-row" aria-label="各视角高频覆盖">
        {(["CN", "US", "JP"] as const).map((geography) => {
          const labels = { CN: "中国", US: "美国", JP: "日本" };
          const coverage = report.high_frequency_coverage[geography];
          return (
            <span key={geography}>
              {labels[geography]}高频 {coverage?.observed ?? 0}/{coverage?.defined ?? 0}
            </span>
          );
        })}
      </div>
      <p className="data-status-note">
        {report.experimental_scoring_ready
          ? "数据已达到实验评分最低门槛，但仍需滚动回测后才会影响上方判断。"
          : `接入门与评分门相互独立。当前历史长度：中国 ${report.high_frequency_history_months.CN ?? 0} 个月、美国 ${report.high_frequency_history_months.US ?? 0} 个月、日本 ${report.high_frequency_history_months.JP ?? 0} 个月；暂不生成实验评分。`}
      </p>
    </section>
  );
}
