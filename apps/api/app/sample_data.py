from copy import deepcopy

from .schemas import Analog, CycleState, DimensionState, Scenario, Snapshot

DIMENSIONS = [
    DimensionState(
        id="technology", label="技术", score=64, state="商业扩散", direction="up", confidence="中"
    ),
    DimensionState(
        id="real", label="实体", score=12, state="修复", direction="flat", confidence="中"
    ),
    DimensionState(
        id="credit", label="信用", score=-28, state="紧缩缓和", direction="up", confidence="中"
    ),
    DimensionState(
        id="inflation", label="通胀", score=-10, state="温和", direction="flat", confidence="中"
    ),
    DimensionState(
        id="demography", label="人口", score=-67, state="收缩", direction="flat", confidence="高"
    ),
    DimensionState(
        id="geopolitics", label="地缘", score=-42, state="碎片化", direction="down", confidence="中"
    ),
]

CYCLES = [
    CycleState(label="库存周期", state="被动去库", trend="修复"),
    CycleState(label="设备信用周期", state="紧缩", trend="修复"),
    CycleState(label="人口建设周期", state="供给成熟", trend="调整"),
    CycleState(label="技术产业长波", state="投资爆发", trend="商业扩散"),
    CycleState(label="个人生命周期", state="等待画像", trend="未评估"),
]

SCENARIOS = [
    Scenario(label="生产扩张", one_year=35, three_year=38, long_term=42),
    Scenario(label="温和调整", one_year=40, three_year=32, long_term=25),
    Scenario(label="滞胀", one_year=15, three_year=18, long_term=18),
    Scenario(label="信用收缩", one_year=10, three_year=12, long_term=15),
]

ANALOGS = [
    Analog(
        country="日本",
        period="1987—1989",
        data_similarity=74,
        structural_comparability=49,
        confidence="低",
    ),
    Analog(
        country="美国",
        period="1994—1997",
        data_similarity=70,
        structural_comparability=62,
        confidence="中",
    ),
    Analog(
        country="中国",
        period="2013—2015",
        data_similarity=68,
        structural_comparability=77,
        confidence="中",
    ),
]

SUMMARIES = {
    "CN": ("中国", "技术扩散增强 × 信用仍受约束 × 人口长期承压"),
    "US": ("美国", "技术资本开支较强 × 金融条件约束 × 增长韧性待验证"),
    "JP": ("日本", "工资与价格制度变化 × 人口收缩 × 货币环境正常化"),
    "GLOBAL": ("全球", "技术扩散 × 信用与财政分化 × 供应链区域化"),
}


def get_sample_snapshot(geography: str) -> Snapshot:
    geography_label, summary = SUMMARIES[geography]
    return Snapshot(
        geography=geography,
        geography_label=geography_label,
        as_of="样例快照",
        data_completeness=87,
        confidence="中",
        summary=summary,
        caveat="当前响应只验证接口与信息结构，所有数值均为样例。",
        dimensions=deepcopy(DIMENSIONS),
        cycles=deepcopy(CYCLES),
        scenarios=deepcopy(SCENARIOS),
        analogs=deepcopy(ANALOGS),
        changes=["技术资本开支信号增强", "信用压力边际缓和", "外部贸易限制风险上升"],
        forks=["生产率是否连续改善", "居民与企业信贷是否恢复", "通胀是否限制政策空间"],
        model_version="sample-v0.1",
        is_sample=True,
    )
