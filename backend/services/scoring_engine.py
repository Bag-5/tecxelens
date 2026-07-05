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
