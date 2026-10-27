# Reading weights: evidence, not yet a usable scale

**Result:** I do not recommend assigning a positive trading weight to any reading from this sample. H4 momentum is the strongest lead, but the required direction is not stable across the two supplied halves. The proposed scale therefore has zero weight on every tested reading until forward evidence resolves the split. This is a measurement result, not a change to the frozen rule set 2.

Run the reproducible analysis with:

```powershell
.venv\Scripts\python.exe research/2026-10-26-three-bots/weights.py
```

The script reads `momentum_trades.csv`, prints the statistics below, and writes no files. It does not regenerate trades. “Fit” means the saved `fitted=True` period (n=95); “never seen” means `False` (n=144). They are the requested partitions, not a clean future test: the never-seen rows are older than the fit window. The all-trade baseline is +0.226 R / 40.0% wins in fit and +0.020 R / 35.4% wins in never-seen.

## Timing and eligible readings

I used only decision-time CSV columns: `bot`, `side`, `window`, `regime`, `risk`, and `mom_H1`, `mom_H4`, `mom_D1`. Outcomes (`r`, `out`, MAE/MFE and counterfactual stops) were not predictors. “Momentum behind” is the stored signed momentum multiplied by +1 for BUY and -1 for SELL; the side is already known at the entry decision. `risk` is the entry stop distance.

The producer `momentum.py` forms each frame from history whose index is the bar **open**, then sets `readable = open + frame duration`; `read_at` takes only `readable <= at`. The app live frame is close-stamped, so applying an extra index shift would be wrong. Hand check at a decision `at=2026-10-27 10:00 UTC`: the H4 bucket opened at 08:00 closes at 12:00 and must be excluded; the prior H4 bucket opened at 04:00 closes at 08:00 and may be used. This is the history convention actually used by the CSV producer. No extra indicator or bar join was added here.

## Numeric readings

AUC measures whether a larger reading ranks a winner above a loser (0.50 is chance). “Median ΔR” is the mean R above the half-specific median minus the mean R at/below it. It is descriptive, not a fitted threshold. “Zero ΔR” is the mean R for momentum ≥0 minus the mean R below 0; for risk, zero is not a useful split and is omitted. AUC and mean R answer different questions.

| Reading (behind trade) | Fit n; AUC; corr with R | Fit median ΔR | Never-seen n; AUC; corr with R | Never-seen median ΔR | Decision |
|---|---:|---:|---:|---:|---|
| H1 momentum | 95; 0.331; −0.080 | −0.301 | 144; 0.534; +0.146 | +0.151 | **Reject:** win ranking and R contrast both reverse. |
| H4 momentum | 95; 0.465; +0.036 | −0.025 | 144; 0.629; +0.227 | +0.348 | **Not yet:** useful out of fit, but no fit-half separation and R effect reverses. |
| D1 momentum | 95; 0.499; +0.065 | +0.069 | 142; 0.504; +0.011 | −0.021 | **Reject:** chance-level win separation; median R effect changes sign. Two D1 values are missing. |
| Stop distance (`risk`) | 95; 0.626; +0.002 | −0.029 | 144; 0.526; −0.104 | −0.472 | **Reject:** apparent fit win separation carries no mean-R lift and is absent outside fit. |

The win AUC for H1 actually changes direction (0.331 to 0.534). H4’s AUC crosses 0.50 (0.465 to 0.629), as does the median-split R contrast. D1’s median-split mean-R contrast changes sign. Risk’s median-split R contrast is negative in both halves, with no useful stable R benefit. These failures are not hidden by pooling the halves.

### The locked H4 ≥ 0 reading

The lock reports the mean R among trades passing H4 ≥0. Recomputing from this CSV reproduces those accepted-group means, but the accepted group average alone does not show the reading’s incremental effect:

| Half | H4 ≥0: n, win, mean R | H4 <0: n, win, mean R | Mean-R contrast ≥0 minus <0 |
|---|---:|---:|---:|
| Fit | 81; 38.3%; +0.214 | 14; 50.0%; +0.294 | **−0.080** |
| Never-seen | 118; 40.7%; +0.207 | 26; 11.5%; −0.829 | **+1.037** |

The accepted means are close (+0.214 and +0.207), exactly as Rule set 2 records. But the reading’s within-half contrast flips sign. The fit-side rejected group is only 14 trades, so this is noisy; the rule in the brief still says a sign-flipping reading is not a weight candidate. The evidence supports continuing to measure H4, not turning its accepted-group average into a positive weight now.

## Categorical readings

Each level is compared with every other level in the same half. Cells show `level n / other n; Δ win rate; Δ mean R` (level minus other). Small or empty levels are shown to expose thin evidence, not treated as candidates.

