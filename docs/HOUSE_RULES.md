# House rules

Each of these was paid for with a real mistake, named underneath it. They survive the clearing of
2026-10-28 because they are about how to work, not about what to trade.

## Measuring

**A rule is in force only where its reading reaches the decider, and only on the paths that check it.**
Before calling a rule in force, name its reading and find it in what the decider actually receives, then
list every path that can open a trade and show the check on each. Prefer one check where the paths meet
over one check per path.
*A rule was locked with its number never wired in, so the answerer guessed and guessed the wrong way all
morning while the real value sat at +3.515. Once wired, the morning plan still armed a trade against it,
because that path consulted nothing.*

**An abnormal count stops the report until it is explained.** A zero, a rate that will not move, a window
that does not match what was asked.
*Three failures announced themselves that way in one day and were talked past.*

**Do not conclude from a handful.** Two trades and six trades gave opposite answers about stop width, and
I wrote a confident conclusion from each.
*Three times in one session I stated a conclusion from two to six samples and the next measurement
reversed it.*

**Say what the measurement cannot show.** Which sample it used, whether it was forward or backward, and
what it rests on.
*A filter was adopted on two halves that agreed in mean only, while its effect flipped sign between them.*

## Recording

**Write it down when it happens, not afterwards.** Every trade, every decision, every lesson, in the file
that holds them - never only in conversation.
*A day's results were reported in chat and the journal went unwritten; an issue stayed marked OPEN after
it had been fixed.*

**A run's report belongs in its folder, in the same change as the run, under the name a reader looks for.**
Never an empty file in its place, and say which commit produced the number.
*Four reports went to a gitignored folder while four 0-byte files held their names; a third of a record
was lost until it was recovered by accident.*

**Write the expectation before the reveal.** What you think will happen, in the file, before you look.
*Every time this was skipped, the explanation arrived after the number and fitted it too well.*

## Changing code

**Do not edit `app/` while a multi-process run is in flight.** Each process re-reads the source, so the
days of one run end up on different code.

**Label a planted bug by what it actually catches.** If a planted bug is not caught, find out whether it
is no bug at all or catches something other than its name.
*One labelled "a NaN lean passes" was really the infinite-lean case; NaN refuses by itself.*

**Reproduce any decision-bearing number through the real code path before reporting it.** A harness can be
fed the wrong parameters silently.

## This machine

- `Path.write_text` rewrites a whole file as CRLF here. Use `write_bytes`.
- Bash heredocs eat backslashes. Write files with the editor tools or a Python script.
- `taskkill` does not work from Git Bash; use `os.kill` from the venv. A stopped background task can leave
  a live child still writing files - check a file's mtime before trusting a reset.
- Read the clock with PowerShell `Get-Date`. Git Bash `date` is wrong here.
- Code, comments and documents in English; conversation with the owner in Thai; times to the owner in Thai
  time.

## Code conventions

The old standards are archived at `docs/archive/CODING_STANDARDS.md` and still describe how `app/` is
written: fail closed, closed bars only, timezone-aware UTC through the clock protocol, MetaTrader5 only
inside `app/broker`, volumes floored never rounded up, every schema change a reviewed migration. Follow
them while that code exists. Run `ruff format`, `ruff check`, `mypy app`, `bandit -r app` and the tests
before calling anything done.
