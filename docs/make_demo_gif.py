"""Render docs/demo.gif: a replay of one real factory job (three review rounds).

Pure Pillow, no browser. Run:  python3 docs/make_demo_gif.py
"""
from PIL import Image, ImageDraw, ImageFont
import os, sys

W, H = 1100, 640
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "demo.gif")

BG = (13, 17, 23)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
AMBER = (210, 153, 34)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
BLUE = (88, 166, 255)
PURPLE = (188, 140, 255)


def font(bold=False, size=16, mono=False):
    names = []
    if mono:
        names = ["DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"]
    else:
        names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for d in ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_TITLE = font(True, 20)
F_BOX = font(True, 15)
F_SMALL = font(False, 13)
F_CHIP = font(True, 12)
F_MONO = font(False, 14, mono=True)
F_MONO_B = font(True, 14, mono=True)
F_CAP = font(True, 17)

STAGES = ["SPEC", "TESTS", "BUILD", "GATE", "REVIEW", "APPROVE", "PR"]
AGENTS = {
    "SPEC": "spec-writer · opus",
    "TESTS": "test-writer · sonnet",
    "BUILD": "builder · opus",
    "GATE": "gate.py hook",
    "REVIEW": "4 in parallel",
    "APPROVE": "approver · opus",
    "PR": "gh pr create",
}
REVIEWERS = ["security", "ux", "ui", "code"]

# Box geometry
BX0, BY, BW, BH, GAP = 34, 120, 128, 74, 22


def box_x(i):
    return BX0 + i * (BW + GAP)


def rr(d, xy, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, r, fill=fill, outline=outline, width=width)


def arrow(d, x0, y, x1, color):
    d.line([(x0, y), (x1 - 6, y)], fill=color, width=2)
    d.polygon([(x1, y), (x1 - 8, y - 5), (x1 - 8, y + 5)], fill=color)


