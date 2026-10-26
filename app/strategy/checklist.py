"""The decision checklist's items A-C (research/2026-10-23-entry/DECISION_CHECKLIST.md, owner 2026-10-23:
every item answered in writing before deciding; 2026-10-25: rewritten so no item reads two ways, the AI trader
answers them before every new trade and the code stops a trade whose HARD item failed). A parity test keeps
this copy equal to the document."""

from __future__ import annotations

ITEMS: dict[str, str] = {
    "A1": "Does the D1 side (`d1_big`, hundreds of D1 bars) point the trade's way?",
    "A2": (
        "Is the entry at support / resistance - inside the band (+-0.15 step) of a main or half"
        " line on the trade's stop side - or a pullback (A4) or a through-the-line weapon (W04 "
        "/ W05)?"
    ),
    "A3": (
        "Is the path from the entry to the take-profit point clear of a strong level (the "
        "readers' strong levels) and of a main line's band?"
    ),
    "A4": (
        "Does the M15-H1 trend agree: `h1_rhythm` = the side, and `m15_rhythm` = the side or "
        "`m15_leg` turned to the side after a counter-leg (a pullback ending)?"
    ),
    "A5": "Is the H1 ATR(14) at most 1.1 x its 20-day median (`h1_vol` <= 1.1)?",
    "A6": (
        "Is it inside the owner's windows (`session` asia 07-09 / london 13-15 Thai / ny "
        "08:00-11:30 New York) with no US release within 60 min, or is the weapon W01 when one "
        "is?"
    ),
    "A7": (
        "Is the trade with yesterday's strong day (`yesterday`) and the D1 `phase`, or - if "
        "against a one-way run - is that run spent (`runaway`=none)?"
    ),
    "A8": (
        "Is the trade the trade of one weapon listed under WEAPON now (its conditions hold)? A "
        "weapon of shadow status trades at half size (the code halves it)."
    ),
    "B1": (
        "On the entry frame, do the swings since the level show higher lows AND higher highs "
        "(BUY) or lower highs AND lower lows (SELL), read from swings, not one bar's close?"
    ),
    "B2": (
        "Is a completed chart pattern at the level on the entry frame and on M1 (double / "
        "triple bottom or top, H&S / inverse H&S, a base and its break, a sweep + higher low / "
        "lower high, a channel break, a break and retest, a triangle), with every entry frame "
        "agreeing?"
    ),
    "B3": (
        "Turn trades: was a level everyone sees (the day's, yesterday's or Asia's high / low, a"
        " round 50, a main line) on the stop side swept by >= 0.1 M5 ATR and closed back, the "
        "sweep bar's volume over 1.0 x the mean (`sweep`=low for a BUY, high for a SELL)?"
    ),
    "B4": (
        "If price consolidated at a line (`bars_at_line` >= 8, `m15_range12_atr` < 3), is the "
        "trade in the direction THROUGH the line?"
    ),
    "B5": (
        "If a line was pierced in the last hour (`line_break` up / down) and held, is the trade"
        " WITH the break?"
    ),
    "C1": (
        "Is the entry frame the smallest of M1 / M5 / M15 whose swing covers the 5 USD target, "
        "and is the exit planned on that frame with a time stop (a scalp out at 60 min, longer "
        "only while the entry frame's structure holds; W01 30 min; a turn weapon 120 min, R03)?"
    ),
    "C2": (
        "Is the trade NOT a flip to the other side after this weapon's stop-out in the same "
        "move (a same-side re-entry after a sweep is allowed)?"
    ),
    "C3": (
        "Is the entry within half the pattern's height of where the turn or run starts (the "
        "pattern's extreme / the broken line) - not chasing?"
    ),
    "C4": (
        "Is the stop at or beyond the map's stop for this side (`a SELL's stop beyond it` / `a "
        "BUY's stop beyond it`), beyond the structure that proves the idea wrong, and not "
        "inside any liquidate zone?"
    ),
    "C5": (
        "Is the take-profit point the next swing, at least 5 USD from the entry and short of "
        "the next main line's band? A liquidate zone is never the take-profit point."
    ),
    "C6": (
        "Does the decision state the exits: break-even when price touches +1 R (the code moves "
        "it), half off at +1 R only above 0.01 lot, the time stop (C1), and out when, after "
        "+0.5 R, an entry-frame bar closes against the trade?"
    ),
    "C7": (
        "Is the size the owner's risk percent (the AI's half = half), with the 0.01-lot minimum"
        " recorded, never a veto?"
    ),
    "C8": (
        "Is the entry now - triggered by the last closed entry-frame bar, or by one of the two "
        "before it while price is still within C3's distance - and not a missed trade taken "
        "late?"
    ),
    "C9": (
        "Has the structure this setup is built on NOT yet run its course (its take-profit point"
        " or the next line not reached since it formed)?"
    ),
}

