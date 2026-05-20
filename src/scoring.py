from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoredEvent:
    event: dict
    score: int
    grade: str
    matched_positive: list[str]
    matched_negative: list[str]
    reason: list[str]


def score_event(event: dict, rules: dict, company_cfg: dict) -> ScoredEvent:
    text = " ".join(
        [
            event.get("title", ""),
            event.get("raw", {}).get("summary", ""),
            company_cfg.get("name", ""),
        ]
    ).lower()

    score = rules["source_weights"].get(event["source"], 0)
    reasons = [f"source={event['source']}"]
    positive = []
    negative = []

    aliases = [a.lower() for a in company_cfg.get("aliases", []) if a]
    if event["source"] == "GOOGLE_NEWS":
        if aliases and any(alias in text for alias in aliases):
            score += 12
            reasons.append("alias_match")
        elif aliases:
            score -= 60
            reasons.append("alias_mismatch")

    required = [k.lower() for k in company_cfg.get("require_keywords_any", []) if k]
    if event["source"] == "GOOGLE_NEWS":
        if required and any(k in text for k in required):
            score += 10
            reasons.append("context_match")
        elif required:
            score -= 35
            reasons.append("context_mismatch")

    excluded = [k.lower() for k in company_cfg.get("exclude_keywords", []) if k]
    hit_excluded = [k for k in excluded if k in text]
    if hit_excluded:
        score -= 80
        negative.extend(hit_excluded)
        reasons.append("excluded=" + ",".join(hit_excluded[:5]))

    for keyword, weight in rules.get("positive_keywords", {}).items():
        if keyword.lower() in text:
            score += int(weight)
            positive.append(keyword)

    for keyword, weight in rules.get("negative_keywords", {}).items():
        if keyword.lower() in text:
            score += int(weight)
            negative.append(keyword)

    if event["source"] == "DART" and any(k in positive for k in ["공급계약", "단일판매", "수주", "실적"]):
        score += 12
        reasons.append("dart_high_signal")

    if positive:
        reasons.append("positive=" + ",".join(positive[:5]))
    if negative:
        reasons.append("negative=" + ",".join(negative[:5]))

    thresholds = rules["thresholds"]
    if score >= thresholds["P1"]:
        grade = "P1"
    elif score >= thresholds["P2"]:
        grade = "P2"
    elif score >= thresholds["P3"]:
        grade = "P3"
    else:
        grade = "P4"

    return ScoredEvent(event=event, score=score, grade=grade, matched_positive=positive, matched_negative=negative, reason=reasons)