def render(state, log, caption, round_no, pulse):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # Header
    d.text((34, 26), "/factory next", font=F_TITLE, fill=PURPLE)
    tw = d.textlength("/factory next", font=F_TITLE)
    d.text((34 + tw + 14, 29), "job 013 · realtime voice adapter", font=font(False, 17), fill=TEXT)
    rtxt = f"round {round_no}" if round_no else ""
    if rtxt:
        rw = d.textlength(rtxt, font=F_BOX)
        rr(d, (W - 34 - rw - 24, 24, W - 34, 54), 15, fill=PANEL, outline=LINE)
        d.text((W - 34 - rw - 12, 31), rtxt, font=F_BOX, fill=AMBER)
    d.text((34, 70), "spec → failing tests → build → hook gate → 4 reviews → approve → pull request",
           font=F_SMALL, fill=MUTED)

    # Stage boxes
    for i, s in enumerate(STAGES):
        x = box_x(i)
        st = state.get(s, "idle")
        col = {"idle": LINE, "active": AMBER, "done": GREEN, "changes": RED}[st]
        fill = PANEL
        rr(d, (x, BY, x + BW, BY + BH), 10, fill=fill, outline=col, width=3 if st != "idle" else 1)
        tcol = TEXT if st != "idle" else MUTED
        d.text((x + 12, BY + 12), s, font=F_BOX, fill=tcol)
        d.text((x + 12, BY + 38), AGENTS[s], font=font(False, 11), fill=MUTED)
        # status dot
        if st == "active":
            r = 5 + (pulse % 2) * 2
            d.ellipse((x + BW - 22 - r, BY + 19 - r, x + BW - 22 + r, BY + 19 + r), fill=AMBER)
        elif st == "done":
            d.text((x + BW - 28, BY + 9), "✓", font=F_BOX, fill=GREEN)
        elif st == "changes":
            d.text((x + BW - 28, BY + 9), "✗", font=F_BOX, fill=RED)
        if i < len(STAGES) - 1:
            arrow(d, x + BW + 2, BY + BH // 2, x + BW + GAP - 2, LINE if st == "idle" else MUTED)

    # Reviewer chips under REVIEW
    rx = box_x(4)
    chips = state.get("chips", {})
    for k, name in enumerate(REVIEWERS):
        v = chips.get(name)
        y = BY + BH + 10 + k * 25
        col = {None: LINE, "run": AMBER, "PASS": GREEN, "CHANGES": RED}[v]
        rr(d, (rx - 8, y, rx + BW + 8, y + 22), 11, fill=PANEL, outline=col, width=2 if v else 1)
        label = name if v in (None, "run") else f"{name} {v}"
        d.text((rx + 2, y + 4), label, font=F_CHIP, fill=TEXT if v else MUTED)

    # Rework loop arrow REVIEW -> BUILD
    if state.get("loop"):
        bx = box_x(2) + BW // 2
        lx = box_x(4) - 8
        y = BY + BH + 56
        d.line([(lx, y), (bx, y)], fill=RED, width=2)
        d.line([(bx, y), (bx, BY + BH + 8)], fill=RED, width=2)
        d.polygon([(bx, BY + BH + 2), (bx - 5, BY + BH + 10), (bx + 5, BY + BH + 10)], fill=RED)
        d.text((box_x(2) + 4, y + 6), "CHANGES → resume the builder", font=F_CHIP, fill=RED)

    # Terminal panel
    ty = 330
    rr(d, (34, ty, W - 34, H - 76), 10, fill=PANEL, outline=LINE)
    for i, c in enumerate([RED, AMBER, GREEN]):
        d.ellipse((52 + i * 18, ty + 12, 62 + i * 18, ty + 22), fill=c)
    d.text((112, ty + 9), "factory/jobs/013-openai-realtime/", font=F_SMALL, fill=MUTED)
    lines = log[-9:]
    for i, (txt, col, bold) in enumerate(lines):
        d.text((54, ty + 38 + i * 21), txt, font=F_MONO_B if bold else F_MONO, fill=col)

    # Caption bar
    if caption:
        d.text((34, H - 56), caption, font=F_CAP, fill=TEXT)
    return im


frames, durations = [], []
state = {"chips": {}}
log = []
round_no = 0


def snap(caption, ms, pulses=1):
    for p in range(pulses):
        frames.append(render({**state, "chips": dict(state["chips"])}, list(log), caption, round_no, p))
        durations.append(ms // pulses)


def L(txt, col=TEXT, bold=False):
    log.append((txt, col, bold))


snap("One feature request in. Agents take it from here.", 1800)

state["SPEC"] = "active"; snap("The spec-writer turns the request into acceptance criteria.", 1200, 2)
state["SPEC"] = "done"; L("spec.md                 acceptance criteria written", MUTED); snap("The spec-writer turns the request into acceptance criteria.", 700)

state["TESTS"] = "active"; snap("A separate agent writes failing tests before any code exists.", 1200, 2)
state["TESTS"] = "done"; L("tests.md                STATUS: WRITTEN", GREEN, True); snap("A separate agent writes failing tests before any code exists.", 800)

round_no = 1
state["BUILD"] = "active"; snap("The builder works on its own branch and git worktree.", 1300, 2)
state["BUILD"] = "done"; L("build.md                STATUS: READY", GREEN, True)
state["GATE"] = "active"; snap("A hook re-runs lint, typecheck, tests and build. Red means no exit.", 1300, 2)
state["GATE"] = "done"; L("gate.md                 GATE: PASS  (lint · typecheck · test · build)", GREEN, True)
snap("A hook re-runs lint, typecheck, tests and build. Red means no exit.", 600)

state["REVIEW"] = "active"; state["chips"] = {n: "run" for n in REVIEWERS}
snap("Four reviewers run in parallel.", 1300, 2)
state["chips"] = {"security": "CHANGES", "ux": "PASS", "ui": "PASS", "code": "PASS"}
state["REVIEW"] = "changes"; state["loop"] = True
L("round-1/review-security VERDICT: CHANGES", RED, True)
L("  API key can leak, unredacted, through a WebSocket error", MUTED)
snap("Security reviewer: the API key can leak through an error message.", 3200)

round_no = 2
state.update({"BUILD": "active", "GATE": "idle", "REVIEW": "idle", "loop": False}); state["chips"] = {}
snap("The same builder is resumed with the findings.", 1300, 2)
state["BUILD"] = "done"; state["GATE"] = "done"; L("gate.md                 GATE: PASS", GREEN, True)
state["REVIEW"] = "active"; state["chips"] = {n: "run" for n in REVIEWERS}; snap("Round 2: build and gate pass again.", 1200, 2)
state["chips"] = {"security": "CHANGES", "ux": "PASS", "ui": "PASS", "code": "PASS"}
state["REVIEW"] = "changes"; state["loop"] = True
L("round-2/review-security VERDICT: CHANGES", RED, True)
L("  fix incomplete: a key ending in a newline still leaks", MUTED)
snap("Round 2: the fix is incomplete. A key ending in a newline still leaks.", 3200)

round_no = 3
state.update({"BUILD": "active", "GATE": "idle", "REVIEW": "idle", "loop": False}); state["chips"] = {}
snap("Back to the builder, one more time.", 1200, 2)
state["BUILD"] = "done"; state["GATE"] = "done"; L("gate.md                 GATE: PASS", GREEN, True)
state["REVIEW"] = "active"; state["chips"] = {n: "run" for n in REVIEWERS}; snap("Round 3.", 1100, 2)
state["chips"] = {n: "PASS" for n in REVIEWERS}; state["REVIEW"] = "done"
L("round-3/review-*        VERDICT: PASS ×4", GREEN, True)
snap("Round 3: all four reviewers pass.", 1600)

state["APPROVE"] = "active"; snap("The approver checks every criterion against the diff.", 1300, 2)
state["APPROVE"] = "done"; L("decision.md             APPROVE", GREEN, True)
state["PR"] = "active"; snap("The approver checks every criterion against the diff.", 700)
state["PR"] = "done"; L("pr.md                   pull request opened, factory record in the body", BLUE, True)
snap("A pull request opens. A human merges it. Nothing reaches main on its own.", 4200)

frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
print(OUT, len(frames), "frames", os.path.getsize(OUT) // 1024, "KB", sum(durations) / 1000, "s")
