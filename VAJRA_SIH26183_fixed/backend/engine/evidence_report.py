"""
Evidence PDF report generator.

Produces a real, forensic-style PDF (not an HTML-to-PDF hack, not a
templated string labelled ".pdf") from a completed trace report:
wallet, timeline, a simplified hop diagram, the risk/confidence
explanation, the case's SHA-256 evidence hash, case ID, officer, a QR
code encoding a verification URL (if the optional `qrcode` package is
installed - see requirements.txt; falls back to a printed hash block
if not, so the report is never blocked on an optional dependency), and
a digital-signature placeholder box for the eventual DSC/eSign
integration (Master Document section 9, "Digital Signature
Placeholder" - not implemented as a real signature in this build).
"""
import hashlib
import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

try:
    import qrcode
except ImportError:  # optional - see module docstring
    qrcode = None

INK = colors.HexColor("#1C1811")
COPPER = colors.HexColor("#B5502E")
SLATE = colors.HexColor("#35506B")
SAGE = colors.HexColor("#2E4832")
CRIMSON = colors.HexColor("#9A3B34")
LINE = colors.HexColor("#C7BFA9")
FAINT = colors.HexColor("#6B6355")


def _wrap(c, text, x, y, max_width, font="Helvetica", size=9, leading=12, color=INK):
    c.setFont(font, size)
    c.setFillColor(color)
    words = str(text).split()
    line = ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, font, size) > max_width and line:
            c.drawString(x, y, line)
            y -= leading
            line = w
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def _section_header(c, y, title):
    c.setFillColor(COPPER)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, title.upper())
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(20 * mm, y - 3, 190 * mm, y - 3)
    return y - 9 * mm


def _draw_hop_diagram(c, report, x, y, width, height):
    """A simplified, static hop-chain diagram for the printed page - the interactive SVG version lives in the live console; this is the
    evidentiary flattened form of the same traced transaction list."""
    txs = sorted(report.get("transactions", []), key=lambda t: t["hop"])
    hops = sorted({t["hop"] for t in txs}) or [0]
    n = min(len(hops), 7)
    if n == 0:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(FAINT)
        c.drawString(x, y - height / 2, "No transactions traced on this path.")
        return
    step = width / max(1, n - 1) if n > 1 else 0
    cy = y - height / 2
    for i, hop in enumerate(hops[:n]):
        cx = x + step * i
        is_last = i == n - 1
        fill = CRIMSON if (is_last and report.get("mixer_hit")) else (SAGE if (is_last and report.get("exchange_match")) else colors.HexColor("#F8F6EF"))
        c.setFillColor(fill)
        c.setStrokeColor(SLATE)
        c.circle(cx, cy, 5.5, fill=1, stroke=1)
        c.setFillColor(INK)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(cx, cy - 14, f"hop {hop}")
        if i > 0:
            c.setStrokeColor(LINE)
            c.setLineWidth(1)
            prev_x = x + step * (i - 1)
            c.line(prev_x + 6, cy, cx - 6, cy)
            # direction arrowhead
            c.line(cx - 6, cy, cx - 10, cy + 2.5)
            c.line(cx - 6, cy, cx - 10, cy - 2.5)
    label = report["exchange_match"]["exchange"] if report.get("exchange_match") else (
        report["mixer_hit"]["label"] if report.get("mixer_hit") else "unresolved terminal wallet")
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(FAINT)
    c.drawCentredString(x + width / 2, y - height + 4, f"Terminal: {label}")


