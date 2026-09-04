"use client";

import Link from "next/link";
import { useState } from "react";
import { DataStatus } from "./data-status";
import { ResearchProgress } from "./research-progress";
import { TermHelp } from "./term-help";
import { snapshots } from "@/lib/sample-data";
import type { Geography } from "@/lib/types";

const arrows = { up: "↑", down: "↓", flat: "→" };

export function Dashboard() {
  const [geography, setGeography] = useState<Geography>("CN");
  const snapshot = snapshots[geography];

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">LONG HORIZON</p>
          <h1>长期环境决策看板</h1>
          <p className="subtitle">技术、信用、人口与历史周期分析</p>
        </div>
        <nav aria-label="地区视角">
          {(Object.keys(snapshots) as Geography[]).map((key) => (
            <button key={key} className={key === geography ? "active" : ""} onClick={() => setGeography(key)}>
              {snapshots[key].geographyLabel}
            </button>
          ))}
        </nav>
      </header>

      <div className="sample-banner">上方周期结论仍为样例 <TermHelp term="样例快照">用于验证界面和决策流程的演示数据，不是模型对当前环境的正式判断。</TermHelp> · 下方“真实研究进展”来自已接入数据</div>

      <section className="hero panel">
        <div className="hero-meta">
          <span>{snapshot.geographyLabel} · {snapshot.asOf}</span>
          <span>数据完整度 <TermHelp term="数据完整度">计划使用的指标中，当前具备合格数据的比例。</TermHelp> {snapshot.dataCompleteness}% · 综合置信度：{snapshot.confidence}</span>
        </div>
        <p className="eyebrow">当前环境</p>
        <h2>{snapshot.summary}</h2>
        <p>{snapshot.caveat}</p>
      </section>

      <DataStatus />
      <ResearchProgress />

      <section className="panel">
        <div className="section-heading"><h2>六维状态 <TermHelp term="六维状态">从技术、信用、人口、通胀、实体经济和政策环境描述长期环境。</TermHelp></h2><span>分数范围 -100～+100 <TermHelp term="状态分数">负数偏弱或收缩，正数偏强或扩张；绝对值表示偏离中性的程度。</TermHelp></span></div>
        <div className="dimension-grid">
          {snapshot.dimensions.map((item) => (
            <article className="dimension" key={item.id}>
              <div className="dimension-title"><strong>{item.label}</strong><span>{item.score > 0 ? "+" : ""}{item.score}</span></div>
              <p>{item.state} <b>{arrows[item.direction]}</b></p>
              <small>置信度：{item.confidence}</small>
              <div className="bar"><i style={{ width: `${Math.abs(item.score)}%` }} /></div>
            </article>
          ))}
        </div>
      </section>

      <div className="two-column">
        <section className="panel">
          <div className="section-heading"><h2>五个周期时钟 <TermHelp term="周期时钟">不同经济机制各自所处的阶段；它们不一定同步转折。</TermHelp></h2><span>彼此独立</span></div>
          <div className="cycle-list">
            {snapshot.cycles.map((cycle) => (
              <div key={cycle.label}><strong>{cycle.label}</strong><span>{cycle.state} → {cycle.trend}</span></div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-heading"><h2>未来情景 <TermHelp term="情景分析">列出几条可能路径，而不是给出唯一预测。</TermHelp></h2><span>概率合计 100% <TermHelp term="情景概率">表达模型在给定信息下的相对权重，不等于保证发生。</TermHelp></span></div>
          <table>
            <thead><tr><th>情景</th><th>1年</th><th>3年</th><th>5～10年</th></tr></thead>
            <tbody>{snapshot.scenarios.map((scenario) => (
              <tr key={scenario.label}><td>{scenario.label}</td><td>{scenario.oneYear}%</td><td>{scenario.threeYear}%</td><td>{scenario.longTerm}%</td></tr>
            ))}</tbody>
          </table>
        </section>
      </div>

      <section className="panel">
        <div className="section-heading">
          <h2>历史镜像 <TermHelp term="历史镜像">寻找数据形态相似的历史时期，用来扩展参考路径，不表示历史会重复。</TermHelp></h2>
          <Link className="research-entry" href="/research/similarity">查看回测证据 →</Link>
        </div>
        <div className="analog-grid">
          {snapshot.analogs.map((analog) => (
            <article key={`${analog.country}-${analog.period}`}>
              <p className="eyebrow">{analog.country}</p>
              <h3>{analog.period}</h3>
              <dl><div><dt>数据相似</dt><dd>{analog.dataSimilarity}</dd></div><div><dt>结构可比</dt><dd>{analog.structuralComparability}</dd></div></dl>
              <p>综合可信度：{analog.confidence}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="two-column">
        <section className="panel"><div className="section-heading"><h2>本月最重要变化</h2></div><ol className="signal-list">{snapshot.changes.map((item) => <li key={item}>{item}</li>)}</ol></section>
        <section className="panel"><div className="section-heading"><h2>关键分叉</h2></div><ol className="signal-list">{snapshot.forks.map((item) => <li key={item}>{item}</li>)}</ol></section>
      </div>

      <section className="profile-callout">
        <div><p className="eyebrow">对我的意义</p><h2>先从职业与技能暴露开始</h2><p>画像仅保存在当前设备。首版不要求账户，也不收集精确资产数值。</p></div>
        <button disabled>个人画像 · 下一迭代</button>
      </section>

      <footer>模型 {snapshot.modelVersion} · 样例快照 · 概率化情景分析，不构成投资或其他专业建议。</footer>
    </main>
  );
}
