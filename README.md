# 长期环境决策看板

> Recommended repository name: `long-horizon-decision-dashboard`

一个面向职业与技能选择的宏观环境研究工具，把周期状态、情景概率、历史相似期和中美日结构性证据放在同一块看板中，帮助用户形成可复盘的决策记录。

本项目是研究与决策辅助工具，不是投资建议，也不承诺准确预测未来；相似期仅作参考。

## 快速开始

要求：Node.js 20+、pnpm 10.x、Python 3.10+。

```powershell
pnpm install
Copy-Item .env.example .env
& .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
# 新终端
pnpm --dir apps/web dev
```

打开 `http://localhost:3000`；API 默认 `http://localhost:8000`。SQLite 数据库、raw 数据和本地环境变量均不会提交。

## 验证

```powershell
pnpm --dir apps/web lint
pnpm --dir apps/web test -- --run
pnpm --dir apps/web build
& .venv\Scripts\python.exe -m pytest apps/api/tests -q
```

## 项目结构

`apps/web` 为 Next.js 前端，`apps/api` 为 FastAPI 与评分逻辑，`docs` 保存迭代/质量/回测说明，`PRD-v1.0.md` 与 `01-08*.md` 保存产品和方法文档。

数据优先采用 World Bank、BOJ、PBC、NBS/e-Stat 等官方免费来源。月度 cutoff 为北京时间每月 15 日 23:59，20 日发布；历史回测遵守 vintage 防泄漏约束。模型负责人提出概率调整，产品负责人批准并留痕。

## 当前文档集

| 顺序 | 文档 | 状态 |
|---:|---|---|
| 0 | [PRD v1.0](PRD-v1.0.md) | 已加入中国、美国、日本、全球四视角，待最终评审 |
| 1 | [MVP 指标数据字典 v0.1](01-MVP指标数据字典-v0.1.md) | 40 个核心指标、5 个事件指标 |
| 2 | [状态与周期评分规则 v0.1](02-状态与周期评分规则-v0.1.md) | 透明基线规则 |
| 3 | [历史相似期算法说明 v0.1](03-历史相似期算法说明-v0.1.md) | 算法与防泄漏规则 |
| 4 | [低保真原型 v0.1](04-低保真原型-v0.1.md) | 首页、历史镜像列表及详情 |
| 5 | [三个历史时间点手工回测样例 v0.1](05-三个历史时间点手工回测样例-v0.1.md) | 日、美、中三个定性样例 |
| 6 | [数据源、授权和成本清单 v0.1](06-数据源授权和成本清单-v0.1.md) | 核实日期 2026-08-15 |
| 7 | [技术架构与开发排期 v0.1](07-技术架构与开发排期-v0.1.md) | 推荐架构及 12 周计划 |
| 8 | [开工决策单 v1.0](08-开工决策单-v1.0.md) | 七项开工选择及推荐组合 |

## 已确认

- 产品采用概率和情景表达，不承诺精确预测；
- MVP 覆盖中国、美国、日本和全球；
- 通过滚动回测逐步增加数据和因子；
- 历史预测档案不可被后续模型覆盖。
- 产品名：长期环境决策看板；
- 第一优先场景：职业与技能选择；
- MVP 不设账户，画像仅保存在用户本地；
- 使用官方免费数据，暂不采购商业数据库；
- 使用 Next.js + FastAPI + PostgreSQL，部署为云端私测版；
- 北京时间每月 15 日 23:59 截止数据，20 日发布；
- 情景概率调整由模型负责人提出、产品负责人批准。

完整记录见[开工决策单](08-开工决策单-v1.0.md)。

## 推荐下一步

第一开发迭代已经启动。代码位于 `apps/web` 与 `apps/api`，本地运行方法见 [开发说明](docs/development.md)。

当前完成情况见[第一开发迭代记录](docs/iteration-01.md)。

首次真实数据接入结果见[数据质量报告 v0.1](docs/data-quality-v0.1.md)。

数据管道实现情况见[第二开发迭代记录](docs/iteration-02.md)。

月频特征与高频覆盖情况见[第三开发迭代记录](docs/iteration-03.md)和[数据质量报告 v0.2](docs/data-quality-v0.2.md)。

财政部高频接入、指标详情页及滚动 cutoff 测试见[第四开发迭代记录](docs/iteration-04.md)和[数据质量报告 v0.3](docs/data-quality-v0.3.md)。

国家统计局正式发布页接入及双质量门见[第五开发迭代记录](docs/iteration-05.md)和[数据质量报告 v0.4](docs/data-quality-v0.4.md)。

中美历史回补和只读实验环境 API 见[第六开发迭代记录](docs/iteration-06.md)和[数据质量报告 v0.5](docs/data-quality-v0.5.md)。

严格 vintage 回测与首轮模型门结果见[第七开发迭代记录](docs/iteration-07.md)和[中国通胀回测 v0.1](docs/backtest-cn-inflation-v0.1.md)。

核心 CPI、子主题聚合和平滑对照回测见[第八开发迭代记录](docs/iteration-08.md)和[中国通胀回测 v0.2](docs/backtest-cn-inflation-v0.2.md)。

消费品、服务与生产价格三子主题回测见[第九开发迭代记录](docs/iteration-09.md)和[中国通胀回测 v0.3](docs/backtest-cn-inflation-v0.3.md)。
