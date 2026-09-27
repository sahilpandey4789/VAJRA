"""
Auto-drafted legal notice generator - Master Document section 4 (stage 6)
and Technical Defense Document section 6 decision thresholds.

Templates are outcome-aware: a freeze notice cites 102 CrPC / 106 BNSS,
a KYC-disclosure request cites 94 BNSS / 79(3)(b) IT Act via the Sahyog
Portal, matching the exact legal pipeline described in the Master
Document section 3.
"""
import datetime

TEMPLATES = {
    "freeze_102_crpc": {
        "subject": "Preservation & freeze request under Section 102 CrPC / 106 BNSS",
        "body": (
            "To: Nodal Officer, {exchange}\n"
            "Re: Preservation & freeze request under Section 102 CrPC / 106 BNSS\n\n"
            "Case reference: {ncrp_ref}\n"
            "Suspect wallet: {suspect_wallet}\n"
            "Attributed deposit wallet: {deposit_wallet} (see attached evidence pack, hash {report_hash_short})\n"
            "Confidence: {confidence_pct}%\n\n"
            "You are requested to preserve all KYC records and freeze further withdrawal "
            "from the account associated with the above deposit wallet, pending formal "
            "written request from this office within 7 days, under Section 102 CrPC / "
            "106 BNSS.\n\n"
            "Investigating Officer: {officer_name}\n"
            "{jurisdiction}"
        ),
        "sla_days": 7,
    },
    "kyc_disclosure": {
        "subject": "KYC-disclosure request under Section 94 BNSS / 79(3)(b) IT Act",
        "body": (
            "To: Nodal Officer, {exchange}\n"
            "Re: KYC-disclosure request under Section 94 BNSS / 79(3)(b) IT Act\n\n"
            "Case reference: {ncrp_ref}\n"
            "Suspect wallet: {suspect_wallet}\n"
            "Wallet under review: {deposit_wallet} (see attached evidence pack, hash {report_hash_short})\n"
            "Confidence: {confidence_pct}% - below the freeze threshold; disclosure requested "
            "to corroborate before further action.\n\n"
            "You are requested to disclose KYC records and transaction history associated "
            "with the above wallet within 7 days, under Section 94 BNSS / 79(3)(b) IT Act, "
            "via the Sahyog Portal.\n\n"
            "Investigating Officer: {officer_name}\n"
            "{jurisdiction}"
        ),
        "sla_days": 7,
    },
}


def generate(notice_type, case_row, report, officer_name, jurisdiction):
    tpl = TEMPLATES.get(notice_type)
    if not tpl:
        raise ValueError(f"No template for notice type {notice_type}")

    exchange = "Unknown VASP"
    deposit_wallet = "(see evidence pack)"
    if report.get("exchange_match"):
        exchange = report["exchange_match"]["exchange"]
        deposit_wallet = report["exchange_match"]["address"]

    body = tpl["body"].format(
        exchange=exchange,
        ncrp_ref=case_row["ncrp_ref"],
        suspect_wallet=case_row["suspect_wallet"],
        deposit_wallet=deposit_wallet,
        report_hash_short=report["report_hash"][:6] + "…" + report["report_hash"][-4:],
        confidence_pct=round(report["confidence"] * 100),
        officer_name=officer_name,
        jurisdiction=jurisdiction,
    )
    sla_due = (datetime.datetime.utcnow() + datetime.timedelta(days=tpl["sla_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "notice_type": notice_type,
        "subject": tpl["subject"],
        "exchange_name": exchange,
        "body": body,
        "sla_due": sla_due,
    }
