# 第十迭代：独立通胀预期信号

本迭代接入中国人民银行城镇储户问卷“物价预期指数”，完成PDF视觉核验、解析、严格 vintage 入库、质量报告和 v0.4 回测。

交付内容：

- `PbcDepositorSurveyConnector`：解析官方PDF季度表。
- `ingest-pbc-depositor`：要求显式传入带时区的正式发布时间。
- `/v1/backtests/cn-inflation-v4` 与对应 CLI。
- 4份官方PDF、52条快照观测及内容哈希审计链。
- v0.4结构稳定性门槛通过，但仍保持 `diagnostic_only`。

下一迭代建议：先定义预测目标（例如未来12个月 CPI 均值/方向），再做扩展窗口或滚动样本外验证，并与“永远预测不变”和简单自回归基线比较。
