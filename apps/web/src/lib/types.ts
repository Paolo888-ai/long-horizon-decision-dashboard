export type Geography = "CN" | "US" | "JP" | "GLOBAL";

export type Confidence = "低" | "中" | "高";

export type DimensionState = {
  id: string;
  label: string;
  score: number;
  state: string;
  direction: "up" | "down" | "flat";
  confidence: Confidence;
};

export type CycleState = {
  label: string;
  state: string;
  trend: string;
};

export type Scenario = {
  label: string;
  oneYear: number;
  threeYear: number;
  longTerm: number;
};

export type Analog = {
  country: string;
  period: string;
  dataSimilarity: number;
  structuralComparability: number;
  confidence: Confidence;
};

export type Snapshot = {
  geography: Geography;
  geographyLabel: string;
  asOf: string;
  dataCompleteness: number;
  confidence: Confidence;
  summary: string;
  caveat: string;
  dimensions: DimensionState[];
  cycles: CycleState[];
  scenarios: Scenario[];
  analogs: Analog[];
  changes: string[];
  forks: string[];
  modelVersion: string;
  isSample: boolean;
};

