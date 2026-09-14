"""
Builds the Stark Financial / JARVIS model review deck in an analyst-report
("Gartner style") format.

Conventions borrowed from analyst research decks:
  - action titles: every headline is a full-sentence assertion, not a label
  - a Key Findings + Recommended Actions opener before any evidence
  - a Magic Quadrant for the model selection decision
  - a Strategic Planning Assumption callout
  - a risk register with severity and named mitigations
  - a source attribution footer on every evidence slide

Style only. No Gartner branding, logo or marks are used: this is Kaustubh
Patil's own analysis, presented to a fictional client.

    Client : Stark Financial, Consumer Lending
    Model  : JARVIS  (Just A Rather Very Intelligent System)

Usage:  python build_gartner_deck.py
Output: reports/Stark_Financial_JARVIS_Model_Review.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from PIL import Image

# ------------------------------------------------------------------ theme --
NAVY = RGBColor(0x00, 0x28, 0x56)
NAVY_DEEP = RGBColor(0x00, 0x1B, 0x3A)
TEAL = RGBColor(0x12, 0xB2, 0xA6)
TEAL_DK = RGBColor(0x0B, 0x8F, 0x86)
TEAL_TINT = RGBColor(0xE4, 0xF7, 0xF5)
INK = RGBColor(0x10, 0x23, 0x3A)
MUTED = RGBColor(0x56, 0x67, 0x7B)
FAINT = RGBColor(0x8E, 0x9D, 0xAF)
BORDER = RGBColor(0xD8, 0xE0, 0xE9)
PANEL = RGBColor(0xF2, 0xF6, 0xF9)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1E, 0x8E, 0x5A)
GREEN_TINT = RGBColor(0xE8, 0xF5, 0xEE)
RED = RGBColor(0xB8, 0x3A, 0x2E)
RED_TINT = RGBColor(0xFB, 0xEC, 0xEA)
AMBER = RGBColor(0xB5, 0x7C, 0x0E)
AMBER_TINT = RGBColor(0xFB, 0xF3, 0xE1)

HEAD = "Segoe UI Semibold"
BODY = "Segoe UI"
NUM = "Segoe UI Semibold"

SW, SH = Inches(13.333), Inches(7.5)
FIG = "reports/figures"
SOURCE = ("Source: Kaustubh Patil analysis for Stark Financial  ·  n = 307,511 applications  ·  "
          "sealed test n = 46,127  ·  August 2026")

prs = Presentation()
prs.slide_width, prs.slide_height = SW, SH
BLANK = prs.slide_layouts[6]


def _noaf(tf):
    b = tf._txBody.find(qn('a:bodyPr'))
    for t in ('a:normAutofit', 'a:spAutoFit'):
        e = b.find(qn(t))
        if e is not None:
            b.remove(e)
    b.append(tf._txBody.makeelement(qn('a:noAutofit'), {}))


def text(s, txt, left, top, width, height=0.5, size=13, color=MUTED, bold=False,
         italic=False, align=PP_ALIGN.LEFT, font=BODY):
    tb = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame; tf.word_wrap = True; _noaf(tf)
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = txt
    r.font.name = font; r.font.size = Pt(size); r.font.color.rgb = color
    r.font.bold = bold; r.font.italic = italic
    return tb


def card(s, left, top, w, h, fill=CARD, line=BORDER, radius=0.035):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                            Inches(w), Inches(h))
    try:
        sh.adjustments[0] = radius
    except Exception:
        pass
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    sh.shadow.inherit = False
    return sh


def rect(s, left, top, w, h, color):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    return sh


def edge(s, left, top, h, color, w=0.055):
    return rect(s, left, top, w, h, color)


def pill(s, txt, left, top, fill=NAVY, fg=WHITE, size=10.5, line=None):
    w = 0.36 + 0.0135 * size * len(txt)
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                            Inches(w), Inches(0.32))
    try:
        sh.adjustments[0] = 0.5
    except Exception:
        pass
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    sh.shadow.inherit = False
    tf = sh.text_frame; tf.word_wrap = False
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = txt.upper()
    r.font.name = BODY; r.font.bold = True; r.font.size = Pt(size); r.font.color.rgb = fg
    try:
        r._r.get_or_add_rPr().set('spc', '70')
    except Exception:
        pass
    return sh, w


def slide(page=None, source=True):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid(); s.background.fill.fore_color.rgb = WHITE
    rect(s, 0, 0, 13.333, Pt(9) / Pt(72), NAVY)
    rect(s, 0, Pt(9) / Pt(72), 2.4, Pt(4) / Pt(72), TEAL)
    if page:
        text(s, f"{page:02d}", 12.35, 0.24, 0.6, 0.3, size=11, color=FAINT, align=PP_ALIGN.RIGHT)
        text(s, "STARK FINANCIAL  ·  CONSUMER LENDING", 0.68, 0.26, 7.5, 0.3,
             size=9.5, color=FAINT, bold=True)
    if source:
        text(s, SOURCE, 0.68, 7.03, 12.0, 0.32, size=8.5, color=FAINT)
    return s


def head(s, txt, top=0.95, size=26, width=11.95):
    """Action title: a full-sentence assertion."""
    return text(s, txt, 0.68, top, width, 1.15, size=size, color=INK, bold=True, font=HEAD)


def kicker(s, txt, top=0.6, fill=NAVY):
    return pill(s, txt, 0.68, top, fill=fill)[0]


def takeaway(s, left, top, w, h, txt, label="KEY TAKEAWAY", color=TEAL_DK, tint=TEAL_TINT, size=12):
    card(s, left, top, w, h, fill=tint, line=color)
    edge(s, left, top, h, color)
    text(s, label, left + 0.26, top + 0.12, w - 0.5, 0.28, size=9.5, color=color, bold=True)
    text(s, txt, left + 0.26, top + 0.42, w - 0.5, h - 0.5, size=size, color=INK)


def notes(s, txt):
    s.notes_slide.notes_text_frame.text = txt


def image_card(s, path, left, top, w, h, pad=0.18):
    im = Image.open(path); ar = im.size[0] / im.size[1]
    bw, bh = w - 2 * pad, h - 2 * pad
    if bw / bh > ar:
        ih = bh; iw = ih * ar
    else:
        iw = bw; ih = iw / ar
    card(s, left, top, w, h)
    s.shapes.add_picture(path, Inches(left + (w - iw) / 2), Inches(top + (h - ih) / 2),
                         width=Inches(iw), height=Inches(ih))


def magic_quadrant(s, left, top, size, points, x_label, y_label):
    """A Magic-Quadrant-style 2x2: quadrant names in the corners, plotted
    entries, and the selected one emphasised."""
    card(s, left, top, size, size, fill=PANEL, line=BORDER)
    mid = size / 2
    # the Leaders cell is tinted so the eye lands there before reading a word
    lead = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left + mid), Inches(top),
                              Inches(mid), Inches(mid))
    lead.fill.solid(); lead.fill.fore_color.rgb = TEAL_TINT
    lead.line.fill.background(); lead.shadow.inherit = False
    rect(s, left + mid - 0.006, top + 0.1, 0.012, size - 0.2, RGBColor(0xCF, 0xDA, 0xE4))
    rect(s, left + 0.1, top + mid - 0.006, size - 0.2, 0.012, RGBColor(0xCF, 0xDA, 0xE4))

    names = [("CHALLENGERS", left + 0.14, top + 0.1, PP_ALIGN.LEFT),
             ("LEADERS", left + size - 1.44, top + 0.1, PP_ALIGN.RIGHT),
             ("NICHE PLAYERS", left + 0.14, top + size - 0.34, PP_ALIGN.LEFT),
             ("VISIONARIES", left + size - 1.44, top + size - 0.34, PP_ALIGN.RIGHT)]
    for nm, x, y, al in names:
        text(s, nm, x, y, 1.3, 0.26, size=9, color=FAINT, bold=True, align=al)

    for xf, yf, label, sub, col, selected in points:
        cx = left + 0.3 + xf * (size - 0.6)
        cy = top + size - 0.3 - yf * (size - 0.6)
        d = 0.26 if selected else 0.16
        if selected:                       # halo ring so the choice is unmistakable
            h = d + 0.26
            ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - h / 2), Inches(cy - h / 2),
                                      Inches(h), Inches(h))
            ring.fill.background(); ring.line.color.rgb = col; ring.line.width = Pt(1.6)
            ring.shadow.inherit = False
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d / 2), Inches(cy - d / 2),
                                 Inches(d), Inches(d))
        dot.fill.solid(); dot.fill.fore_color.rgb = col
        dot.line.color.rgb = WHITE; dot.line.width = Pt(1.8)
        dot.shadow.inherit = False
        # label on the side with more room, stacked clear of the marker
        wd = 1.85
        if cx - left > size / 2:
            lx, al = cx - d / 2 - wd - 0.1, PP_ALIGN.RIGHT
        else:
            lx, al = cx + d / 2 + 0.1, PP_ALIGN.LEFT
        text(s, label, lx, cy - 0.30, wd, 0.28, size=11, align=al,
             color=INK if selected else MUTED, bold=selected)
        text(s, sub, lx, cy - 0.02, wd, 0.26, size=9, color=FAINT, align=al)

    text(s, y_label, left, top - 0.32, size, 0.28, size=9.5, color=MUTED, bold=True)
    text(s, x_label, left, top + size + 0.1, size, 0.5, size=9.5, color=MUTED, bold=True,
         align=PP_ALIGN.CENTER)


def ruler(s, left, top, width, zones, marker, marker_label):
    h = 0.36
    x = left
    for frac, col, lab in zones:
        w = width * frac
        rect(s, x, top, w, h, col)
        text(s, lab, x, top + h + 0.05, w, 0.45, size=9, color=MUTED, align=PP_ALIGN.CENTER)
        x += w
    mx = left + width * marker
    rect(s, mx - 0.018, top - 0.12, 0.036, h + 0.24, INK)
    text(s, marker_label, mx - 1.2, top - 0.46, 2.4, 0.3, size=11.5, color=INK, bold=True,
         align=PP_ALIGN.CENTER)


def set_cell(c, txt, size=11.5, color=INK, bold=False, fill=CARD, align=PP_ALIGN.LEFT, font=BODY):
    c.fill.solid(); c.fill.fore_color.rgb = fill
    c.margin_left = c.margin_right = Inches(0.13)
    c.margin_top = c.margin_bottom = Inches(0.05)
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = c.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = txt
    r.font.name = font; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color


# ================================================================ 01 COVER ==
# A cold open. No numbers, no agenda: the name, what it does, and who built it.
# The concentric arcs are the deck's own metaphor, a dial with a line drawn on
# it, and a quiet nod to the client's name.
s = slide(source=False)
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0, 0, 2.4, Pt(5) / Pt(72), TEAL)

# arc motif, bleeding off the right edge, built from progressively lighter rings
for r_in, col in ((4.55, RGBColor(0x03, 0x33, 0x60)),
                  (3.50, RGBColor(0x06, 0x3D, 0x6E)),
                  (2.55, RGBColor(0x0A, 0x49, 0x7E)),
                  (1.70, RGBColor(0x0E, 0x59, 0x8E))):
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(11.35 - r_in), Inches(3.75 - r_in),
                              Inches(r_in * 2), Inches(r_in * 2))
    ring.fill.background()
    ring.line.color.rgb = col; ring.line.width = Pt(1.6)
    ring.shadow.inherit = False
core = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(11.35 - 0.62), Inches(3.75 - 0.62),
                          Inches(1.24), Inches(1.24))
core.fill.solid(); core.fill.fore_color.rgb = RGBColor(0x06, 0x3D, 0x6E)
core.line.color.rgb = TEAL_DK; core.line.width = Pt(1.6)
core.shadow.inherit = False
# the threshold line drawn across the dial: the idea the whole deck is about
rect(s, 11.10, 2.45, 0.035, 2.6, TEAL)

text(s, "CONSUMER LENDING  ·  CREDIT DECISIONING", 0.9, 1.72, 9, 0.35,
     size=11.5, color=TEAL, bold=True)
text(s, "JARVIS", 0.9, 2.18, 8.2, 1.5, size=72, color=WHITE, bold=True, font=HEAD)
text(s, "Just A Rather Very Intelligent System", 0.9, 3.52, 8.2, 0.5,
     size=19, color=RGBColor(0xA9, 0xE7, 0xE1))
rect(s, 0.9, 4.18, 1.6, 0.035, TEAL)
text(s, "The engine that decides who Stark Financial lends to,", 0.9, 4.45, 8.6, 0.45,
     size=17, color=RGBColor(0xD2, 0xDF, 0xEC))
text(s, "and what that decision is worth.", 0.9, 4.82, 8.6, 0.45,
     size=17, color=RGBColor(0xD2, 0xDF, 0xEC))
text(s, "Kaustubh Patil", 0.9, 5.72, 6, 0.35, size=14, color=WHITE, bold=True)
text(s, "Built and independently assessed  ·  August 2026", 0.9, 6.06, 7, 0.35,
     size=12, color=RGBColor(0x8F, 0xA8, 0xC2))
notes(s, "Open cold, do not read the slide. Say: this is JARVIS, the engine that decides who we lend "
         "to. In the next few minutes I will show you what it decides, what it is worth, where it "
         "breaks, and what I would do with it. Then go straight to the summary.")

# ====================================================== 02 KEY FINDINGS =====
s = slide(2)
kicker(s, "Executive Summary")
head(s, "JARVIS is ready to deploy, on four conditions")
text(s, "KEY FINDINGS", 0.68, 1.95, 6.0, 0.3, size=10, color=TEAL_DK, bold=True)
findings = [
    ("It beats the incumbent scorecard by a margin that survives three independent tests.",
     "0.774 against 0.757, and the gap holds on a sealed test set."),
    ("The decline threshold is an economic result, not a modelling preference.",
     "Two independent routes both land on 7%."),
    ("A compliance defect was found during this review, and fixing it cost almost nothing.",
     "Gender was an input. Removing it cost 0.0005 accuracy."),
]
y = 2.32
for i, (f, sub) in enumerate(findings, 1):
    card(s, 0.68, y, 6.0, 1.32, fill=PANEL, line=None)
    edge(s, 0.68, y, 1.32, TEAL)
    text(s, str(i), 0.92, y + 0.14, 0.4, 0.3, size=11, color=TEAL_DK, bold=True)
    text(s, f, 1.28, y + 0.12, 5.2, 0.72, size=12.5, color=INK, bold=True)
    text(s, sub, 1.28, y + 0.82, 5.2, 0.4, size=11, color=MUTED)
    y += 1.44

text(s, "RECOMMENDED ACTIONS", 7.0, 1.95, 5.6, 0.3, size=10, color=NAVY, bold=True)
actions = [
    ("Deploy the gender-free pipeline", "and only that variant"),
    ("Issue reason codes on every decline", "already automated, no extra build"),
    ("Monitor drift monthly against a frozen reference", "the tripwire is built and test-fired"),
    ("Route thin-file applicants to a human", "the model's weakest segment"),
]
y = 2.32
for i, (a, sub) in enumerate(actions, 1):
    card(s, 7.0, y, 5.63, 0.97, fill=CARD, line=BORDER)
    edge(s, 7.0, y, 0.97, NAVY)
    text(s, f"{i}.  {a}", 7.26, y + 0.14, 5.1, 0.4, size=12.5, color=INK, bold=True)
    text(s, sub, 7.44, y + 0.52, 4.9, 0.35, size=10.5, color=MUTED)
    y += 1.08
notes(s, "This slide alone should be enough for a decision. Read the three findings, then the "
         "four actions, then say: the rest of this deck is the evidence behind those. If the "
         "someone only has two minutes, this is the two minutes.")

# ========================================================== 03 THE PROBLEM ==
s = slide(3)
kicker(s, "The Business Problem")
head(s, "Two applicants look identical on paper. One of them costs thirteen of the other.")
cw = 5.9
card(s, 0.68, 1.95, cw, 2.5, fill=GREEN_TINT, line=GREEN)
edge(s, 0.68, 1.95, 2.5, GREEN)
text(s, "APPLICANT A", 0.98, 2.14, 5.2, 0.3, size=10.5, color=GREEN, bold=True)
text(s, "Borrows $20,000 and pays every instalment.", 0.98, 2.48, 5.2, 0.5, size=14.5, color=INK)
text(s, "+$1,000", 0.98, 2.95, 5.2, 0.85, size=38, color=GREEN, bold=True, font=NUM)
text(s, "Stark Financial earns its 5% lifetime margin", 0.98, 3.82, 5.2, 0.35, size=11.5, color=MUTED)

card(s, 0.68 + cw + 0.47, 1.95, cw, 2.5, fill=RED_TINT, line=RED)
edge(s, 0.68 + cw + 0.47, 1.95, 2.5, RED)
text(s, "APPLICANT B", 1.35 + cw, 2.14, 5.2, 0.3, size=10.5, color=RED, bold=True)
text(s, "Borrows $20,000 and stops paying after six months.", 1.35 + cw, 2.48, 5.2, 0.5,
     size=14.5, color=INK)
text(s, "−$13,000", 1.35 + cw, 2.95, 5.2, 0.85, size=38, color=RED, bold=True, font=NUM)
text(s, "Stark Financial loses 65% of what it lent", 1.35 + cw, 3.82, 5.2, 0.35, size=11.5, color=MUTED)

card(s, 0.68, 4.65, 11.95, 0.85, fill=NAVY, line=None)
text(s, "Eight in every hundred approved loans turn out to be an Applicant B.",
     1.0, 4.87, 11.3, 0.45, size=18, color=WHITE, bold=True)
takeaway(s, 0.68, 5.65, 11.95, 1.15,
         "The two mistakes do not cost the same, so the value is not in the model's accuracy. "
         "It is in where the approve/decline line is drawn, and that is a money question before "
         "it is a statistics question.", label="WHY THIS IS A BOARD-LEVEL QUESTION")
notes(s, "Slow down on the two numbers. One thousand against thirteen thousand. Say the ratio "
         "out loud: one bad loan costs thirteen good ones. That single fact drives every "
         "decision in the rest of the deck.")

# ============================================================= 04 APPROACH ==
s = slide(4)
kicker(s, "Methodology")
head(s, "Four steps, with the test set sealed until the last one")
steps = [
    ("01", "Assemble", "307,511 applications joined to 1.7M bureau records from other lenders."),
    ("02", "Clean and split", "Sentinel audit, missingness kept as signal, 70/15/15 stratified."),
    ("03", "Engineer", "153 features grouped the way a credit officer already thinks."),
    ("04", "Compete", "Three candidate models, one pipeline, judged once on sealed data."),
]
w, gap = 2.84, 0.24
x = 0.68
for num, title, desc in steps:
    card(s, x, 1.95, w, 2.15, fill=PANEL, line=None)
    edge(s, x, 1.95, 2.15, TEAL)
    text(s, num, x + 0.24, 2.1, 1.0, 0.35, size=13, color=TEAL_DK, bold=True, font=NUM)
    text(s, title, x + 0.24, 2.48, w - 0.45, 0.4, size=14.5, color=INK, bold=True)
    text(s, desc, x + 0.24, 2.92, w - 0.45, 1.05, size=11.5, color=MUTED)
    x += w + gap

card(s, 0.68, 4.35, 11.95, 1.0, fill=NAVY_DEEP, line=None)
text(s, "STRATEGIC PLANNING ASSUMPTION", 1.0, 4.5, 8, 0.28, size=9.5, color=TEAL, bold=True)
text(s, "Leakage is structurally impossible here: every fitted transform lives inside one "
        "pipeline, refitted per fold. The sealed test number is the only one that had to be earned twice.",
     1.0, 4.78, 11.3, 0.5, size=13, color=RGBColor(0xD3, 0xE1, 0xEE))
takeaway(s, 0.68, 5.5, 11.95, 1.3,
         "No class weighting was used, deliberately. The costs are asymmetric, but that "
         "asymmetry belongs in the decision threshold where it can be seen and changed, not "
         "buried inside the model where it cannot.", label="A DECISION WORTH DEFENDING")
notes(s, "Keep this under forty seconds. The sentinel story is the colour if you have time: one "
         "column claimed a thousand years of employment, which turned out to be how the system "
         "recorded pensioners. Otherwise move on.")

# ====================================================== 05 MAGIC QUADRANT ===
s = slide(5)
kicker(s, "Model Selection")
head(s, "Accuracy alone would have picked the wrong model")
magic_quadrant(
    s, 0.68, 1.88, 4.62,
    [(0.12, 0.10, "Prior baseline", "no signal", FAINT, False),
     (0.26, 0.58, "Random forest", "0.758, opaque", MUTED, False),
     (0.80, 0.44, "Logistic scorecard", "0.757, transparent", NAVY, False),
     (0.82, 0.90, "Boosting + SHAP", "0.774, selected", TEAL_DK, True)],
    x_label="COMPLETENESS OF VISION  →  EXPLAINABILITY",
    y_label="ABILITY TO EXECUTE  →  accuracy")

x0 = 6.25
text(s, "HOW TO READ THIS", x0, 1.95, 7.0, 0.3, size=10, color=TEAL_DK, bold=True)
rows = [
    ("The checklist", "Logistic scorecard", "Adds up points like an underwriter with a rulebook. "
     "Total transparency, but it can only draw straight lines.", NAVY),
    ("The panel", "Random forest", "Hundreds of small opinions, then a majority vote. "
     "Accurate enough, but it cannot tell you why it voted that way.", MUTED),
    ("The apprentice", "Gradient boosting", "Each round studies the last round's mistakes. "
     "Sharpest answer, and opaque on its own.", TEAL_DK),
]
y = 2.32
for tag, name, desc, col in rows:
    card(s, x0, y, 6.38, 1.16, fill=CARD, line=BORDER)
    edge(s, x0, y, 1.16, col)
    text(s, tag.upper(), x0 + 0.24, y + 0.12, 3.0, 0.28, size=9.5, color=col, bold=True)
    text(s, name, x0 + 0.24, y + 0.38, 3.0, 0.32, size=13.5, color=INK, bold=True)
    text(s, desc, x0 + 3.05, y + 0.16, 3.15, 0.95, size=10.5, color=MUTED)
    y += 1.26

takeaway(s, x0, 6.02, 6.38, 0.88,
         "SHAP is what moves boosting from Challenger to Leader: same accuracy, now able to "
         "justify every decision.", label="THE DECIDING FACTOR", size=11.5)
notes(s, "This is the slide that answers 'why boosting and not the simple model'. The honest "
         "version: on raw accuracy the forest and the scorecard are nearly tied, and boosting "
         "wins by 1.7 points. But the reason boosting is deployable is SHAP. Without it, it "
         "would sit in Challengers with the forest and I would not recommend it.")

# ========================================================== 06 BENCHMARK ====
s = slide(6)
kicker(s, "Benchmark")
head(s, "0.774 is where a good model should sit on this kind of data")
text(s, "The score is AUROC: given one customer who repays and one who defaults, how often does "
        "JARVIS correctly rank the defaulter as riskier?",
     0.68, 1.9, 11.9, 0.5, size=14, color=INK)
ruler(s, 0.68, 2.95, 11.95,
      [(0.28, RED_TINT, "0.50 to 0.65\ncoin flip to weak"),
       (0.18, AMBER_TINT, "0.65 to 0.70\nusable, not good"),
       (0.30, GREEN_TINT, "0.70 to 0.78\nindustry normal here"),
       (0.24, RGBColor(0xD3, 0xEF, 0xE0), "0.80 and up\nneeds behavioural data")],
      marker=0.685, marker_label="JARVIS: 0.774")

cards = [("0.774", "sealed test AUROC", TEAL_DK), ("0.757", "incumbent scorecard", MUTED),
         ("1 in 3", "of all defaults sit in the riskiest tenth", GREEN),
         ("0.067", "Brier score: the probabilities are honest", GREEN)]
x, w = 0.68, 2.9
for val, lab, col in cards:
    card(s, x, 4.3, w, 1.25, fill=PANEL, line=None)
    edge(s, x, 4.3, 1.25, col)
    text(s, val, x + 0.22, 4.42, w - 0.4, 0.5, size=26, color=col, bold=True, font=NUM)
    text(s, lab, x + 0.22, 4.95, w - 0.4, 0.5, size=10.5, color=MUTED)
    x += w + 0.13

takeaway(s, 0.68, 5.75, 11.95, 1.05,
         "0.80 is not the target and claiming it would be a warning sign. Without behavioural or "
         "transaction history, models on application and bureau data alone land between 0.70 and "
         "0.78. Anything far above that range usually means a leak.", label="READING THE SCALE HONESTLY")
notes(s, "If someone asks 'is 0.774 good': yes, for this data. Say why 0.80 would actually worry "
         "you. That answer is more convincing than the number itself.")

# ========================================================= 07 THE DECISION ==
s = slide(7)
kicker(s, "The Decision", fill=GREEN)
head(s, "The 7% cut-off is where a loan stops making money")
card(s, 0.68, 1.95, 5.85, 1.85, fill=GREEN_TINT, line=GREEN)
edge(s, 0.68, 1.95, 1.85, GREEN)
text(s, "NET BENEFIT ON THE SEALED TEST BOOK", 0.98, 2.12, 5.3, 0.3, size=10.5, color=GREEN, bold=True)
text(s, "+$578.7M", 0.94, 2.42, 5.4, 1.0, size=48, color=GREEN, bold=True, font=NUM)
text(s, "versus approving everyone, across 46,127 applications", 0.98, 3.4, 5.3, 0.35,
     size=11.5, color=MUTED)

card(s, 0.68, 3.95, 5.85, 2.05, fill=PANEL, line=None)
edge(s, 0.68, 3.95, 2.05, TEAL)
text(s, "WHY 7%, AND NOT SOME OTHER NUMBER", 0.98, 4.12, 5.3, 0.3, size=10.5, color=TEAL_DK, bold=True)
text(s, "A good loan earns 5%. A bad one loses 65%.", 0.98, 4.44, 5.3, 0.35, size=13, color=INK)
text(s, "5%  ÷  (5% + 65%)  =  7.1%", 0.98, 4.82, 5.3, 0.5, size=21, color=INK, bold=True, font=NUM)
text(s, "Sweeping the real profit curve over 46,127 loans lands on 7%. Two independent routes, "
        "the same answer.", 0.98, 5.38, 5.3, 0.55, size=11, color=MUTED)

image_card(s, f"{FIG}/deck_profit_curve.png", 6.75, 1.95, 5.88, 3.05, pad=0.10)
for val, lab, x in [("63.2%", "approved at that line", 6.75), ("74.5%", "of future defaults stopped", 9.8)]:
    card(s, x, 5.15, 2.83, 0.85, fill=CARD, line=BORDER)
    edge(s, x, 5.15, 0.85, NAVY)
    text(s, val, x + 0.2, 5.24, 2.5, 0.4, size=20, color=NAVY, bold=True, font=NUM)
    text(s, lab, x + 0.2, 5.62, 2.5, 0.3, size=10, color=MUTED)
takeaway(s, 6.75, 6.15, 5.88, 0.66,
         "It is a dial. Move it and I can price the move.", label="THE POINT", size=11.5)
notes(s, "This is the slide that carries the argument. Say the division out loud: five over seventy "
         "is seven point one. Then say I found the same number a completely different way. If "
         "they push for a higher approval rate, the answer is yes and here is the cost.")

# ====================================================== 08 EXPLAINABILITY ===
# Was a wall of prose. Now: the artefact on the left, the arithmetic that
# produced it on the right, drawn rather than described.
s = slide(8)
kicker(s, "Explainability")
head(s, "Every decline arrives with its reasons already attached")

card(s, 0.68, 1.9, 5.75, 4.05, fill=RED_TINT, line=RED)
edge(s, 0.68, 1.9, 4.05, RED)
text(s, "WHAT THE APPLICANT RECEIVES", 0.98, 2.06, 5.2, 0.3, size=9.5, color=RED, bold=True)
text(s, "“Your application was declined.", 0.98, 2.36, 5.2, 0.38,
     size=14, color=INK, bold=True)
text(s, "The main reasons were:”", 0.98, 2.70, 5.2, 0.38,
     size=14, color=INK, bold=True)
_letter = ["Your external credit score is low",
           "You have amounts past due with other lenders",
           "You are using a high share of your existing credit",
           "Payments elsewhere have been past due"]
_y = 3.28
for _i, _r in enumerate(_letter, 1):
    circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.0), Inches(_y + 0.02), Inches(0.26), Inches(0.26))
    circ.fill.solid(); circ.fill.fore_color.rgb = RED
    circ.line.fill.background(); circ.shadow.inherit = False
    _tf = circ.text_frame; _tf.margin_left = _tf.margin_right = 0
    _tf.margin_top = _tf.margin_bottom = 0; _tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _p = _tf.paragraphs[0]; _p.alignment = PP_ALIGN.CENTER
    _run = _p.add_run(); _run.text = str(_i)
    _run.font.name = BODY; _run.font.size = Pt(9.5); _run.font.bold = True; _run.font.color.rgb = WHITE
    text(s, _r, 1.4, _y, 4.8, 0.36, size=12.5, color=INK)
    _y += 0.46
text(s, "Plain language, no column names. Generated automatically for every decline.",
     0.98, 5.32, 5.2, 0.45, size=10, color=MUTED, italic=True)

# right: the same four reasons, as the contributions that produced the score
card(s, 6.6, 1.9, 6.03, 4.05, fill=PANEL, line=None)
edge(s, 6.6, 1.9, 4.05, NAVY)
text(s, "WHERE THOSE REASONS COME FROM", 6.9, 2.06, 5.4, 0.3, size=9.5, color=NAVY, bold=True)
text(s, "The model returns the score already broken into the factors that built it.",
     6.9, 2.36, 5.45, 0.4, size=12, color=INK)

_f = [("Low external credit score", 2.22),
      ("Amounts past due elsewhere", 0.48),
      ("High utilisation of existing credit", 0.21),
      ("Past-due payment history", 0.21)]
_mx, _bx, _bw = 2.22, 9.62, 2.35
_y = 2.94
for _lab, _v in _f:
    text(s, _lab, 6.9, _y - 0.03, 2.75, 0.34, size=10.5, color=INK)
    rect(s, _bx, _y + 0.04, _bw, 0.2, RGBColor(0xE3, 0xEA, 0xF1))
    rect(s, _bx, _y + 0.04, max(_bw * _v / _mx, 0.05), 0.2, RED)
    text(s, f"+{_v:.2f}", _bx + _bw + 0.1, _y - 0.03, 0.75, 0.3, size=10.5, color=MUTED, bold=True)
    _y += 0.46
rect(s, 6.9, _y + 0.04, 5.45, 0.014, BORDER)
text(s, "These add up to the score exactly", 6.9, _y + 0.14, 3.4, 0.32, size=11.5, color=INK, bold=True)
text(s, "72.6%", 11.35, _y + 0.08, 1.0, 0.42, size=19, color=RED, bold=True, font=NUM,
     align=PP_ALIGN.RIGHT)
text(s, "so the four printed on the letter are the four largest pieces of this "
        "applicant’s own number, not a guess written afterwards.",
     6.9, _y + 0.56, 5.45, 0.6, size=10.5, color=MUTED)

takeaway(s, 0.68, 6.12, 11.95, 0.72,
         "Compliance is not written after the decision. It falls out of the same arithmetic that "
         "made it, so the stated reason can never drift from the real one.",
         label="WHY THIS MATTERS", size=12)
notes(s, "The regulator question is not explain the model, it is justify this decision. The bars on "
         "the right are that applicant’s actual factor contributions, and the four on the letter "
         "are simply the largest of them. Point at the bars, not the paragraph.")

# ========================================================= 09 RISK REGISTER =
s = slide(9)
kicker(s, "Risk Register", fill=AMBER)
head(s, "Three limitations, each with a named control")
rows = [
    ("Macroeconomic shift", "Everyone gets riskier at once and the model does not see it coming.",
     "Drift tripwire, monthly. Test-fired on a simulated severe recession.", "TESTED, NOT PROMISED", GREEN),
    ("No out-of-time validation", "The data carries no dates, so the model cannot be tested against another period.",
     "Monthly retraining plus drift monitoring until dated cohorts exist.", "COMPENSATING CONTROL", AMBER),
    ("Approved-population bias", "JARVIS has only ever seen applicants the old process said yes to.",
     "Thin files route to a human reviewer. Reject inference is first on the roadmap.", "HUMAN IN THE LOOP", NAVY),
]
y = 1.95
for name, risk, control, tag, col in rows:
    card(s, 0.68, y, 11.95, 1.32, fill=PANEL if col != AMBER else AMBER_TINT, line=None)
    edge(s, 0.68, y, 1.32, col)
    text(s, name, 0.95, y + 0.16, 2.9, 0.6, size=13.5, color=INK, bold=True)
    text(s, risk, 3.95, y + 0.18, 4.0, 0.9, size=11, color=MUTED)
    text(s, control, 8.05, y + 0.18, 4.3, 0.7, size=11, color=INK)
    # right-aligned and sat BELOW the control text: a fixed left edge ran off
    # the slide, and mid-height overlapped the second line of the control
    chip_w = 0.36 + 0.0135 * 8.5 * len(tag)
    pill(s, tag, 12.4 - chip_w, y + 0.88, fill=col, size=8.5)
    y += 1.44
text(s, "RISK", 3.95, 1.72, 2.0, 0.25, size=9, color=FAINT, bold=True)
text(s, "CONTROL", 8.05, 1.72, 2.0, 0.25, size=9, color=FAINT, bold=True)
takeaway(s, 0.68, 6.2, 11.95, 0.78,
         "A model whose blind spots are named and instrumented is safer than one that looks flawless.",
         label="POSITION", size=11.5)
notes(s, "Do not rush this. Naming your own limits is what buys credibility for everything else "
         "you claimed. The tripwire being test-fired rather than merely documented is the "
         "strongest point on the slide.")

# ============================================================= 10 FAIRNESS ==
s = slide(10)
kicker(s, "Fairness Audit", fill=RED)
head(s, "The audit failed, and fixing it cost almost nothing")
card(s, 0.68, 1.95, 5.85, 2.35, fill=RED_TINT, line=RED)
edge(s, 0.68, 1.95, 2.35, RED)
text(s, "THE DEFECT", 0.98, 2.12, 5.2, 0.3, size=10.5, color=RED, bold=True)
text(s, "Gender was a model input. That is prohibited in credit decisions regardless of how much "
        "accuracy it buys.", 0.98, 2.45, 5.3, 0.8, size=13, color=INK)
text(s, "Male adverse-impact ratio", 0.98, 3.25, 3.6, 0.3, size=11, color=MUTED)
text(s, "0.75", 4.9, 3.2, 1.4, 0.4, size=17, color=RED, bold=True, font=NUM)
text(s, "Applicants aged 20 to 35", 0.98, 3.62, 3.6, 0.3, size=11, color=MUTED)
text(s, "0.62", 4.9, 3.57, 1.4, 0.4, size=17, color=RED, bold=True, font=NUM)
text(s, "Four-fifths screen: anything below 0.80 is flagged.", 0.98, 3.98, 5.3, 0.3,
     size=10, color=MUTED, italic=True)

card(s, 6.78, 1.95, 5.85, 2.35, fill=GREEN_TINT, line=GREEN)
edge(s, 6.78, 1.95, 2.35, GREEN)
text(s, "THE FIX", 7.08, 2.12, 5.2, 0.3, size=10.5, color=GREEN, bold=True)
text(s, "Retrained the identical model without gender.", 7.08, 2.45, 5.3, 0.4, size=13, color=INK)
text(s, "0.0005", 7.08, 2.85, 5.3, 0.7, size=34, color=GREEN, bold=True, font=NUM)
text(s, "the entire accuracy cost, in AUROC", 7.08, 3.5, 5.3, 0.3, size=11.5, color=MUTED)
text(s, "Age effects remain and are defensible: they are risk-based, and older applicants are "
        "favoured rather than penalised.", 7.08, 3.82, 5.3, 0.45, size=10.5, color=MUTED, italic=True)

card(s, 0.68, 4.55, 11.95, 1.3, fill=NAVY, line=None)
text(s, "RECOMMENDATION:  DEPLOY THE GENDER-FREE PIPELINE, WITH CONDITIONS", 1.0, 4.73, 11.3, 0.4,
     size=15.5, color=WHITE, bold=True)
text(s, "Reason codes on every decline  ·  monthly drift monitoring  ·  quarterly fairness "
        "re-audit  ·  a human lane for thin files  ·  monthly champion/challenger retraining",
     1.0, 5.16, 11.3, 0.5, size=12, color=RGBColor(0xC5, 0xD8, 0xE8))
takeaway(s, 0.68, 6.05, 11.95, 0.75,
         "I would rather find a defect in my own model than have someone else find it in production.",
         label="POSITION", size=12)
notes(s, "Own this. Do not apologise for it. Finding it yourself and pricing the fix at "
         "essentially zero is the strongest governance signal in the entire review.")

# ============================================================= 11 LIVE DEMO =
s = slide(11)
kicker(s, "Live Demonstration")
head(s, "JARVIS, scoring an applicant you choose, right now")
card(s, 0.68, 1.95, 11.95, 2.1, fill=PANEL, line=None)
edge(s, 0.68, 1.95, 2.1, TEAL)
text(s, "I am about to open the underwriting desk, type in an applicant, and let the real model "
        "decide in front of you.", 1.0, 2.15, 11.2, 0.5, size=16.5, color=INK, bold=True)
cols = [("The decision", "probability of default, and approve or decline at the 7% line"),
        ("The money", "expected loss against expected margin, for that exact loan"),
        ("The reasons", "the same four that would appear on the applicant's letter")]
cx = 1.0
for t, sub in cols:
    text(s, t, cx, 2.78, 3.5, 0.3, size=13, color=TEAL_DK, bold=True)
    text(s, sub, cx, 3.08, 3.5, 0.75, size=11, color=MUTED)
    cx += 3.78
takeaway(s, 0.68, 4.28, 11.95, 0.95,
         "Nothing here is pre-recorded. It is the same model artifact validated in this deck, "
         "scoring an applicant chosen in the room.", label="WHY LIVE", size=12.5)
text(s, "Fallback: if the demo misbehaves, the decline letter on slide 8 is the same output from "
        "the same model, and I will talk you through that instead.",
     0.68, 5.45, 11.95, 0.4, size=10.5, color=FAINT, italic=True)
notes(s, "Have the app open at 127.0.0.1:5000 before you arrive here. Click Thin file. Narrate "
         "while it scores. Point at the decision, then the money row, then the reasons. Sixty "
         "seconds. Do not troubleshoot live.")

# ========================================================== 12 ARCHITECTURE =
s = slide(12)
kicker(s, "How It Works")
head(s, "The model decides. The AI only writes it up.")
boxes = [("1", "You type\nthe applicant", "in the browser", NAVY),
         ("2", "The trained model\nscores it", "probability of default", NAVY),
         ("3", "The arithmetic\nexplains it", "which factors, and how much", TEAL_DK),
         ("4", "The AI\nnarrates it", "one plain-English paragraph", AMBER)]
bw, bgap, x = 2.68, 0.48, 0.75
for num, title, sub, col in boxes:
    tint = AMBER_TINT if col == AMBER else (TEAL_TINT if col == TEAL_DK else PANEL)
    card(s, x, 2.1, bw, 1.95, fill=tint, line=None)
    edge(s, x, 2.1, 1.95, col)
    text(s, num, x + 0.22, 2.24, 1.0, 0.3, size=11, color=col, bold=True)
    text(s, title, x + 0.22, 2.56, bw - 0.45, 0.9, size=14, color=INK, bold=True)
    text(s, sub, x + 0.22, 3.44, bw - 0.45, 0.45, size=10.5, color=MUTED)
    if num != "4":
        ch = s.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x + bw + 0.09), Inches(2.94),
                                Inches(0.3), Inches(0.28))
        ch.fill.solid(); ch.fill.fore_color.rgb = RGBColor(0xB9, 0xC6, 0xD4)
        ch.line.fill.background(); ch.shadow.inherit = False
    x += bw + bgap

card(s, 0.68, 4.42, 11.95, 1.45, fill=NAVY_DEEP, line=None)
text(s, "The AI never makes the decision, and it cannot change one.", 1.0, 4.6, 11.3, 0.45,
     size=17, color=WHITE, bold=True)
text(s, "It is handed a decision that has already been made, together with the numbers behind it, "
        "and asked to turn them into a paragraph. Unplug it and the decision, the money and the "
        "four reasons come out identical.", 1.0, 5.05, 11.3, 0.7, size=12.5,
     color=RGBColor(0xC5, 0xD8, 0xE8))
takeaway(s, 0.68, 6.08, 11.95, 0.72,
         "Everything auditable stays deterministic. The only non-deterministic component is the prose.",
         label="WHY IT IS BUILT THIS WAY", size=12)
notes(s, "This is the slide the risk officer cares about. The language model sits strictly "
         "downstream of the decision and is given the numbers as facts. If the network is down "
         "the app writes the paragraph itself and nothing else changes.")

# =========================================================== 13 BOTTOM LINE =
s = slide(source=False)
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0, 0, 2.4, Pt(5) / Pt(72), TEAL)
text(s, "THE BOTTOM LINE", 0.9, 1.6, 8, 0.35, size=11.5, color=TEAL, bold=True)
text(s, "Deploy JARVIS, gender-free,\nwith four conditions.", 0.9, 2.05, 11.5, 1.8,
     size=40, color=WHITE, bold=True, font=HEAD)
items = [("+$578.7M", "net benefit on the sealed book"), ("0.774", "against a 0.757 incumbent"),
         ("7%", "the cut-off, where a loan breaks even"), ("0.0005", "the price of the fairness fix")]
x = 0.9
for val, lab in items:
    text(s, val, x, 4.35, 3.0, 0.55, size=25, color=TEAL, bold=True, font=NUM)
    text(s, lab, x, 4.92, 3.0, 0.5, size=11, color=RGBColor(0xA6, 0xBC, 0xD2))
    x += 3.05
rect(s, 0.9, 5.75, 1.6, 0.03, TEAL)
text(s, "Kaustubh Patil  ·  Stark Financial, Consumer Lending  ·  Questions welcome",
     0.9, 6.0, 11.0, 0.4, size=13, color=RGBColor(0xC5, 0xD8, 0xE8))
notes(s, "Close on the recommendation, not on thanks. Read the four numbers, then stop talking "
         "and let the room come to you.")

prs.save("reports/Stark_Financial_JARVIS_Model_Review.pptx")
print("Saved reports/Stark_Financial_JARVIS_Model_Review.pptx with",
      len(prs.slides._sldIdLst), "slides")
