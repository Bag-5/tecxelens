from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.flowables import Flowable

BRAND_INDIGO = HexColor("#4f46e5")
BRAND_CYAN = HexColor("#06b6d4")
TEXT_PRIMARY = HexColor("#111827")
TEXT_SECONDARY = HexColor("#6b7280")
BORDER_LIGHT = HexColor("#e5e7eb")
BG_STRIP = HexColor("#0f0b2a")

SEVERITY_COLORS = {
    "critical": HexColor("#dc2626"),
    "high": HexColor("#ea580c"),
    "medium": HexColor("#ca8a04"),
    "low": HexColor("#16a34a"),
}

SEVERITY_BG = {
    "critical": HexColor("#fef2f2"),
    "high": HexColor("#fff7ed"),
    "medium": HexColor("#fefce8"),
    "low": HexColor("#f0fdf4"),
}

RISK_COLORS = {
    "Excellent": HexColor("#22c55e"),
    "Good": HexColor("#06b6d4"),
    "Medium": HexColor("#eab308"),
    "Poor": HexColor("#f97316"),
    "Critical": HexColor("#ef4444"),
}


class ScoreBar(Flowable):
    def __init__(self, score: int, width, height=6):
        super().__init__()
        self.score = max(0, min(100, score))
        self._width = width
        self._height = height

    def draw(self):
        c = self.canv
        w = self._width
        h = self._height
        r = h / 2

        c.setStrokeColor(HexColor("#e5e7eb"))
        c.setLineWidth(0.5)
        c.setFillColor(HexColor("#f3f4f6"))
        p = c.beginPath()
        p.roundRect(0, 0, w, h, r)
        c.drawPath(p, fill=1, stroke=1)

        fill_w = (self.score / 100) * w
        if fill_w > 0:
            if self.score >= 90:
                bar_color = RISK_COLORS["Excellent"]
            elif self.score >= 75:
                bar_color = RISK_COLORS["Good"]
            elif self.score >= 50:
                bar_color = RISK_COLORS["Medium"]
            elif self.score >= 25:
                bar_color = RISK_COLORS["Poor"]
            else:
                bar_color = RISK_COLORS["Critical"]

            c.setFillColor(bar_color)
            p2 = c.beginPath()
            p2.roundRect(0, 0, fill_w, h, r)
            c.drawPath(p2, fill=1, stroke=0)


