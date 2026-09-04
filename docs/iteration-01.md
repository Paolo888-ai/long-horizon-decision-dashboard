# 第一开发迭代记录

## 状态

启动日期：2026-08-15  
当前状态：基础骨架完成，等待正式数据连接器开发。

## 已完成

- Next.js 16 App Router + TypeScript 前端；
- 中国、美国、日本、全球四视角切换；
- 六维状态、五周期、情景、历史镜像、变化与分叉首屏；
- 全站样例数据标识，避免被误认为正式判断；
- FastAPI 样例 API 和 OpenAPI 文档；
- 七张 SQLAlchemy 2 核心数据表；
- 北京时间每月 15 日 23:59 cutoff 规则；
- 本地 `.venv` 和 pnpm 锁文件；
- 前后端基础测试和生产构建验证。

## 验证结果

| 检查 | 结果 |
|---|---|
| 前端 ESLint | 通过 |
| 前端 Vitest | 3/3 通过 |
| Next.js 生产构建 | 通过 |
| Python Ruff | 通过 |
| API/Python pytest | 7/7 通过；第三方 TestClient 有 1 条弃用警告 |
| SQLAlchemy 表注册 | 7/7 通过 |

## 当前非阻塞问题

- FastAPI 测试栈提示 Starlette `TestClient` 与 `httpx` 的未来迁移警告，当前测试有效；
- 当前沙箱允许读取但不允许更新 `.git` 元数据，因此仓库仍显示初始 `master`，未执行提交；
- pnpm 使用工作区批准列表允许 `sharp` 构建脚本，其他依赖脚本仍默认不受信任；
- 正式 PostgreSQL 和云环境尚未启动。

## 下一迭代

1. 建立 source registry 和 indicator definition 种子数据；
2. 实现 FRED/ALFRED、OECD、日本 e-Stat/BOJ 和中国官方数据的首批连接器；
3. 每个视角接入至少两个真实指标；
4. 保存原始响应、vintage、哈希和来源授权元数据；
5. 生成第一份数据质量报告；
6. 用真实指标替换首页的部分样例数字，但在覆盖不足前保持“实验数据”标签。
