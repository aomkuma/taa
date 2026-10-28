# Find what the AI lane swallows (2026-10-27)

Read-only. Two other sessions are editing this repo; change nothing. Write only
`research/2026-10-24-replay/SWALLOWED.md`. Use `.venv\Scripts\python.exe`.

## The thread to pull

`app/ai/trader.suspended()` turns the owner's rule suspensions into the set of rules switched off. Given
a value that is not a timestamp it raises - it always did. On 2026-10-27 a prose note was written into
`data/replay/ai/store/suspended.json` and a whole replay day ran **to completion, with no warning, no log
line, and a normal-looking journal**, while every rule stayed in force. The experiment it was meant to
run therefore measured nothing, and the two runs it was compared against were identical - which is the
only reason it was noticed.

So an exception was raised and something ate it. **Find what.**

Then widen the question: **what else does the AI lane hide?** Walk every `except` in `app/ai/`,
`app/engine/ai_trader.py` and `app/strategy/ai_lane.py`, and for each one answer:
- what can reach it;
- what the system does afterwards - does it log, record, alert, or continue silently;
- and whether a reader of the resulting journal could tell that anything went wrong.

The replay machinery is how this system learns, so a failure it cannot show is a failure that teaches
the wrong lesson. Two already happened today: this one, and a watcher state left 17 months in the future
that made "AI woken 0 times" look like a decision instead of a bug.

## What to deliver

1. **The swallower**, named with file and line, and the proof (a reproduction is best).
2. **A table of every `except` in those modules**: what it catches, what it hides, and whether the
   journal would show it. Mark each SAFE (reported one way or another) or SILENT.
3. For every SILENT one: what a reader would wrongly conclude from a journal produced while it fired.
4. **The one change** that would have made today's failure visible, written as a concrete suggestion -
   do not implement it.

Say plainly where you found nothing. Do not propose a broad refactor; the system is running live on a
demo account tonight and the owner has had enough change for one day.