def _build_styles():
    ss = getSampleStyleSheet()

    styles = {
        "cover_brand": ParagraphStyle(
            "CoverBrand", parent=ss["h1"],
            fontSize=28, leading=34, textColor=colors.white,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
            spaceAfter=2 * mm,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=ss["h1"],
            fontSize=16, leading=22, textColor=HexColor("#c7d2fe"),
            fontName="Helvetica", alignment=TA_CENTER,
            spaceAfter=12 * mm,
        ),
        "cover_label": ParagraphStyle(
            "CoverLabel", parent=ss["Normal"],
            fontSize=10, leading=14, textColor=HexColor("#9ca3af"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "cover_value": ParagraphStyle(
            "CoverValue", parent=ss["Normal"],
            fontSize=13, leading=17, textColor=colors.white,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "score_num": ParagraphStyle(
            "ScoreNum", parent=ss["h1"],
            fontSize=56, leading=62, textColor=TEXT_PRIMARY,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "score_bar_label": ParagraphStyle(
            "ScoreBarLabel", parent=ss["Normal"],
            fontSize=14, leading=18,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "section_h1": ParagraphStyle(
            "SectionH1", parent=ss["h1"],
            fontSize=18, leading=24, textColor=TEXT_PRIMARY,
            fontName="Helvetica-Bold",
            spaceBefore=8 * mm, spaceAfter=4 * mm,
        ),
        "section_h2": ParagraphStyle(
            "SectionH2", parent=ss["h2"],
            fontSize=13, leading=17, textColor=TEXT_PRIMARY,
            fontName="Helvetica-Bold",
            spaceBefore=6 * mm, spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCustom", parent=ss["Normal"],
            fontSize=10, leading=15, textColor=TEXT_PRIMARY,
            fontName="Helvetica",
            spaceAfter=3 * mm,
        ),
        "body_small": ParagraphStyle(
            "BodySmall", parent=ss["Normal"],
            fontSize=9, leading=13, textColor=TEXT_SECONDARY,
            fontName="Helvetica",
        ),
        "callout": ParagraphStyle(
            "Callout", parent=ss["Normal"],
            fontSize=10, leading=15, textColor=TEXT_PRIMARY,
            fontName="Helvetica",
            leftIndent=4 * mm,
        ),
        "badge": ParagraphStyle(
            "Badge", parent=ss["Normal"],
            fontSize=8, leading=10, textColor=colors.white,
            fontName="Helvetica-Bold",
        ),
        "ref_badge": ParagraphStyle(
            "RefBadge", parent=ss["Normal"],
            fontSize=8, leading=10, textColor=BRAND_INDIGO,
            fontName="Helvetica",
        ),
        "footer": ParagraphStyle(
            "Footer", parent=ss["Normal"],
            fontSize=8, leading=10, textColor=TEXT_SECONDARY,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "file_label": ParagraphStyle(
            "FileLabel", parent=ss["Normal"],
            fontSize=9, leading=13, textColor=HexColor("#9ca3af"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
    }
    return styles


def _severity_badge(severity: str) -> list:
    color = SEVERITY_COLORS.get(severity, HexColor("#6b7280"))
    bg = SEVERITY_BG.get(severity, HexColor("#f9fafb"))
    return [
        Paragraph(severity.upper(), ParagraphStyle(
            "BadgeInline", fontName="Helvetica-Bold",
            fontSize=8, leading=10, textColor=color,
            alignment=TA_CENTER,
        )),
        ("bg", bg),
        ("border", color),
    ]


def _score_color(score: int) -> Color:
    if score >= 90:
        return RISK_COLORS["Excellent"]
    if score >= 75:
        return RISK_COLORS["Good"]
    if score >= 50:
        return RISK_COLORS["Medium"]
    if score >= 25:
        return RISK_COLORS["Poor"]
    return RISK_COLORS["Critical"]


def _hex(c: Color) -> str:
    return f"#{int(c.red * 255):02x}{int(c.green * 255):02x}{int(c.blue * 255):02x}"


def _draw_cover_header(canvas, doc):
    w, h = A4
    bar_height = 90 * mm
    canvas.saveState()

    bg = canvas.beginPath()
    bg.rect(0, h - bar_height, w, bar_height)
    canvas.setFillColor(BG_STRIP)
    canvas.drawPath(bg, fill=1, stroke=0)

    accent_h = 3
    accent_y = h - bar_height
    grad_steps = 40
    for i in range(grad_steps):
        t = i / (grad_steps - 1)
        r = 0.31 + t * (0.02 - 0.31)
        g = 0.27 + t * (0.71 - 0.27)
        b = 0.83 + t * (0.83 - 0.83)
        step_w = w / grad_steps
        c = canvas.beginPath()
        c.rect(i * step_w, accent_y, step_w + 1, accent_h)
        canvas.setFillColor(Color(r, g, b))
        canvas.drawPath(c, fill=1, stroke=0)

    canvas.restoreState()


def _draw_footer(canvas, doc):
    w, h = A4
    canvas.saveState()
    canvas.setStrokeColor(BORDER_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 18 * mm, w - 20 * mm, 18 * mm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_SECONDARY)
    canvas.drawString(20 * mm, 12 * mm, "TECXE Lens — Compliance Assessment Report")
    canvas.drawRightString(
        w - 20 * mm, 12 * mm,
        f"Page {doc.page}"
    )
    canvas.restoreState()


def generate_report(data: dict, filename: str, output_path: Path) -> Path:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=25 * mm,
        bottomMargin=30 * mm,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
    )

    s = _build_styles()
    story = []

    PAGE_W = A4[0] - 44 * mm  # usable width

    # ── COVER ──
    story.append(Spacer(1, 95 * mm))
    story.append(Paragraph("TECXE Lens", s["cover_brand"]))
    story.append(Paragraph("Compliance Assessment Report", s["cover_title"]))

    clean_name = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    story.append(Paragraph(clean_name, s["file_label"]))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(datetime.now().strftime("%B %d, %Y"), s["file_label"])
    )
    story.append(Spacer(1, 12 * mm))

    score = data["overall_score"]
    risk = data["risk_level"]
    sc = _score_color(score)
    sc_hex = f"#{sc.red:02x}{sc.green:02x}{sc.blue:02x}"

    story.append(Paragraph(str(score), ParagraphStyle(
        "CoverScore", fontName="Helvetica-Bold",
        fontSize=64, leading=72, textColor=colors.white,
        alignment=TA_CENTER,
    )))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f'<font color="{sc_hex}">●</font>  {risk}',
        ParagraphStyle(
            "CoverRisk", fontName="Helvetica-Bold",
            fontSize=16, leading=20, textColor=HexColor("#d1d5db"),
            alignment=TA_CENTER,
        )
    ))
    story.append(PageBreak())

    # ── EXECUTIVE SUMMARY ──
    story.append(Paragraph("Executive Summary", s["section_h1"]))
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=BRAND_INDIGO,
        spaceAfter=4 * mm,
    ))
    story.append(Paragraph(data.get("summary", ""), s["body"]))
    story.append(Spacer(1, 4 * mm))

    # Score bar
    story.append(Paragraph(
        f'Compliance Score: <b>{score}/100</b> — {risk}',
        s["section_h2"],
    ))
    story.append(ScoreBar(score, PAGE_W, height=8))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'<font color="{sc_hex}">■</font>  {risk}  '
        f'<font color="{_hex(TEXT_SECONDARY)}">'
        f'({"Excellent" if score >= 90 else "Good" if score >= 75 else "Medium" if score >= 50 else "Poor" if score >= 25 else "Critical"})</font>',
        s["body_small"],
    ))
    story.append(PageBreak())

    # ── FINDINGS ──
    story.append(Paragraph("Findings & Recommendations", s["section_h1"]))
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=BRAND_INDIGO,
        spaceAfter=4 * mm,
    ))

    for idx, f in enumerate(data.get("findings", []), 1):
        sev = f.get("severity", "low")
        sev_color = SEVERITY_COLORS.get(sev, HexColor("#6b7280"))
        sev_bg = SEVERITY_BG.get(sev, HexColor("#f9fafb"))
        sc_hex_sev = f"#{sev_color.red:02x}{sev_color.green:02x}{sev_color.blue:02x}"
        bg_hex = f"#{sev_bg.red:02x}{sev_bg.green:02x}{sev_bg.blue:02x}"

        badge_cells = [
            [
                Paragraph(
                    f'<font color="{sc_hex_sev}"><b>{sev.upper()}</b></font>',
                    ParagraphStyle(
                        "SevBadge", fontSize=9, leading=12,
                        fontName="Helvetica-Bold", alignment=TA_CENTER,
                        textColor=sev_color,
                    ),
                ),
            ]
        ]
        badge_tbl = Table(badge_cells, colWidths=[24 * mm])
        badge_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), sev_bg),
            ("BOX", (0, 0), (-1, -1), 0.5, sev_color),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        title = f"<b>{idx}. {f['title']}</b>"
        title_para = Paragraph(title, ParagraphStyle(
            "FindingTitle", fontName="Helvetica-Bold",
            fontSize=12, leading=16, textColor=TEXT_PRIMARY,
        ))

        header_tbl = Table(
            [[badge_tbl, title_para]],
            colWidths=[30 * mm, PAGE_W - 30 * mm],
        )
        header_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        blocks = [header_tbl, Spacer(1, 2 * mm)]

        desc = f.get("description", "")
        if desc:
            blocks.append(Paragraph(desc, s["body"]))

        rec = f.get("recommendation", "")
        if rec:
            rec_tbl = Table(
                [[Paragraph(rec, s["callout"])]],
                colWidths=[PAGE_W - 8 * mm],
            )
            rec_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#eef2ff")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, BRAND_INDIGO),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
            ]))
            blocks.append(Spacer(1, 2 * mm))
            blocks.append(rec_tbl)

        refs = f.get("references", [])
        if refs:
            ref_blocks = []
            for ref in refs:
                doc_name = Path(ref["document"]).stem.replace("_", " ").replace("-", " ").title()
                section = ref.get("section", "")
                ref_text = f"<b>{doc_name}</b>"
                if section:
                    ref_text += f" — {section}"
                ref_blocks.append(Paragraph(ref_text, ParagraphStyle(
                    "RefItem", fontName="Helvetica",
                    fontSize=9, leading=13, textColor=BRAND_INDIGO,
                    leftIndent=11,  # bullet indent
                )))

            ref_display = "<br/>".join(
                f"●  {r}" for r in [
                    f"<b>{Path(ref['document']).stem.replace('_', ' ').replace('-', ' ').title()}</b>"
                    + (f" — {ref.get('section', '')}" if ref.get("section") else "")
                    for ref in refs
                ]
            )
            ref_table = Table(
                [[Paragraph(
                    f'<font color="{_hex(BRAND_INDIGO)}">{ref_display}</font>',
                    ParagraphStyle(
                        "RefsBlock", fontName="Helvetica",
                        fontSize=9, leading=13,
                    ),
                )]],
                colWidths=[PAGE_W],
            )
            ref_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f5f3ff")),
                ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#ddd6fe")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            blocks.append(Spacer(1, 2 * mm))
            blocks.append(ref_table)

        cves = f.get("cves", [])
        if cves:
            cve_rows = [[
                Paragraph("CVE ID", ParagraphStyle(
                    "CVEHdr", fontName="Helvetica-Bold",
                    fontSize=8, leading=11, textColor=colors.white,
                )),
                Paragraph("Description", ParagraphStyle(
                    "CVEHdr", fontName="Helvetica-Bold",
                    fontSize=8, leading=11, textColor=colors.white,
                )),
                Paragraph("CVSS", ParagraphStyle(
                    "CVEHdr", fontName="Helvetica-Bold",
                    fontSize=8, leading=11, textColor=colors.white,
                    alignment=TA_CENTER,
                )),
                Paragraph("Severity", ParagraphStyle(
                    "CVEHdr", fontName="Helvetica-Bold",
                    fontSize=8, leading=11, textColor=colors.white,
                    alignment=TA_CENTER,
                )),
            ]]
            for cve in cves[:5]:
                cvss = cve.get("cvss_score")
                cve_color = (
                    HexColor("#dc2626") if cvss and cvss >= 9.0
                    else HexColor("#ea580c") if cvss and cvss >= 7.0
                    else HexColor("#ca8a04") if cvss and cvss >= 4.0
                    else HexColor("#16a34a")
                )
                cve_rows.append([
                    Paragraph(cve.get("id", ""), ParagraphStyle(
                        "CVEID", fontName="Helvetica",
                        fontSize=8, leading=11, textColor=TEXT_PRIMARY,
                    )),
                    Paragraph(
                        (cve.get("description", "")[:120] + "...")
                        if len(cve.get("description", "")) > 120
                        else cve.get("description", ""),
                        ParagraphStyle(
                            "CVEDesc", fontName="Helvetica",
                            fontSize=8, leading=11, textColor=TEXT_SECONDARY,
                        ),
                    ),
                    Paragraph(
                        str(cvss) if cvss is not None else "--",
                        ParagraphStyle(
                            "CVEScore", fontName="Helvetica",
                            fontSize=9, leading=11,
                            textColor=cve_color, alignment=TA_CENTER,
                        ),
                    ),
                    Paragraph(cve.get("severity", ""), ParagraphStyle(
                        "CVESev", fontName="Helvetica",
                        fontSize=8, leading=11,
                        textColor=cve_color, alignment=TA_CENTER,
                    )),
                ])

            cve_tbl = Table(
                cve_rows,
                colWidths=[30 * mm, PAGE_W - 30 * mm - 22 * mm, 14 * mm, 16 * mm],
                repeatRows=1,
            )
            cve_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1e1b4b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            # alternating row colors
            for i in range(2, len(cve_rows), 2):
                cve_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, i), (-1, i), HexColor("#f9fafb")),
                ]))
            blocks.append(Spacer(1, 2 * mm))
            blocks.append(cve_tbl)

        blocks.append(HRFlowable(
            width="100%", thickness=0.5, color=BORDER_LIGHT,
            spaceBefore=3 * mm, spaceAfter=5 * mm,
        ))
        story.append(KeepTogether(blocks))

    doc.build(
        story,
        onFirstPage=_draw_cover_header,
        onLaterPages=_draw_footer,
    )
    return output_path
