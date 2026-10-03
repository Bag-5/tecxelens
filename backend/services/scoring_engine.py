WEIGHT_MAP = {
    "critical": 30,
    "high": 20,
    "medium": 10,
    "low": 5,
}

RISK_LEVELS: list[tuple[int, str]] = [
    (90, "Excellent"),
    (75, "Good"),
    (50, "Medium"),
    (25, "Poor"),
    (0, "Critical"),
]


def compute_score(findings: list[dict]) -> dict:
    penalty = sum(WEIGHT_MAP.get(f["severity"], 0) for f in findings)
    overall_score = max(0, min(100, 100 - penalty))

    risk_level = "Critical"
    for threshold, label in RISK_LEVELS:
        if overall_score >= threshold:
            risk_level = label
            break

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
    }


# Link exposure is scored separately and deliberately does not share
# WEIGHT_MAP. Folding link reputation into compute_score would let a malicious
# link drag down a compliance number that is meant to describe how well a
# document satisfies a standard -- and that figure is the one a report is
# quoted on. Weights are steeper because a single confirmed malicious URL is a
# more concrete problem than a documentation-level control gap.
LINK_WEIGHT_MAP = {
    "critical": 40,
    "high": 25,
    "medium": 10,
    "low": 3,
}


def compute_link_risk(links: list[dict]) -> dict:
    """Score link exposure on the same 0-100 / band scale as compliance.

    Uses the same RISK_LEVELS bands and the same "higher is safer" direction so
    the existing score ring and report cover render correctly without changes.
    Only links with a real severity are counted; clean and unchecked links do
    not dilute the result.
    """
    penalty = sum(LINK_WEIGHT_MAP.get(link.get("severity", ""), 0) for link in links)
    score = max(0, min(100, 100 - penalty))

    risk_level = "Critical"
    for threshold, label in RISK_LEVELS:
        if score >= threshold:
            risk_level = label
            break

    return {
        "overall_score": score,
        "risk_level": risk_level,
    }
