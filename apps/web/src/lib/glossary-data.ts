export type GlossaryEntry = {
  term: string;
  aliases: string[];
  plain: string;
  caution: string;
  category: string;
};

export const glossaryEntries: GlossaryEntry[] = [
  { term: "cutoff", aliases: ["截止线", "数据截止时间"], category: "数据", plain: "只允许使用这个时点之前已经公开的数据。", caution: "用于防止回测偷看未来。" },
  { term: "vintage", aliases: ["数据版本", "历史版本"], category: "数据", plain: "某个历史时点实际能看到的那一版数据。", caution: "终值历史可能经过修订，不能冒充实时回测。" },
  { term: "状态相似", aliases: ["state similarity"], category: "相似期", plain: "比较当前各指标所处位置是否接近某个历史时点。", caution: "只描述当下位置，不描述之后怎么走。" },
  { term: "轨迹相似", aliases: ["trajectory similarity"], category: "相似期", plain: "比较此前一段时间的方向和变化速度。", caution: "轨迹相似仍不保证未来路径相同。" },
  { term: "表面相似度", aliases: ["总相似度"], category: "相似期", plain: "把已纳入指标的状态与轨迹合成为一个易排序的分数。", caution: "不是历史重演概率。" },
  { term: "结构可比性", aliases: ["结构分"], category: "结构", plain: "比较人口、信用、预期口径和政策制度等慢变量。", caution: "结构接近也不代表经济结果必然一致。" },
  { term: "Jaccard稳定性", aliases: ["榜单稳定性", "Jaccard"], category: "回测", plain: "衡量相邻月份的相似期名单有多少重合。", caution: "接近1更稳定，接近0更敏感。" },
  { term: "中位数", aliases: ["median"], category: "统计", plain: "把结果排序后位于中间的值。", caution: "比平均数更少受极端值影响，但会隐藏分布宽度。" },
  { term: "置信度", aliases: ["confidence"], category: "证据", plain: "证据能够支持结论的强弱等级。", caution: "不是成功率，也不是情景概率。" },
  { term: "证据等级B", aliases: ["B级证据"], category: "证据", plain: "有官方数据和可复算方法，但缺少严格历史版本或前瞻验证。", caution: "只能用于辅助研究。" },
  { term: "滚动回测", aliases: ["walk-forward"], category: "回测", plain: "在多个历史时点重复模拟当时能够做出的判断。", caution: "比一次性拟合更接近真实使用，但仍不代表未来表现。" },
  { term: "情景概率", aliases: ["scenario probability"], category: "情景", plain: "模型在当前信息下分配给不同未来路径的相对权重。", caution: "不是承诺，也不能直接转换成个人行动比例。" },
  { term: "周期时钟", aliases: ["cycle clock"], category: "周期", plain: "描述库存、信用、人口、技术等机制各自所处阶段。", caution: "不同周期可能不同步。" },
  { term: "LPR", aliases: ["贷款市场报价利率"], category: "政策", plain: "中国银行贷款定价的重要参考基准。", caution: "LPR变化不等于所有借款人的实际利率同幅变化。" },
  { term: "QQE", aliases: ["量化与质化货币宽松"], category: "政策", plain: "既扩大央行资产购买规模，也改变购买资产期限和类型。", caution: "不能只用资产负债表规模判断政策效果。" },
  { term: "YCC", aliases: ["收益率曲线控制"], category: "政策", plain: "央行直接引导短期与长期利率处于目标附近。", caution: "目标区间和执行方式会随制度阶段变化。" },
  { term: "信用占GDP", aliases: ["私人信贷占GDP"], category: "信用", plain: "私人部门获得的国内信贷相对于经济规模的比例。", caution: "高比例不自动等于危机，也不等于当期信用脉冲。" },
  { term: "政策事件账本", aliases: ["事件编码"], category: "政策", plain: "逐条保存制度变化、官方来源、编码理由和审批状态。", caution: "事件选择带有判断，因此必须双人复核。" },
];

export function findGlossaryEntry(term: string) {
  const key = term.toLowerCase();
  return glossaryEntries.find((entry) => [entry.term, ...entry.aliases].some((value) => value.toLowerCase() === key));
}
