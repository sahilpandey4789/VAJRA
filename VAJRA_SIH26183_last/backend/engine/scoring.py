"""
Exchange attribution confidence formula - Technical Defense Document,
section 6. Not a vibe: a weighted, documented, inspectable formula.

    confidence = sigma( w1*DepositFingerprint + w2*SweepRegularity
                       + w3*SenderDiversityZScore + w4*(1 - MixerPenalty)
                       + w5*AI_IllicitProbability_inverse + bias )
    sigma(x) = 1 / (1 + e^-x)

Weights below are fit against the held-out fixture set described in
engine/fixtures.py (three known outcomes) using a small closed-form
grid search (scripts/fit_weights.py) - not chosen by eyeballing a
target number. As more labelled cases accumulate in production, the
documented next step is to re-fit these via logistic regression
against real investigator-confirmed outcomes (Technical Defense
Document section 6).
"""
import math

WEIGHTS = {
    "w1_deposit_fingerprint": 2.55,
    "w2_sweep_regularity": 1.85,
    "w3_sender_diversity_z": 0.55,
    "w4_mixer_clear": 2.35,
    "w5_ai_illicit_inverse": 1.65,
    "bias": -7.82,
}

DECISION_THRESHOLDS = [
    {"min": 0.75, "action": "suggest_freeze", "notice_type": "freeze_102_crpc",
     "label": "Suggest freeze notice (102 CrPC / 106 BNSS)",
     "rationale": "High enough confidence to justify formal legal action; officer still reviews and confirms before sending."},
    {"min": 0.40, "action": "suggest_kyc", "notice_type": "kyc_disclosure",
     "label": "Suggest KYC-disclosure request",
     "rationale": "Enough signal to justify asking the exchange for records, not yet enough for a freeze."},
    {"min": 0.0, "action": "manual_review", "notice_type": None,
     "label": "Flag for manual review",
     "rationale": "Automated pipeline has reached its evidentiary limit; a human analyst takes over."},
]


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def score(deposit_fingerprint, sweep_regularity, sender_diversity_z, mixer_penalty, ai_illicit_probability,
          cluster_quality=None):
    ai_inverse = 1.0 - ai_illicit_probability
    mixer_clear = 1.0 - mixer_penalty
    z = (
        WEIGHTS["w1_deposit_fingerprint"] * deposit_fingerprint
        + WEIGHTS["w2_sweep_regularity"] * sweep_regularity
        + WEIGHTS["w3_sender_diversity_z"] * sender_diversity_z
        + WEIGHTS["w4_mixer_clear"] * mixer_clear
        + WEIGHTS["w5_ai_illicit_inverse"] * ai_inverse
        + WEIGHTS["bias"]
    )
    conf = sigmoid(z)
    breakdown = [
        {"factor": "Deposit-fingerprint match", "value": round(deposit_fingerprint, 3),
         "weight": WEIGHTS["w1_deposit_fingerprint"], "contribution": round(WEIGHTS["w1_deposit_fingerprint"] * deposit_fingerprint, 3)},
        {"factor": "Sweep regularity", "value": round(sweep_regularity, 3),
         "weight": WEIGHTS["w2_sweep_regularity"], "contribution": round(WEIGHTS["w2_sweep_regularity"] * sweep_regularity, 3)},
        {"factor": "Sender-diversity z-score", "value": round(sender_diversity_z, 3),
         "weight": WEIGHTS["w3_sender_diversity_z"], "contribution": round(WEIGHTS["w3_sender_diversity_z"] * sender_diversity_z, 3)},
        {"factor": "Mixer penalty (inverted)", "value": round(mixer_clear, 3),
         "weight": WEIGHTS["w4_mixer_clear"], "contribution": round(WEIGHTS["w4_mixer_clear"] * mixer_clear, 3)},
        {"factor": "AI illicit-probability (inverted)", "value": round(ai_inverse, 3),
         "weight": WEIGHTS["w5_ai_illicit_inverse"], "contribution": round(WEIGHTS["w5_ai_illicit_inverse"] * ai_inverse, 3)},
    ]
    if cluster_quality is not None:
        # Diagnostic only - NOT part of the sigmoid above (see docstring).
        # Shown so "why this confidence number" always includes cluster
        # trustworthiness, without silently smuggling a 6th weight into
        # a formula that was calibrated on five.
        breakdown.append({
            "factor": "Cluster quality (diagnostic - not in formula)",
            "value": round(cluster_quality, 3), "weight": 0.0, "contribution": 0.0,
        })
    return round(conf, 4), breakdown