def generate_pdf(report, case_row, officer_row, verification_base_url=None):
    """Returns raw PDF bytes for one trace report."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # --- Header ---
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, page_h - 22 * mm, "VAJRA - Evidence Report")
    c.setFont("Helvetica", 9)
    c.setFillColor(FAINT)
    c.drawString(20 * mm, page_h - 28 * mm,
                 "Virtual Asset Judicial Response & Attribution - Indian Cyber Crime Coordination Centre (I4C)")
    c.setStrokeColor(COPPER)
    c.setLineWidth(1.2)
    c.line(20 * mm, page_h - 31 * mm, 190 * mm, page_h - 31 * mm)

    y = page_h - 40 * mm

    # --- Case metadata ---
    meta = [
        ("Case ID", case_row["id"]),
        ("NCRP reference", case_row["ncrp_ref"]),
        ("Suspect wallet", report["suspect_wallet"]),
        ("Chain", report["chain"]),
        ("Investigating officer", officer_row["name"] if officer_row else " - "),
        ("Jurisdiction", officer_row["jurisdiction"] if officer_row else case_row["jurisdiction"]),
        ("Generated at (UTC)", report["generated_at"]),
        ("Data source", report.get("data_source", "offline-fixture")),
    ]
    for label, value in meta:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(FAINT)
        c.drawString(20 * mm, y, f"{label}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(INK)
        c.drawString(62 * mm, y, str(value))
        y -= 5.6 * mm

    y -= 4 * mm
    y = _section_header(c, y, "Fund-flow timeline")
    _draw_hop_diagram(c, report, 25 * mm, y, 160 * mm, 26 * mm)
    y -= 32 * mm

    y = _section_header(c, y, "Attribution confidence")
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(COPPER)
    c.drawString(20 * mm, y, f"{round(report['confidence'] * 100)}%")
    c.setFont("Helvetica", 9)
    c.setFillColor(INK)
    y2 = _wrap(c, report["decision"]["rationale"], 45 * mm, y + 4, 140 * mm)
    y -= 8 * mm
    for f in report.get("confidence_breakdown", []):
        c.setFont("Helvetica", 8)
        c.setFillColor(FAINT)
        c.drawString(22 * mm, y, f"{f['factor']}")
        c.setFillColor(INK)
        c.drawRightString(188 * mm, y, f"{f['value']}  (contribution {f['contribution']:+})" if f.get("weight") else f"{f['value']} (diagnostic)")
        y -= 5 * mm

    y -= 3 * mm
    y = _section_header(c, y, "AI risk engine - why this prediction")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(INK)
    c.drawString(20 * mm, y, f"Illicit-probability score: {round(report.get('ai_illicit_probability', 0) * 100)}%")
    y -= 5.5 * mm
    for reason in report.get("ai_explanation", [])[:5]:
        sign = "+" if reason["direction"] == "+" else "−"
        color = CRIMSON if reason["direction"] == "+" else SAGE
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(22 * mm, y, sign)
        c.setFillColor(INK)
        c.setFont("Helvetica", 8.5)
        c.drawString(28 * mm, y, reason["reason"])
        y -= 5 * mm

    # --- New page for hash / QR / signature ---
    c.showPage()
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(20 * mm, page_h - 22 * mm, "Evidence integrity & verification")
    y = page_h - 34 * mm

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(FAINT)
    c.drawString(20 * mm, y, "SHA-256 evidence-pack hash:")
    y -= 5.5 * mm
    c.setFont("Courier", 8)
    c.setFillColor(INK)
    h = report.get("report_hash", "")
    c.drawString(20 * mm, y, h[:44])
    y -= 4.5 * mm
    if len(h) > 44:
        c.drawString(20 * mm, y, h[44:])
        y -= 8 * mm
    else:
        y -= 4 * mm

    verify_payload = f"{verification_base_url or 'vajra://verify'}/{case_row['id']}/{h}"
    qr_size = 32 * mm
    qr_x, qr_y = 20 * mm, y - qr_size
    if qrcode is not None:
        qr_img = qrcode.make(verify_payload)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)
    else:
        c.setStrokeColor(LINE)
        c.rect(qr_x, qr_y, qr_size, qr_size)
        _wrap(c, "QR verification requires the optional 'qrcode' package "
                 "(pip install qrcode[pil]) - hash above is verifiable manually.",
              qr_x + 2 * mm, qr_y + qr_size - 5 * mm, qr_size - 4 * mm, size=6.5, color=FAINT)
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(FAINT)
    c.drawString(qr_x, qr_y - 5 * mm, "Scan to verify against case record")

    # --- Digital signature placeholder ---
    sig_x, sig_y, sig_w, sig_h = 100 * mm, qr_y, 70 * mm, qr_size
    c.setStrokeColor(LINE)
    c.setDash(2, 2)
    c.rect(sig_x, sig_y, sig_w, sig_h)
    c.setDash()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(FAINT)
    c.drawCentredString(sig_x + sig_w / 2, sig_y + sig_h / 2 + 3, "Digital Signature")
    c.drawCentredString(sig_x + sig_w / 2, sig_y + sig_h / 2 - 6, "(DSC / eSign integration - placeholder)")

    c.setFont("Helvetica", 7)
    c.setFillColor(FAINT)
    c.drawString(20 * mm, 15 * mm,
                 "This report is generated by the VAJRA reference build for SIH26183. "
                 "See docs/BUILT_VS_ROADMAP.md for exactly what is production-real vs. documented next step.")

    c.showPage()
    c.save()
    return buf.getvalue()
