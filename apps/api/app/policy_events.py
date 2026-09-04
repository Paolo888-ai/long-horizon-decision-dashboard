from collections import Counter

POLICY_EVENTS = [
    {
        "id": "CN-2015-DEPOSIT-RATE-LIBERALIZATION",
        "geography": "CN",
        "event_date": "2015-10-24",
        "category": "interest_rate_framework",
        "title": "取消存款利率浮动上限",
        "direction": "more_market_based",
        "coding_reason": "行政利率管制基本放开，金融机构存款定价自主性提高。",
        "source_url": "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125960/126052/4213321/8137cbbd5934477ea7d76bb154ab6526/2020091516563165419.pdf",
        "source_provider": "中国人民银行",
        "reviewers": ["research_editor"],
    },
    {
        "id": "CN-2019-LPR-REFORM",
        "geography": "CN",
        "event_date": "2019-08-17",
        "category": "policy_transmission",
        "title": "改革完善贷款市场报价利率形成机制",
        "direction": "stronger_market_transmission",
        "coding_reason": "推动贷款利率两轨合一，提高政策利率向贷款定价的传导效率。",
        "source_url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212550010243/index.html",
        "source_provider": "中国人民银行",
        "reviewers": ["research_editor"],
    },
    {
        "id": "CN-2024-PRIMARY-POLICY-RATE",
        "geography": "CN",
        "event_date": "2024-07-22",
        "category": "operating_target",
        "title": "强化7天期逆回购利率的主要政策利率属性",
        "direction": "clearer_price_target",
        "coding_reason": "由数量与多重价位招标转向更清晰的价格型政策信号。",
        "source_url": "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/5347949/afbfa5df25ee45889d916a2819b60a43/2024110815410752868.pdf",
        "source_provider": "中国人民银行",
        "reviewers": ["research_editor"],
    },
    {
        "id": "JP-2013-QQE",
        "geography": "JP",
        "event_date": "2013-04-04",
        "category": "operating_target",
        "title": "引入量化与质化货币宽松（QQE）",
        "direction": "balance_sheet_easing",
        "coding_reason": "操作目标由隔夜利率转向基础货币，并扩大国债和风险资产购买。",
        "source_url": "https://www.boj.or.jp/en/mopo/outline/ref_qqe.htm",
        "source_provider": "日本银行",
        "reviewers": ["research_editor"],
    },
    {
        "id": "JP-2016-YCC",
        "geography": "JP",
        "event_date": "2016-09-21",
        "category": "yield_curve_framework",
        "title": "引入收益率曲线控制（YCC）",
        "direction": "direct_yield_curve_control",
        "coding_reason": "同时设定短期政策利率和长期利率操作目标。",
        "source_url": "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2016/k160921a.pdf",
        "source_provider": "日本银行",
        "reviewers": ["research_editor"],
    },
    {
        "id": "JP-2024-FRAMEWORK-NORMALIZATION",
        "geography": "JP",
        "event_date": "2024-03-19",
        "category": "interest_rate_framework",
        "title": "结束负利率与YCC框架",
        "direction": "short_rate_primary_tool",
        "coding_reason": "短期利率重新成为主要政策工具，QQE with YCC 完成其角色。",
        "source_url": "https://www.boj.or.jp/en/mopo/mpmdeci/state_2024/k240319a.htm",
        "source_provider": "日本银行",
        "reviewers": ["research_editor"],
    },
]


def build_policy_evidence() -> dict:
    events = []
    for event in POLICY_EVENTS:
        reviewers = event["reviewers"]
        events.append(
            {
                **event,
                "review_status": (
                    "approved" if len(set(reviewers)) >= 2 else "awaiting_second_review"
                ),
            }
        )
    approved = [event for event in events if event["review_status"] == "approved"]
    approved_by_country = Counter(event["geography"] for event in approved)
    approved_categories = {event["category"] for event in approved}
    gate_passed = (
        approved_by_country["CN"] >= 2
        and approved_by_country["JP"] >= 2
        and len(approved_categories) >= 2
    )
    return {
        "version": "policy-event-codebook-v0.1",
        "score_allowed": gate_passed,
        "approval_rule": "two distinct reviewers per event",
        "scoring_gate": {
            "minimum_approved_events_per_country": 2,
            "minimum_shared_categories": 2,
            "approved_cn": approved_by_country["CN"],
            "approved_jp": approved_by_country["JP"],
            "approved_shared_categories": len(approved_categories),
            "passed": gate_passed,
        },
        "events": events,
    }
