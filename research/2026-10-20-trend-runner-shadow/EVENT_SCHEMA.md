# Shadow event schema

All timestamps are ISO-8601 UTC. JSON may contain one object or a list of objects.

## Opportunity

```json
{
  "trade_key": "forward-unique-key",
  "entry_time": "2026-10-21T08:31:00Z",
  "anchor": "2026-10-21T08:00:00Z",
  "window": "LONDON",
  "side": 1,
  "entry": 2675.50,
  "spread": 0.20,
  "stop": 2669.50,
  "risk": 6.0,
  "features": {
    "h1_flow_6_atr": 0.25,
    "h4_flow_3_atr": 0.40,
    "open_space_atr": 1.20,
    "h1_atr_percentile_120": 0.65,
    "risk_h1_feature": 0.28,
    "pullback_ratio_feature": 0.42,
    "anchor_entry_minutes": 31.0,
    "side_feature": 1.0,
    "session_asia": 0.0,
    "session_london": 1.0,
    "prior_session_runner_edge": 0.10
  }
}
```

The upstream detector owns entry/fill/stop construction. `spread` is the executable quote spread at the frozen
entry tick and is required by the RUNNER structure-stop buffer. Every price feature must use only bars available no later
than `entry_time`; the prior-session feature may use only outcomes completed before entry.

## Outcome

```json
{
  "trade_key": "forward-unique-key",
  "fast_exit_time": "2026-10-21T09:31:00Z",
  "runner_exit_time": "2026-10-21T15:12:00Z",
  "fast_r": 2.0,
  "runner_r": 1.5,
  "fast_usd_fixed_001": 12.0,
  "runner_usd_fixed_001": 9.0
}
```

Each USD value must equal its R value times initial risk. The event is accepted only after both hypothetical FAST and
RUNNER paths complete, because the frozen session-history feature is mean `RUNNER - FAST`. The opportunity must
already have frozen decisions. Outcomes never update an existing decision or monthly model snapshot.