VERDICTS: dict[str, str] = {
    "A1": "yes: it equals the side (up = BUY); no: the opposite; n/a: `none`",
    "A2": "yes: one of them; no: mid-zone and not a pullback; n/a: W01",
    "A3": "yes: clear; no: a strong level or a main band before the take-profit point",
    "A4": (
        "yes: as stated; no: `h1_rhythm` against; n/a: a fade / reclaim weapon that is with "
        "`d1_big` while the M15 / H1 rhythm is not running into the level (L17)"
    ),
    "A5": "yes / no from the reading",
    "A6": (
        "yes: both; no: `session`=none (passes only at confidence >= 70) or a release within 60"
        " min and not W01"
    ),
    "A7": (
        "yes: as stated; no: against them while `runaway` points against the trade; n/a: "
        "`yesterday`=none and `phase`=none"
    ),
    "A8": "yes: a listed weapon; no: none listed, or another weapon's trade",
    "B1": "yes: both; no: one of them only, or the mirror; n/a: W01, W03",
    "B2": (
        "yes: a named pattern whose trigger broke, or a pending order at a plan scenario's "
        "level (the rejection there is the pattern); no: none, half-formed, or a steep arrival;"
        " n/a: W01"
    ),
    "B3": (
        "yes: `sweep` reads the trade's side; no: the other side or none; n/a: continuation "
        "weapons (W01, W03, W04, W05, W08)"
    ),
    "B4": ("yes: through; no: a bounce off the line out of the consolidation; n/a: `bars_at_line` < 8"),
    "B5": (
        "yes: the side = `line_break`; no: the pierced line used as support / resistance "
        "against the break; n/a: `line_break`=none, or a sweep closed back (that is B3)"
    ),
    "C1": "yes: both; no: a frame whose swing cannot reach 5 USD, mixed frames, or no time stop",
    "C2": "yes: not a flip; no: a flip; n/a: no stop-out today on this weapon",
    "C3": "yes: within it; no: farther (B2 once entered 1.7 heights late, F04)",
    "C4": "yes: all; no: nearer than the map's stop, or inside a liquidate zone",
    "C5": (
        "yes: as stated; no: under 5 USD, beyond the band, or at a liquidate zone (a main band "
        "nearer than 5 USD = no trade); the actual TP 10 % short, never under 5 USD (code)"
    ),
    "C6": "yes: all stated; no: missing",
    "C7": "yes / no from the lane",
    "C8": "yes: as stated; no: a look-back entry",
    "C9": (
        "yes: not run; no: reached - a new trade on it is a finished cycle (P24); a same-side "
        "re-entry after a stop-out sweep is not"
    ),
}

DECIDES: dict[str, str] = {
    "A1": "AI",
    "A2": "AI",
    "A3": "AI",
    "A4": "AI",
    "A5": "code R01",
    "A6": "code R09, R07",
    "A7": "AI",
    "A8": "AI (the list: code)",
    "B1": "AI",
    "B2": "AI",
    "B3": "AI (the reading: code)",
    "B4": "AI",
    "B5": "AI",
    "C1": "AI",
    "C2": "AI",
    "C3": "AI",
    "C4": "AI (the map's stop: code)",
    "C5": "AI (the 5 USD floor: code)",
    "C6": "AI",
    "C7": "code",
    "C8": "AI + code (closed bars only)",
    "C9": "AI",
}

KINDS: dict[str, str] = {
    "A1": "WEIGHTED",
    "A2": "WEIGHTED",
    "A3": "WEIGHTED",
    "A4": "WEIGHTED",
    "A5": "HARD",
    "A6": "HARD",
    "A7": "WEIGHTED",
    "A8": "HARD",
    "B1": "WEIGHTED",
    "B2": "WEIGHTED",
    "B3": "WEIGHTED",
    "B4": "WEIGHTED",
    "B5": "WEIGHTED",
    "C1": "WEIGHTED",
    "C2": "HARD",
    "C3": "WEIGHTED",
    "C4": "HARD",
    "C5": "HARD",
    "C6": "WEIGHTED",
    "C7": "code",
    "C8": "HARD",
    "C9": "HARD",
}

# the HARD items the AI answers (the code-decided ones - A5, A6 - are its brakes R01 / R09 / R07)
HARD = tuple(k for k, kind in KINDS.items() if kind == "HARD" and not DECIDES[k].startswith("code"))


def checklist_lines() -> list[str]:
    """The items as the AI reads them: the question, what yes / no / n/a mean, the kind and who decides."""
    return [f"- {k} [{KINDS[k]}; {DECIDES[k]}]: {ITEMS[k]} -- {VERDICTS[k]}" for k in ITEMS]
