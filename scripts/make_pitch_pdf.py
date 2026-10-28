#!/usr/bin/env python3
"""Generate the manager pitch PDF for the One Touch Resolve.

Produces docs/Coordinated-Outcome-Engine-Pitch.pdf — a clean, professional
2-3 page brief written in plain business English.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Coordinated-Outcome-Engine-Pitch.pdf"

# ── Brand palette ──────────────────────────────────────────────────────────
INK      = colors.HexColor("#1a1f36")
INK2     = colors.HexColor("#3c4257")
MUTED    = colors.HexColor("#697386")
BRAND    = colors.HexColor("#635bff")
BRAND_BG = colors.HexColor("#eef0ff")
LINE     = colors.HexColor("#e6e9ef")
OK       = colors.HexColor("#1a9c6b")
CARD     = colors.HexColor("#fbfcfe")

styles = getSampleStyleSheet()

def S(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)

body   = S("body", fontName="Helvetica", fontSize=9.5, leading=14, textColor=INK2, spaceAfter=6)
h1     = S("h1", fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=INK, spaceAfter=2)
sub    = S("sub", fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED, spaceAfter=10)
h2     = S("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=BRAND, spaceBefore=12, spaceAfter=5)
lead   = S("lead", fontName="Helvetica-Bold", fontSize=10.5, leading=15, textColor=INK, spaceAfter=6)
small  = S("small", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)
cardh  = S("cardh", fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=INK)
cardb  = S("cardb", fontName="Helvetica", fontSize=8.8, leading=12.5, textColor=INK2)


def bullets(items, style=body):
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=6, value="•") for t in items],
        bulletType="bullet", bulletColor=BRAND, bulletFontSize=8, leftIndent=12, spaceAfter=6,
    )


def kpi_row(cells):
    data = [[Paragraph(f"<b>{v}</b>", S("kv", fontName="Helvetica-Bold", fontSize=15, textColor=BRAND, alignment=1)),]
            for v, _ in cells]
    # build a single row of value/label stacks
    row_v = [Paragraph(f"<b>{v}</b>", S("kv", fontName="Helvetica-Bold", fontSize=14, textColor=BRAND, alignment=1)) for v, _ in cells]
    row_l = [Paragraph(l, S("kl", fontName="Helvetica", fontSize=7.5, textColor=MUTED, alignment=1)) for _, l in cells]
    t = Table([row_v, row_l], colWidths=[(170*mm)/len(cells)]*len(cells))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CARD),
        ("BOX", (0,0), (-1,-1), 0.5, LINE),
        ("INNERGRID", (0,0), (-1,-1), 0.5, LINE),
        ("TOPPADDING", (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,1), (-1,1), 8),
        ("TOPPADDING", (0,1), (-1,1), 0),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    # Top brand band
    canvas.setFillColor(BRAND)
    canvas.rect(0, A4[1]-14*mm, A4[0], 14*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(18*mm, A4[1]-9.2*mm, "HCLTech")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(A4[0]-18*mm, A4[1]-9.2*mm, "AWS CDS Agentic AI Partner Hackathon — Sept. 2026")
    # Footer
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.5)
    canvas.line(18*mm, 12*mm, A4[0]-18*mm, 12*mm)
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18*mm, 8*mm, "One Touch Resolve — Confidential draft for internal review")
    canvas.drawRightString(A4[0]-18*mm, 8*mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm, topMargin=20*mm, bottomMargin=16*mm,
        title="One Touch Resolve — Hackathon Pitch", author="HCLTech",
    )
    E = []

    E.append(Paragraph("One Touch Resolve", h1))
    E.append(Paragraph("An agentic AI solution that settles a rental-car accident claim in days, not months — "
                       "by coordinating every party across their preferred channel.", sub))
    E.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=8))

    E.append(Paragraph("The problem we are solving", h2))
    E.append(Paragraph(
        "A rental-car accident is inherently three people who never talk to each other directly: the renter, the "
        "rental fleet branch, and the insurer's adjuster — each sitting in a different system. Today the only thing "
        "connecting them is the renter, making phone calls. Rental agreements demand the accident be reported within "
        "about 24 hours or the damage waiver is voided, yet the full claim can take six to eighteen months to settle, "
        "dragged out by back-ordered parts and supplemental approvals. Meanwhile the car sits in limbo and the "
        "renter's rental coverage runs out before repairs finish. No one owns the coordination, and every silent "
        "handoff erodes trust.", body))

    E.append(Paragraph("What we built", h2))
    E.append(Paragraph(
        "We built a supervisor AI agent on Amazon Bedrock that runs a small team of specialist agents — one for the "
        "renter, one for the fleet branch, and one for the insurer. The supervisor drives all of them toward a single "
        "goal: a settled claim. It talks to each party on the channel that fits them — WhatsApp for the renter (Maya), "
        "RCS with SMS fallback for the fleet coordinator (Dan), and email for the insurer's adjuster (Priya) — while "
        "keeping one shared record as the single source of truth.", body))

    E.append(Paragraph("How it works, in one claim", h2))
    E.append(bullets([
        "Maya, the renter, reports a collision by sending photos on WhatsApp from the roadside — inside the 24-hour "
        "window. The agent opens the claim and uses AI to gauge severity and likely repair time.",
        "In parallel, it asks Dan at the fleet branch for an estimate over RCS and sends Priya, the insurer's "
        "adjuster, a coverage notice by email.",
        "The rear bumper turns out to be back-ordered. Instead of stalling, the agent re-plans: it arranges a swap "
        "rental for Maya, sources the part from an alternative supplier, and proactively keeps her informed.",
        "Mid-conversation Dan drops off RCS out on the lot, so the agent continues seamlessly over SMS without losing "
        "any context.",
        "Once all three parties have confirmed, the agent issues the settlement by email and closes the loop with "
        "Maya — in days rather than months.",
    ]))

    E.append(Paragraph("Why this is more than a chatbot", h2))
    E.append(Paragraph(
        "A chatbot answers questions. This solution takes action and coordinates independent parties to a finished "
        "outcome. Two capabilities set it apart, and neither can be faked by a single-response assistant:", body))
    E.append(bullets([
        "<b>Commit gate:</b> the claim never advances until every required party has agreed. If one party is blocked, "
        "the agent re-plans around it rather than getting stuck.",
        "<b>Channel continuity:</b> a single conversation survives across WhatsApp, RCS, SMS, and email, because the "
        "state lives with the agent, not in any one channel.",
    ]))

    E.append(Spacer(1, 4))
    E.append(kpi_row([
        ("Days", "to settle vs 6–18 months today"),
        ("3 parties", "coordinated in one workflow"),
        ("4 channels", "WhatsApp · RCS · SMS · Email"),
        ("1 record", "shared source of truth"),
    ]))

    # ---- Page 2 ----
    E.append(Spacer(1, 12))
    E.append(Paragraph("The technology", h2))
    E.append(Paragraph(
        "The solution is built entirely on AWS. The intelligence runs on Amazon Bedrock; the customer communication "
        "runs on AWS Communication Developer Services. It deploys as serverless infrastructure with a single command.", body))

    tech = [
        ["Layer", "AWS service", "Role"],
        ["Reasoning", "Amazon Bedrock (AgentCore, Nova / Nova Pro)", "Supervisor and specialist agents; claim triage and re-planning"],
        ["Messaging", "AWS End User Messaging (SMS, RCS)", "Interactive updates to the fleet branch, with automatic SMS fallback"],
        ["Messaging", "AWS End User Messaging Social (WhatsApp)", "Rich two-way conversation with the renter"],
        ["Email", "Amazon SES", "Formal, auditable documents — coverage notices and settlement letters"],
        ["Plumbing", "SNS, Lambda, DynamoDB, S3, IAM", "Event routing, tools, shared claim state, storage, security"],
    ]
    tt = Table(tech, colWidths=[22*mm, 62*mm, 90*mm])
    tt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND_BG),
        ("TEXTCOLOR", (0,0), (-1,0), BRAND),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8.3),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("TEXTCOLOR", (0,1), (-1,-1), INK2),
        ("GRID", (0,0), (-1,-1), 0.5, LINE),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, CARD]),
    ]))
    E.append(tt)

    E.append(Paragraph("Where it stands today", h2))
    E.append(Paragraph(
        "The full solution is built and runs end to end. The AI reasoning and the email channel are already wired to "
        "live AWS services — claim triage is produced by a real Amazon Bedrock model, and coverage and settlement "
        "emails are sent through Amazon SES. The messaging channels (WhatsApp, RCS, SMS) are demonstrated in a "
        "controlled simulation for now, and switch to live once the messaging numbers and WhatsApp business account "
        "are provisioned. Nothing in the demo is mocked in a way that hides how the system actually works.", body))

    E.append(Paragraph("Why it matters commercially", h2))
    E.append(Paragraph(
        "We designed this as a reusable engine, not a one-off. The same core re-skins across industries by swapping "
        "the parties and the rules — utilities (outage coordination), retail and logistics (delivery and "
        "installation), healthcare (referrals and scheduling), and finance (dispute resolution). We build it once and "
        "offer a configured version per industry, with a clear path to list it on AWS Marketplace.", body))

    E.append(Paragraph("The opportunity", h2))
    E.append(bullets([
        "Entry into the AWS Communication Developer Services Agentic AI Partner Hackathon, judged November 2026.",
        "Prize pool of 40,000 US dollars, plus a dedicated Best of WhatsApp award sponsored by Meta.",
        "Winners receive go-to-market and enablement support from AWS and a joint case study — direct visibility for "
        "HCLTech's agentic AI practice.",
    ]))

    E.append(Paragraph("What we are asking for", h2))
    E.append(Paragraph(
        "Support to finish the live channel setup (a WhatsApp business number and messaging identities), a short "
        "review of the demo before submission, and sign-off to enter under HCLTech in AWS Partner Central. The build "
        "is ready; the remaining work is provisioning and polish ahead of the October submission window.", body))

    doc.build(E, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
