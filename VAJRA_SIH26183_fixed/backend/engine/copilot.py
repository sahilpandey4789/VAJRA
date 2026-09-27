"""
Investigation Copilot - a reasoning layer that narrates and acts on
signals the pipeline already computed for real (confidence_breakdown
from engine/scoring.py, the RandomForest's local explanation from
engine/ml_model.py, mixer/exchange/cross-case/pattern findings). It does
not call an LLM and does not invent a new probability estimate - every
line it produces traces back to a field already in the report, which is
the point: "explainable AI" here means every conclusion ships with the
specific evidence and the specific rule that produced it, not a plainer
sentence wrapped around the same black box.

next_steps() is a deterministic decision table keyed off
decision["action"] plus the specific flags present (mixer, cross-case
link, detected patterns) - again inspectable and testable, not
generated free-text.

Pure functions only, operating on an already-built report dict. Unit-
tested directly (tests/test_copilot.py), same convention as every other
engine/ module.
"""

CONFIDENCE_LABELS = [
    (0.75, "High"),
    (0.40, "Medium"),
    (0.0, "Low"),
]


def confidence_label(confidence):
    for threshold, label in CONFIDENCE_LABELS:
        if confidence >= threshold:
            return label
    return "Low"


def _why_suspicious(report):
    """
    Evidence list built entirely from fields the pipeline already
    computed - confidence_breakdown (engine/scoring.py) and
    ai_explanation (engine/ml_model.py's local feature attribution) - narrated, not re-derived. Sorted so the strongest real contribution
    to the confidence score leads.
    """
    items = []
    for factor in report.get("confidence_breakdown", []):
        if factor.get("weight", 0) == 0:
            continue  # diagnostic-only rows (e.g. cluster quality) aren't part of the scored formula
        items.append({
            "signal": factor["factor"],
            "evidence": f"value {factor['value']} × weight {factor['weight']} = {factor['contribution']:+.3f} to the confidence score",
            "contribution": factor["contribution"],
        })
    for feat in report.get("ai_explanation", []):
        if feat["direction"] != "+":
            continue  # only the factors that raised suspicion belong in "why suspicious"
        items.append({
            "signal": f"ML signal: {feat['reason']}",
            "evidence": f"RandomForest attribution magnitude {feat['magnitude']} (feature: {feat['feature']})",
            "contribution": feat["magnitude"],
        })
    items.sort(key=lambda i: i["contribution"], reverse=True)
    return items[:6]


def _next_steps(report):
    """
    Deterministic next-step suggestions keyed off the actual decision and
    flags already computed - not a free-text generation. Each step
    states which real finding justifies it.
    """
    steps = []
    decision = report.get("decision", {})
    action = decision.get("action")

    if action == "suggest_freeze":
        steps.append({
            "step": "Draft and route a freeze notice for supervisor approval",
            "why": f"Confidence {report.get('confidence')} clears the freeze threshold and the terminal wallet "
                   f"matches a known exchange - see decision.rationale.",
        })
    elif action == "suggest_kyc":
        steps.append({
            "step": "Send a KYC-disclosure request to the matched exchange",
            "why": "Confidence is high enough to justify records, not yet a freeze - decision.rationale explains the gap.",
        })
    elif action == "manual_review" and report.get("mixer_hit"):
        steps.append({
            "step": "Escalate to a human analyst for off-chain / OSINT follow-up",
            "why": f"The deterministic trail stops at {report['mixer_hit'].get('label', 'a known mixer')}; "
                   f"automated tracing cannot see past this hop.",
        })
    elif action == "insufficient_evidence":
        steps.append({
            "step": "Document evidentiary limit and consider closing pending new information",
            "why": "No deposit-fingerprint or exchange pattern match was found on this trail.",
        })
    else:
        steps.append({
            "step": "Route to manual review",
            "why": decision.get("rationale", "Automated pipeline reached its evidentiary limit."),
        })

    if report.get("linked_case_details"):
        n = len(report["linked_case_details"])
        steps.append({
            "step": f"Cross-reference with {n} linked open case(s) before finalising action",
            "why": f"Suspect wallet's fund-flow shares a laundering-path address with {n} other case(s) - "
                   f"see the Case Network view for the full graph.",
        })

    for pattern in report.get("risk_patterns", []):
        if pattern["pattern"] == "structuring":
            steps.append({
                "step": "Flag for structuring/smurfing review under applicable reporting-threshold provisions",
                "why": pattern["evidence"],
            })
        elif pattern["pattern"] == "layering":
            steps.append({
                "step": "Request extended-hop tracing beyond the current max-hop limit",
                "why": pattern["evidence"],
            })

    return steps


def generate_brief(report):
    """
    The Investigation Copilot's output for a single report: a one-line
    headline, ranked evidence for "why suspicious", the risk patterns
    already detected, and next steps - all cross-referencing fields that
    already exist in `report`, so nothing here can say something the
    rest of the console doesn't already show the receipts for.
    """
    confidence = report.get("confidence", 0.0)
    decision = report.get("decision", {})
    label = confidence_label(confidence)

    if decision.get("action") == "suggest_freeze":
        headline = f"{label}-confidence match ({confidence:.0%}) - recommend freeze notice"
    elif decision.get("action") == "suggest_kyc":
        headline = f"{label}-confidence match ({confidence:.0%}) - recommend KYC-disclosure request"
    elif report.get("mixer_hit"):
        headline = f"Trail blocked at a known mixer - manual follow-up required"
    elif decision.get("action") == "insufficient_evidence":
        headline = f"{label}-confidence ({confidence:.0%}) - insufficient evidence to proceed automatically"
    else:
        headline = f"{label}-confidence ({confidence:.0%}) - flagged for manual review"

    return {
        "headline": headline,
        "confidence": confidence,
        "confidence_label": label,
        "why_suspicious": _why_suspicious(report),
        "next_steps": _next_steps(report),
    }