def attribution_tier(confidence, exchange_matched, mixer_penalty, sanctions_matched=False):
    """
    Data-provenance attribution tier - CONFIRMED / PROBABLE / UNATTRIBUTED.

    This is deliberately separate from the confidence score and the
    decide() action above. `confidence` says "how strong is the signal";
    this says "how certain are we of *who* actually received the funds,
    and on what kind of evidence". A high confidence score built entirely
    from heuristics (deposit-fingerprint, sweep regularity, AI probability)
    is still PROBABLE, not CONFIRMED - CONFIRMED is reserved for a direct,
    first-party address match (the terminal wallet is literally in
    known_exchange_wallets, looked up in tracer.py's
    _known_exchange_lookup(), not inferred).

    Returns {"tier": ..., "reason": ...} - the reason string is what a
    report/UI shows next to the tier so "why UNATTRIBUTED" is never a
    bare label with no explanation, the same discipline the rest of this
    codebase already applies to the confidence breakdown and the AI
    explanation.
    """
    if sanctions_matched:
        # Strongest possible evidence tier: a real, government-published
        # designation (see engine/ofac_sanctions.py) - independent of
        # mixer_penalty, because the sanctioned address itself is the
        # evidence, not an inference about what lies past it.
        return {
            "tier": "CONFIRMED",
            "reason": "Address matches a real, published OFAC Specially Designated Nationals (SDN) "
                      "list entry - a first-party U.S. Treasury sanctions designation, the strongest "
                      "evidence tier this system produces.",
        }
    if mixer_penalty >= 1.0:
        return {
            "tier": "UNATTRIBUTED",
            "reason": "A known mixer/tumbler sits on the path - the deterministic trail breaks there, "
                      "so no exchange can be confirmed or even probabilistically inferred past that hop.",
        }
    if exchange_matched:
        # First-party evidence: the terminal address is literally present
        # in known_exchange_wallets (see tracer.py's _known_exchange_lookup),
        # not a scraped third-party label and not a heuristic inference.
        return {
            "tier": "CONFIRMED",
            "reason": "Terminal wallet matches a known exchange hot-wallet address on file - "
                      "a direct first-party address match, not a heuristic inference.",
        }
    if confidence >= 0.40:
        return {
            "tier": "PROBABLE",
            "reason": "No direct exchange-wallet match, but deposit-fingerprint/sweep-regularity/"
                      "AI-probability signals cross the evidentiary threshold - a heuristic inference, "
                      "not a confirmed address match.",
        }
    return {
        "tier": "UNATTRIBUTED",
        "reason": "Neither a direct exchange-wallet match nor a strong enough heuristic signal was found - "
                  "the trail's evidentiary strength ends here.",
    }


def decide(confidence, mixer_penalty, exchange_matched):
    if mixer_penalty >= 1.0:
        return {"action": "manual_review", "notice_type": None,
                "label": "Flag for manual review - mixer-blocked",
                "rationale": "A known mixer/tumbler sits on the path; the deterministic trail breaks here. "
                             "Confidence is explicitly capped rather than guessing past the mixer hop."}
    if not exchange_matched and confidence < 0.40:
        return {"action": "insufficient_evidence", "notice_type": None,
                "label": "Insufficient evidence - recommend closing",
                "rationale": "No deposit-fingerprint or exchange pattern match found on this trail. "
                             "Automated pipeline has reached its evidentiary limit."}
    for tier in DECISION_THRESHOLDS:
        if confidence >= tier["min"]:
            return {"action": tier["action"], "notice_type": tier["notice_type"],
                    "label": tier["label"], "rationale": tier["rationale"]}
    return DECISION_THRESHOLDS[-1]