| Reading level | Fit | Never-seen | Assessment |
|---|---:|---:|---|
| Bot = DOWN | 38/57; +16.7 pp; +0.091 R | 46/98; −7.3 pp; −0.454 R | **Reject:** both effects reverse. |
| Bot = RANGE | 34/61; −16.5 pp; +0.074 R | 44/100; +7.9 pp; +0.676 R | **Reject:** win effect reverses; R estimate swings widely. |
| Bot = UP | 23/72; −1.1 pp; −0.212 R | 54/90; −0.4 pp; −0.191 R | Stable weak negative result, not a positive reading to weight. |
| Side = BUY | 36/59; +2.7 pp; +0.168 R | 81/63; +6.5 pp; +0.250 R | **Not independent:** BUY/SELL is determined by bot for both trend bots. A mild same-sign descriptive effect does not establish a portable side weight. |
| Regime = bear | 38/57; −5.3 pp; −0.045 R | 15/129; +5.1 pp; +0.197 R | **Reject:** both signs reverse; unseen cell is small. |
| Regime = bull | 46/49; +2.5 pp; +0.038 R | 105/39; +6.4 pp; −0.181 R | **Reject:** win and R effects disagree; mean-R sign reverses. |
| Regime = mixed | 11/84; +6.2 pp; +0.014 R | 22/122; −15.0 pp; −0.139 R | **Reject:** win effect reverses. |
| Regime = unknown | 0/95; undefined | 2/142; +14.8 pp; +2.580 R | **No evidence:** two trades, none in fit; the striking mean is a tiny-cell artifact. |
| Window = Asia | 31/64; −1.9 pp; +0.140 R | 44/100; −11.7 pp; +0.087 R | No win-rate edge; R effect small and not enough to warrant a weight. |
| Window = London | 19/76; −10.5 pp; −0.259 R | 30/114; +1.6 pp; +0.245 R | **Reject:** win and R effects reverse. |
| Window = NY open | 45/50; +8.4 pp; +0.042 R | 70/74; +8.9 pp; −0.236 R | **Reject:** R effect reverses despite the win-rate pattern. |

Regime `unknown` is produced by two earliest unseen records, and D1 momentum is missing on two records because the rolling 50-bar D1 measure is not yet available. Neither small count supports inference. `risk` is always nonnegative, so its zero split has no comparison group.

## Overlap and selection premium

Momentum readings overlap. Correlations of momentum-behind values are H1/H4 **0.327 fit, 0.267 unseen**; H4/D1 **0.618, 0.411**; H1/D1 **0.216, −0.071**. H4 and D1 especially can double-count similar directional context. The categorical readings overlap too: all 84 DOWN trades are SELL and all 77 UP trades are BUY; only RANGE has both sides (40 BUY, 38 SELL). Bot, side, and regime should not be assigned independent full-strength weights from these marginal tables.

The script estimates best-of-N optimism with 5,000 permutations of R against the same 16 predeclared numeric/one-hot columns (four numeric columns plus categorical levels). The observed maximum absolute feature/R correlation is **0.156**; the 95th percentile of the null maximum is **0.187**. Thus a best-looking marginal correlation this large is not surprising under a no-association model after searching those 16 columns. This estimate is only for linear correlation in this small sample; it does not account for all possible cutoffs or analyst choices, so it is not a correction that makes a candidate significant.

## Proposed weights and next measurement

For the inert `Weight` / `Scale` vessel, the proposed evidence-based weights from this study are:

| Reading | Weight | Direction | Why |
|---|---:|---|---|
| H1 momentum behind | 0.00 | high | Win and mean-R effects reverse between halves. |
| H4 momentum behind | 0.00 | high | Best lead, but both win ranking and mean-R contrast fail the stable-sign requirement. Keep measuring; do not encode the lock’s subgroup mean as a weight. |
| D1 momentum behind | 0.00 | high | AUC is chance in both halves; median-split R effect reverses. |
| Risk / stop distance | 0.00 | — | Win ranking does not translate to R, especially outside fit. |
| Bot, side, regime, session window | 0.00 | — | Marginal effects flip, overlap structurally, or rely on thin groups. |

This is an explicit **no-positive-weight** proposal, rather than a qualified production score: the current readings do not pass the locked sign rule. No threshold is proposed. Rule set 2 remains a separately frozen historical rule and should be judged on its forward journal; this file does not revise it.

**Would not take:** H1, D1, risk, bot, regime, session-window, or side weights from these marginal results. I would also not count H4 and D1 as independent evidence if later data supports both; they correlate substantially.

**Measure next:** prospectively log every eligible entry decision from 2026-10-28 onward with its point-in-time readings, including H4 values for entries accepted and refused by the locked H4 ≥0 rule, then compare realized mean R and win separation on untouched forward data. That supplies the missing comparator and avoids selecting only the trades the current rule allowed.
