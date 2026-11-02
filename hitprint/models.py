from dataclasses import dataclass, field


@dataclass
class Video:
    id: str
    title: str
    views: int | None
    duration: float | None
    upload_date: str | None  # YYYYMMDD
    url: str | None = None
    path: str | None = None
    stayed_pct: float | None = None
    features: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class Rule:
    feature: str
    text: str
    better: str
    worse: str
    n_better: int
    n_worse: int
    median_better: float
    median_worse: float
    ratio: float
    confidence: float
    fixable: bool
    advice: str  # the better side as direct advice, e.g. "Keep it under 25 seconds"
