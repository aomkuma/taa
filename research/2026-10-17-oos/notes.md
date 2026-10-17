- 2026-10-17: started at 11:48 Thai; the runs before it (S1 + resume year at 7 of 12 months, S1 on the FX
  majors at 84 % of August with no trade) were stopped for this (owner).
- 2026-10-17 12:30: another session edits `app/strategy/setups.py` in the main tree (the owner's triple screen); from
  then the queue runs the code from a worktree frozen at commit e7cbfc9 (`.claude/worktrees/oos-runner`).
  s1_2024-11, v1_2024-12 and f1_2024-12 had already started from the main tree (f1_2024-12 after the edit):
  to be rerun from the frozen code and compared.
- 2026-10-17 13:10: S1's own stop cap went off in `config.yaml` (owner: no SL_TOO_FAR). The S1 runs here keep
  `config_scalp_s1.yaml` (4.0) like the in-sample year; the cap binds only when the spread exceeds about 2 ATR.
