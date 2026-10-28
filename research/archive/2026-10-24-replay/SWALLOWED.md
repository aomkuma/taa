# Find what the AI lane swallows

**Read-only report.** I did not write `SWALLOWED.md` or change any files. I found 19 `except` handlers in `app/ai/`; there are **none** in `app/engine/ai_trader.py` or `app/strategy/ai_lane.py`.

## The swallower

The exception is caught at **`app/ai/watcher.py:226`**.

The path is:

1. `AITraderLane._decide()` passes the contents of `suspended.json` to `trader.decide()` (`app/engine/ai_trader.py:191–203`).
2. `trader.decide()` calls `suspended()` before it prompts the provider or writes a decision (`app/ai/trader.py:402`).
3. `suspended()` catches `ValueError`/`TypeError` from `pd.Timestamp(until)` and raises a clearer `ValueError` (`app/ai/trader.py:243–252`).
4. `AIWatcher.on_bar()` catches that exception, logs it, appends a `FAILED` line to `watch_alerts.log`, then returns `None` (`app/ai/watcher.py:226–231`). The replay can continue, but no decision or session-journal entry is written for that wake.

**Proof in the replay artifacts:** `watch_alerts.log` contains repeated `FAILED` lines with `DateParseError: Unknown datetime string format` and the prose suspension note. Its tail shows failures numbered 1365–1370. This confirms the exception was caught and the replay continued. It also means the brief’s “no log line” is not true of the artifacts I inspected: the error is in `watch_alerts.log`, though it is absent from the normal decision/session journal.

The current `suspended.json` contains a valid timestamp, so it does not reproduce the bad input as it stands. The alert log preserves evidence of the malformed value that triggered those failures.

## Exception inventory

**SAFE** means the failure or invalid result is reported through a status, log, alert file, raised error, or stored row. **SILENT** means the handler discards the exception without an error record. “Journal” below means the replay decision/session journal unless a different store is named.

