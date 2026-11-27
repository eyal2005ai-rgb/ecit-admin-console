"""Audit trail: one JSON line per run + a branded PDF report."""
from __future__ import annotations

import json
import platform
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .config import (APP_NAME, APP_VERSION, BRAND_LINE, EULA_VERSION, PUBLISHER,
                     audit_dir, resource_path)
from .tasks.base import Status, StepResult


def build_record(task_id: str, tenant: dict, admin_upn: str, target: dict,
                 results: list[StepResult]) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "app": APP_NAME, "version": APP_VERSION, "eula_version": EULA_VERSION,
        "task": task_id,
        "time_utc": now.isoformat(timespec="seconds"),
        "time_local": now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "computer": platform.node(),
        "tenant": {"id": tenant.get("id", ""), "name": tenant.get("displayName", "")},
        "admin": admin_upn,
        "target": {"id": target.get("id"), "name": target.get("displayName"),
                   "upn": target.get("userPrincipalName")},
        "results": [{**asdict(r), "status": r.status.value} for r in results],
    }


def append_jsonl(record: dict, folder: Path | None = None) -> Path:
    folder = folder or audit_dir()
    path = folder / "audit-log.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


_STATUS_COLOR = {
    Status.OK.value: colors.HexColor("#1e7d32"),
    Status.PARTIAL.value: colors.HexColor("#b26a00"),
    Status.FAILED.value: colors.HexColor("#c62828"),
    Status.SKIPPED.value: colors.HexColor("#616161"),
}


def _esc(text: str) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def write_pdf(record: dict, folder: Path | None = None) -> Path:
    folder = folder or audit_dir()
    stamp = record["time_utc"].replace(":", "").replace("-", "")[:15]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", record["target"]["upn"] or "user")[:60]
    path = folder / f"{record['task']}_{safe}_{stamp}.pdf"

    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=11)
    story = []

    logo = resource_path("ecit_logo.png")
    header_left = Image(str(logo), width=38 * mm, height=14 * mm, kind="proportional") if logo.exists() else Paragraph("<b>ECIT</b>", styles["Title"])
    header = Table([[header_left, Paragraph(f"<b>{APP_NAME}</b><br/>Offboarding audit report", styles["Heading3"])]],
                   colWidths=[50 * mm, 120 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [header, Spacer(1, 6 * mm)]

    t = record["target"]
    info = [
        ["Employee", f"{t['name']} ({t['upn']})"],
        ["Tenant", f"{record['tenant']['name']} ({record['tenant']['id']})"],
        ["Performed by", record["admin"]],
        ["Date & time", f"{record['time_local']}  (UTC {record['time_utc']})"],
        ["Computer", record["computer"]],
        ["App version", f"{APP_NAME} {record['version']}"],
    ]
    it = Table([[Paragraph(f"<b>{a}</b>", cell), Paragraph(_esc(b), cell)] for a, b in info],
               colWidths=[35 * mm, 135 * mm])
    it.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f3f3"))]))
    story += [it, Spacer(1, 6 * mm), Paragraph("<b>Steps</b>", styles["Heading4"])]

    rows = [[Paragraph("<b>Step</b>", cell), Paragraph("<b>Result</b>", cell), Paragraph("<b>Details</b>", cell)]]
    for r in record["results"]:
        detail = _esc(r["detail"])
        if r.get("items"):
            detail += "<br/>" + "<br/>".join("• " + _esc(i) for i in r["items"])
        color = _STATUS_COLOR.get(r["status"], colors.black).hexval()[2:]
        rows.append([Paragraph(_esc(r["title"]), cell),
                     Paragraph(f'<font color="#{color}"><b>{r["status"]}</b></font>', cell),
                     Paragraph(detail, cell)])
    st = Table(rows, colWidths=[42 * mm, 25 * mm, 103 * mm], repeatRows=1)
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f3f3")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [st, Spacer(1, 8 * mm),
              Paragraph("The new password was generated randomly and was not displayed or recorded. "
                        "Session revocation can take a few minutes to reach every app.", small)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(15 * mm, 10 * mm, BRAND_LINE)
        canvas.drawRightString(195 * mm, 10 * mm,
                               f"Provided as-is under the {PUBLISHER} EULA ({record['eula_version']}). Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"Offboarding report - {t['upn']}", author=PUBLISHER)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
