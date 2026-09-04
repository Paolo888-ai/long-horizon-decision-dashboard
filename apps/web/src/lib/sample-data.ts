import type { Geography, Snapshot } from "./types";

const dimensions = [
  { id: "technology", label: "技术", score: 64, state: "商业扩散", direction: "up" as const, confidence: "中" as const },
  { id: "real", label: "实体", score: 12, state: "修复", direction: "flat" as const, confidence: "中" as const },
  { id: "credit", label: "信用", score: -28, state: "紧缩缓和", direction: "up" as const, confidence: "中" as const },
  { id: "inflation", label: "通胀", score: -10, state: "温和", direction: "flat" as const, confidence: "中" as const },
  { id: "demography", label: "人口", score: -67, state: "收缩", direction: "flat" as const, confidence: "高" as const },
  { id: "geopolitics", label: "地缘", score: -42, state: "碎片化", direction: "down" as const, confidence: "中" as const },
];

const common = {
  asOf: "样例快照",
  dataCompleteness: 87,
  confidence: "中" as const,
  summary: "技术扩散增强 × 信用仍受约束 × 人口长期承压",
  caveat: "这不是单一的繁荣或衰退状态。当前页面仅验证信息结构，所有数值均为样例。",
  dimensions,
  cycles: [
    { label: "库存周期", state: "被动去库", trend: "修复" },
    { label: "设备信用周期", state: "紧缩", trend: "修复" },
    { label: "人口建设周期", state: "供给成熟", trend: "调整" },
    { label: "技术产业长波", state: "投资爆发", trend: "商业扩散" },
    { label: "个人生命周期", state: "等待画像", trend: "未评估" },
  ],
  scenarios: [
    { label: "生产扩张", oneYear: 35, threeYear: 38, longTerm: 42 },
    { label: "温和调整", oneYear: 40, threeYear: 32, longTerm: 25 },
    { label: "滞胀", oneYear: 15, threeYear: 18, longTerm: 18 },
    { label: "信用收缩", oneYear: 10, threeYear: 12, longTerm: 15 },
  ],
  analogs: [
    { country: "日本", period: "1987—1989", dataSimilarity: 74, structuralComparability: 49, confidence: "低" as const },
    { country: "美国", period: "1994—1997", dataSimilarity: 70, structuralComparability: 62, confidence: "中" as const },
    { country: "中国", period: "2013—2015", dataSimilarity: 68, structuralComparability: 77, confidence: "中" as const },
  ],
  changes: ["技术资本开支信号增强", "信用压力边际缓和", "外部贸易限制风险上升"],
  forks: ["生产率是否连续改善", "居民与企业信贷是否恢复", "通胀是否限制政策空间"],
  modelVersion: "sample-v0.1",
  isSample: true,
};

export const snapshots: Record<Geography, Snapshot> = {
  CN: { ...common, geography: "CN", geographyLabel: "中国" },
  US: { ...common, geography: "US", geographyLabel: "美国", summary: "技术资本开支较强 × 金融条件约束 × 增长韧性待验证" },
  JP: { ...common, geography: "JP", geographyLabel: "日本", summary: "工资与价格制度变化 × 人口收缩 × 货币环境正常化" },
  GLOBAL: { ...common, geography: "GLOBAL", geographyLabel: "全球", summary: "技术扩散 × 信用与财政分化 × 供应链区域化" },
};

