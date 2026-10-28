# One-way detector adapter handoff

## Delivered path

`M1 parquet + daily tick parquet -> causal frozen TR1 detector -> 11 frozen features -> append-only journal -> score`

Rules are independently implemented in `shadow/detector.py`, `shadow/live_features.py` and `shadow/adapter.py`.
Operational scanning starts no earlier than 2026-10-21 UTC. The adapter finalizes an anchor only after its complete
deadline is present. Missing future M1/ticks stay pending without a database row.

## Verification evidence

- Full P1-only replay checked 192 weekday/session anchors.
- Emitted exactly 138/138 frozen entries with no extras or missing entries.
- Fill time, side, entry, spread, stop, risk and detector fields matched frozen artifacts.
- All 11 features matched the independently verified R2 panel; maximum absolute error was 2.22e-16.
- Twelve real-data truncation cases produced identical detections.
- Operational scan for 2026-10-21, run on 2026-10-20 before data existed, returned `PENDING_M1: 3` and left the
  delivered database empty.

See `ADAPTER_PARITY.json` for machine-readable evidence.

## Operation

Run `scan` over a half-open local-calendar range after M1 and tick files are updated. Reruns are safe: finalized anchor
IDs are immutable and already-processed anchors are skipped. Valid entries are written and scored immediately before
any outcome can be accepted.

The entry adapter never creates outcome labels. The separate verified outcome adapter may run later through `settle`;
it waits for the full 8-hour data horizon and writes both hypothetical FAST and RUNNER paths in one journal event.
The journal verifies both cash/R identities and uses their completion maximum as causal availability.

## Safety

There is no terminal, broker, engine, execution or order import. The historical boundary bypass exists only as the
explicit `operational=False` argument used by parity tests; the CLI never exposes it.