| Handler | What can reach it; what happens next | Journal visibility | Classification |
|---|---|---|---|
| `app/ai/advisory.py:141` | `_num()` receives a value `float()` cannot convert. Returns `None` without logging. | No error marker; a downstream reader may see a missing value. | **SILENT** |
| `app/ai/advisory.py:290` | Provider output fails Pydantic validation. Converts it to a descriptive `ValueError` and raises it. The notes caller records `INVALID`. | Not the trade journal; the advisory note row records status and detail. | **SAFE** |
| `app/ai/notes.py:113` | An unexpected exception escapes `_call()` in synchronous mode. `_failed()` increments stats and logs an error; it does not create a note row for that exception. | No replay decision entry; system log reports it. | **SAFE** |
| `app/ai/notes.py:202` | `check()` rejects a nominally successful answer. Converts it to `Status.INVALID`; `_call()` stores that status and detail in `AINoteRow`. | Not the trade journal; visible in the AI notes record. | **SAFE** |
| `app/ai/providers.py:199` | Anthropic package is unavailable. Returns `Status.ERROR` through `done()`, which logs the result. | Downstream decision or note consumer receives the error status. | **SAFE** |
| `app/ai/providers.py:217` | Anthropic API timeout. Returns `Status.TIMEOUT` with detail and logs via `done()`. | Downstream record can show timeout status and detail. | **SAFE** |
| `app/ai/providers.py:219` | Other Anthropic API errors, including status, rate-limit, and connection errors. Returns `Status.ERROR` with type and detail; logs via `done()`. | Downstream record can show error status and detail. | **SAFE** |
| `app/ai/providers.py:264` | Answer validation fails after a nominal `OK`. Returns `Assessment(Status.INVALID, detail=...)`. | Not necessarily the replay decision journal; the assessment consumer receives an explicit invalid status. | **SAFE** |
| `app/ai/replay.py:231` | `subprocess.run()` times out for the JSON-mode replay provider. Returns `Answer(Status.TIMEOUT, detail=...)`. | Downstream AI record can show timeout. | **SAFE** |
| `app/ai/replay.py:233` | Starting that provider raises `OSError`. Returns `Answer(Status.ERROR, detail=...)`. | Downstream AI record can show error and detail. | **SAFE** |
| `app/ai/replay.py:299` | Codex CLI subprocess times out. Returns `Answer(Status.TIMEOUT, detail=...)`. | Downstream AI record can show timeout. | **SAFE** |
| `app/ai/replay.py:301` | Starting the Codex CLI raises `OSError`. Returns `Answer(Status.ERROR, detail=...)`. | Downstream AI record can show error and detail. | **SAFE** |
| `app/ai/replay.py:384` | A line in Codex’s JSON event stream is malformed. Skips the line and continues without recording it. | The journal may show a final answer but not that an event line was discarded. | **SILENT** |
| `app/ai/replay.py:406` | Provider output is not valid JSON. Returns `Answer(Status.ERROR, detail=...)`. | Downstream AI record can show error and detail. | **SAFE** |
| `app/ai/replay.py:410` | Parsed JSON fails output-schema validation. Returns `Answer(Status.INVALID, detail=...)`. | Downstream AI record can show invalid status and detail. | **SAFE** |
| `app/ai/replay.py:422` | CLI stdout is not valid JSON. Returns `Answer(Status.ERROR, detail=...)`. | Downstream AI record can show error and detail. | **SAFE** |
| `app/ai/replay.py:446` | CLI structured output fails schema validation. Returns `Answer(Status.INVALID, detail=...)`. | Downstream AI record can show invalid status and detail. | **SAFE** |
| `app/ai/schema.py:144` | Assessment output fails Pydantic validation. Raises a descriptive `ValueError`; `assess_with()` converts it to an invalid assessment. | Consumer receives an invalid status and detail. | **SAFE** |
| `app/ai/trader.py:245` | A suspension value cannot be parsed as a timestamp. Raises a descriptive `ValueError` instead of treating the rule as suspended. The watcher catches it at line 226. | No decision/session-journal entry for the failed wake; `watch_alerts.log` records it. | **SAFE** |
| `app/ai/watcher.py:226` | Any exception from a watcher cycle, including the suspension error. Increments failures, logs a traceback, appends to `watch_alerts.log`, and returns `None`. | No decision/session-journal entry for that wake; alert log reports it. | **SAFE** |

## What a journal reader could wrongly conclude

- **`advisory.py:141` — SILENT:** A nonnumeric input becomes `None` with no explanation. A reader could take the resulting absence of a value as ordinary missing data rather than a conversion failure.
- **`replay.py:384` — SILENT:** Malformed Codex event lines disappear. A reader could assume the event stream was complete; the journal only reflects whatever valid events and final answer survived parsing.

For the suspension failure, a reader looking only at the normal journal could conclude that the replay simply had no decision at that time—or that no wake was needed. The separate alert log shows that a wake failed before a decision was produced.

## The future watcher state

This incident is a silent wake-condition failure, not an `except` handler. `wake_reasons()` computes minutes since `last_call`; when that timestamp is in the future, the value is negative. Cooldown, behaviour, plan-level, and heartbeat checks then fail their `minutes >= …` conditions, so the watcher can produce no wakes. The replay journal can consequently report “AI woken 0 times” without revealing the bad state.

`research/2026-10-24-replay/day.py` now has `check_watcher_is_not_ahead()` to stop a replay whose stored `last_call` is later than the requested day. The current `watch_state.json` is for 2025-02-26; the stored state no longer shows the future timestamp described in the brief.

## One change that would have exposed today’s failure

In `AIWatcher.on_bar()`’s exception handler, **append a `FAILED` record containing `as_of` and the exception detail to the same decision/session journal used for successful wakes before returning `None`**. That would make a failed wake visible to the replay report reader without changing the broader flow.
2026-10-27T15:14:44.928167Z ERROR codex_core::session: failed to record rollout items: thread 01a17deb-4b09-7e63-a1ed-a7ab23a49b7c not found