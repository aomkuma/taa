# XAUUSD M5 profile research - current status

**As of:** 2026-11-01 (Asia/Bangkok)  
**Working folder:** `research/xauusd_poc_m5/`  
**Sample:** FBS-Demo XAUUSD M5 and bid/ask ticks through 2026-10-28; expanded coverage replay uses 264 sessions (184 development / 80 validation).
**Work state:** Paused at the user's request. The latest 1.5x relative-volume confirmation replay was interrupted before producing outputs; it has no result and is not part of the evidence.

## Decision

**No robust winning method has been found in the tested data.** No candidate met the predeclared rule: at least 20 development trades, positive net R in at least two of three chronological development folds, and positive validation net R. Therefore no strategy is selected or recommended for live trading.

A methodological review found that the studies built profiles from raw FBS quote records, while TradingView documents Forex/CFD profiles using lower-timeframe tick volume and price-row allocation. The 2R raw-tick result (+4.77R validation on 12 trades) reversed when recalculated from FBS M1 tick_volume: -7.98R on 7 validation trades, 0 winners. Withdraw the earlier candidate status. The corrected result is still only an FBS proxy, not OANDA. No method is on the forward watch-list.

## Experiments

| Folder | Question | Main result | Decision |
|---|---|---|---|
| [`rolling_6h_m5`](rolling_6h_m5/REPORT.md) | Rolling six-hour edge fade | 316 total; development -72.11R; validation -4.38R | Rejected |
| [`stable_profile_clusters_2026-10-31`](stable_profile_clusters_2026-10-31/REPORT.md) | Frozen profile-cluster rotation / breakout | Rotation validation -2.90R; breakout validation -5.76R | Rejected |
| [`target_sensitivity_2026-10-31`](target_sensitivity_2026-10-31/REPORT.md) | Change target POC to opposite VA edge | Opposite edge validation -8.63R | Rejected |
| [`profile_migration_filter_2026-10-31`](profile_migration_filter_2026-10-31/REPORT.md) | Only trade toward profile POC migration | 43 trades; validation -2.24R | Rejected |
| [`flat_poc_cluster_2026-10-31`](flat_poc_cluster_2026-10-31/REPORT.md) | Require older/recent POC stability | 78 trades; validation -3.43R | Rejected; gate still passed most sessions |
| [`time_stop_cluster_2026-10-31`](time_stop_cluster_2026-10-31/REPORT.md) | Exit after 12 M5 bars | No exits changed; same as baseline | Redundant |
| [`nextbar_rejection_2026-10-31`](nextbar_rejection_2026-10-31/REPORT.md) | Require next-bar break of rejection candle | 25 total; validation 4 trades / -2.36R | Insufficient and negative |
| [`min_reward_risk_2026-10-31`](min_reward_risk_2026-10-31/REPORT.md) | Require executable POC distance >=2R on raw quote bins | Historical validation +4.77R; methodological proxy changed later | Withdrawn; not a candidate |
| [`m1_tick_volume_profile_2026-10-31`](m1_tick_volume_profile_2026-10-31/REPORT.md) | Recalculate profile from M1 tick_volume and price-range allocation | 2R validation -7.98R / 7 trades / 0 wins; baseline -15.98R | No candidate; still FBS vs OANDA mismatch |
| [`bin_size_sensitivity_2026-10-31`](bin_size_sensitivity_2026-10-31/REPORT.md) | Test $0.01, $0.10, $0.50 profile rows | All widths negative in validation; 2R has 0 validation wins | No candidate across widths |
| [`m1_rotation_breakout_2026-10-31`](m1_rotation_breakout_2026-10-31/REPORT.md) | With corrected M1 profile, rotate inside VA or switch to breakout retest | Rotation validation -15.98R; combined -26.83R | Rejected |
| [`same_poc_cluster_2026-10-31`](same_poc_cluster_2026-10-31/REPORT.md) | Require identical POC centers across the two 3h halves | 22 cluster sessions; validation 4 trades / -4.09R | Too sparse and negative |
| [`edge_stop_rotation_2026-10-31`](edge_stop_rotation_2026-10-31/REPORT.md) | Put stop beyond the frozen VA boundary | Validation -11.92R, improved from -15.98R but still negative | Rejected |
| [`close_break_stop_2026-10-31`](close_break_stop_2026-10-31/REPORT.md) | Exit only after M5 closes outside the VA | 36% validation win rate but -21.67R; 16 close stops averaged -2.17R | Rejected; close-stop losses too large |
| [`confirmed_2r_cluster_2026-10-31`](confirmed_2r_cluster_2026-10-31/REPORT.md) | Next-bar confirmation + >=2R | 4 dev trades; 0 validation trades | Rejected; too sparse |
| [`low_efficiency_rotation_2026-10-31`](low_efficiency_rotation_2026-10-31/REPORT.md) | Trade only if six-hour efficiency <=0.25 | 71 total; validation -2.88R | Rejected; almost no change |
| [`directional_breakout_filter_2026-10-31`](directional_breakout_filter_2026-10-31/REPORT.md) | Require directional six-hour regime for breakout retest | Only 2 gated breakouts in development, 0 in validation | Rejected; too sparse |
| [`edge_limit_oco_2026-10-31`](edge_limit_oco_2026-10-31/REPORT.md) | First OCO limit simulation | Stop could already be crossed at fill; close-expiry ordering was wrong | Withdrawn as invalid |
| [`edge_limit_oco_spread_safe_2026-10-31`](edge_limit_oco_spread_safe_2026-10-31/REPORT.md) | Intermediate wider-stop OCO | Dev -89.68R; val -22.95R; residual execution accounting issue found | Superseded |
| [`edge_limit_oco_execution_audited_2026-10-31`](edge_limit_oco_execution_audited_2026-10-31/REPORT.md) | Direct buy-VAL/sell-VAH OCO, quote-audited | Dev -65.57R / 110; val -27.33R / 48; 69 fills stopped at entry quote | Rejected |
| [`edge_limit_oco_inside_va_2026-10-31`](edge_limit_oco_inside_va_2026-10-31/REPORT.md) | Only post OCO when prior M5 close is inside frozen VA | Dev -49.56R / 68; val -13.93R / 31 | Rejected |
| [`edge_limit_oco_cluster_efficiency_2026-10-31`](edge_limit_oco_cluster_efficiency_2026-10-31/REPORT.md) | Add six-hour directional efficiency <=0.25 | Dev -46.49R / 66; val -13.04R / 30 | Rejected |
| [`edge_limit_oco_trend_aligned_2026-10-31`](edge_limit_oco_trend_aligned_2026-10-31/REPORT.md) | Allow edge side aligned with six-hour drift | Dev -24.64R / 36; val -11.83R / 19 | Rejected; <20 development trades |
| [`edge_limit_oco_stable_poc_2026-10-31`](edge_limit_oco_stable_poc_2026-10-31/REPORT.md) | Activate only when POCs across two three-hour halves differ <=$0.50 | Dev -22.44R / 32; val +10.95R / 22; all validation targets in Oct 2026 | No candidate; regime-dependent |
| [`edge_limit_oco_stable_poc_2026-10-31/expanded_coverage`](edge_limit_oco_stable_poc_2026-10-31/expanded_coverage/REPORT.md) | Repeat stable-POC rotation on expanded 264-session coverage | 50 dev / -24.35R; 32 val / +1.50R; every dev fold negative | Rejected; 4/32 validation targets, gain marginal |
| [`edge_limit_oco_stable_poc_2026-10-31/expanded_200bar`](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar/REPORT.md) | Stable-POC rotation using previous 200 completed M5 bars | 15 dev / -14.43R; 8 val / -6.56R; all 23 trades stopped | Rejected; no POC targets |
| [`edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_breakout`](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_breakout/REPORT.md) | Two-close breakout after a 200-bar balanced cluster | 20 dev / -11.00R; 18 val / +3.97R but -$12.96/oz; 1/3 folds positive | Rejected; development and fixed-size PnL negative |
| [`edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_structstop`](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_structstop/REPORT.md) | Same breakout; stop beyond full 200-bar profile extreme | 20 dev / -1.51R; 18 val / +0.02R; price PnL negative in both | Rejected; wider stop did not restore expectancy |
| [`edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_retest`](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_retest/REPORT.md) | Require retest-and-reclaim after two-close 200-bar breakout; wide stop | 9 dev / -1.53R; 6 val / -1.49R; only 15 trades | Rejected; fakeout filter did not improve transfer |
| [`test_breakout_200bar_volfilter.py`](edge_limit_oco_stable_poc_2026-10-31/test_breakout_200bar_volfilter.py) | Require breakout-bar M5 tick volume >=1.5x prior 20-bar median; wide stop | Replay interrupted before trade outputs or summary were written | No result; do not infer performance |
| [`edge_limit_oco_stable_poc_trend_2026-10-31`](edge_limit_oco_stable_poc_trend_2026-10-31/REPORT.md) | Add side alignment to stationary-cluster method | Dev -15.89R / 16; val -8.27R / 8; zero targets | Rejected; too sparse and negative |
| [`edge_limit_oco_stable_poc_1usd_2026-10-31`](edge_limit_oco_stable_poc_1usd_2026-10-31/REPORT.md) | Relax POC drift to $1.00 | Dev -20.88R / 51; val -1.13R / 28; only fold 3 near flat | No candidate |
| [`edge_limit_oco_stable_poc_2usd_2026-10-31`](edge_limit_oco_stable_poc_2usd_2026-10-31/REPORT.md) | Relax POC drift to $2.00 | Dev -36.67R / 67; val -20.37R / 35 | Rejected |
| [`edge_limit_oco_stable_poc_1usd_tp1r_2026-10-31`](edge_limit_oco_stable_poc_1usd_tp1r_2026-10-31/REPORT.md) | Change target from POC to fixed 1R | Dev -26.79R / 51; val -19.10R / 28 | Rejected |
| [`edge_limit_oco_stability_ratio_5pct_2026-10-31`](edge_limit_oco_stability_ratio_5pct_2026-10-31/REPORT.md) | Normalize half-POC drift to 5% of VA width | Dev -30.62R / 44; val +10.60R / 18; all dev folds negative | No candidate |
| [`edge_limit_oco_hvn_cluster_2026-10-31`](edge_limit_oco_hvn_cluster_2026-10-31/REPORT.md) | Require >=25% of six-hour tick volume within 5% of VA width around POC | 17 trades; all stopped; dev -6.42R / 12, val -2.52R / 5 | Rejected; too sparse and negative |
| [`sweep_reclaim_6h_2026-10-31`](sweep_reclaim_6h_2026-10-31/REPORT.md) | Enter after a six-hour VA-edge sweep closes back inside; stop past signal wick, target POC | 59 trades; dev -4.81R / 38, val -10.06R / 21; 1/3 dev folds positive | Rejected; negative validation |
| [`edge_limit_oco_raw_ticks_2026-10-31`](edge_limit_oco_raw_ticks_2026-10-31/REPORT.md) | Rebuild six-hour profile from direct FBS quote updates per $0.10 price bin; same OCO rules | 157 trades; only 4 targets; dev -70.82R / 109, val -19.59R / 48 | Rejected; worse than OHLC allocation proxy |
| [`edge_limit_oco_profile_extreme_stop_2026-10-31`](edge_limit_oco_profile_extreme_stop_2026-10-31/REPORT.md) | Put stop beyond frozen six-hour profile low/high, keep VAL/VAH entry and POC target | 158 trades; dev -0.05R / 110, val -4.01R / 48; dev folds inconsistent | No candidate; validation negative |
| [`edge_limit_oco_profile_extreme_stop_2026-10-31/expanded_coverage`](edge_limit_oco_profile_extreme_stop_2026-10-31/expanded_coverage/REPORT.md) | Repeat VAL/VAH limit rotation with broader 264-session coverage | 182 dev / -7.04R; 80 val / -12.01R; only last dev fold positive | Rejected; broader coverage worsened both periods |
| [`edge_limit_oco_extreme_stop_balance_2026-10-31`](edge_limit_oco_extreme_stop_balance_2026-10-31/REPORT.md) | Add six-hour directional efficiency <=0.25 to full-range-stop OCO | 158 trades; dev +0.26R / 110, val -3.42R / 48; fold 1 -12.97R | Rejected; validation negative and gate weak |
| [`edge_limit_oco_extreme_stop_stablepoc_2026-10-31`](edge_limit_oco_extreme_stop_stablepoc_2026-10-31/REPORT.md) | Require half-profile POCs within $0.50, with full-range stops | 107 trades; dev -6.99R / 73, val -3.86R / 34; 1/3 folds positive | Rejected |
| [`edge_limit_oco_extreme_stop_trend_2026-10-31`](edge_limit_oco_extreme_stop_trend_2026-10-31/REPORT.md) | Only buy VAL with rising 6h drift / sell VAH with falling drift, full-range stop | 59 trades; dev +0.75R / 37, val -5.11R / 22; 2/3 dev folds positive | Rejected; validation negative |
| [`poc_retest_continuation_2026-10-31`](poc_retest_continuation_2026-10-31/REPORT.md) | Trend-aligned rejection/retest at frozen POC; target opposite VA edge | 32 trades; dev -14.65R / 19, val -3.07R / 13; all dev folds negative | Rejected; sparse and negative |
| [`poc_migration_retest_2026-10-31`](poc_migration_retest_2026-10-31/REPORT.md) | Require >=$0.50 half-profile POC migration; trade close-confirmed POC retest toward VA edge | 27 trades; dev -16.09R / 18, val -4.06R / 9; all dev folds negative | Rejected; sparse and negative |
| [`entry_hour_audit_2026-10-31`](entry_hour_audit_2026-10-31/REPORT.md) | Exploratory UTC-hour breakdown of full-range-stop OCO | 06:00 UTC dev +4.12R / 8 but val -1.30R / 2; 00:00 UTC val -1.65R / 34 | No time window supported; post-hoc diagnostic only |
| [dukascopy_crossfeed_2026-10-31](dukascopy_crossfeed_2026-10-31/REPORT.md) | Re-test cluster edge strategy on independent Dukascopy bid/ask M1 feed; compare 3h/6h/12h | Best validation +2.50R / 12 trades (12h structural stop), but dev -6.33R; other setups negative | No candidate; feed and regime transfer failed |
| [cluster_lifecycle_2026-10-31](cluster_lifecycle_2026-10-31/REPORT.md) | Keep frozen cluster active until invalidation; also test M5 edge sweep-and-reclaim | Best dev +2.23R / 24 (12h reclaim), validation -9.13R / 16 | No candidate; development edge did not transfer |

| [`atr_stop_sensitivity_2026-10-31`](atr_stop_sensitivity_2026-10-31/REPORT.md) | Replace tight/full-range stop with 0.1–1.0 M5 ATR offsets on the same limit entries | Every ATR stop had negative development folds and validation; full-profile stop remained least negative | No candidate; stop width alone does not repair edge entries |
| [`balance_breakout_retest_2026-10-31`](balance_breakout_retest_2026-10-31/REPORT.md) | After balance cluster, enter retest in direction of two-close M5 breakout | 6h validation -3.54R / 28; 12h validation -7.01R / 23; one positive dev fold each | Reject; continuation retest also failed |
| [`balance_breakout_close_2026-10-31`](balance_breakout_close_2026-10-31/REPORT.md) | Enter at next M1 open after two M5 closes outside frozen VA; target one VA width | 12h dev +20.72R / 41 and 3/3 positive dev folds; validation -12.54R / 21 | Reject; clear regime failure on holdout |
| [`fbs_breakout_close_2026-11-01`](fbs_breakout_close_2026-11-01/REPORT.md) | Re-run 12h confirmed breakout on expanded FBS coverage; require entry quote within 60s | 62 dev / +27.51R; 33 val / -6.02R; fold 1 -7.91R | Rejected; coverage expansion did not fix validation |
| [`partial_poc_targets_2026-10-31`](partial_poc_targets_2026-10-31/REPORT.md) | Exit at 50/70/78/88/100% of distance to POC with structural stop | Best val -1.80R (12h/70%); all 12h development folds negative; 78/88% negative | No candidate; earlier targets do not repair expectancy |
| [`breakout_breakeven_2026-10-31`](breakout_breakeven_2026-10-31/REPORT.md) | Move breakout stop to entry after +0.5R / +1R | 12h development edge erased and validation worsened; 6h validation improved but remained -7.33R | Reject; BE management does not fix transfer |
## Data and execution limits

- Earlier experiments counted raw FBS quote records per $0.10 bin. The method-corrected run uses FBS M1 `tick_volume` spread across price rows from M1 OHLC ranges, which is closer to TradingView's documented lower-timeframe tick-volume method, but remains an approximation.
- The screenshot is OANDA and local history is FBS-Demo. Exact OANDA VP levels cannot be inferred from FBS. The M1 tick volume is broker-specific activity, not centralized XAUUSD trade volume.
- Bid/ask fills use raw FBS quote ticks; commission and extra slippage are not included. TradingView describes Volume Profile as reactive and the 70% VA as a configurable convention ([basic concepts](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/)).
- All data currently ends at 2026-10-28. The 48-session validation block is historical and partly inspected through earlier experiments; repeated strategy search further weakens its value as a holdout.
- A backtest can reject weak ideas; it cannot prove future profitability. A candidate needs fresh forward quotes, enough trades, and full costs before it is a method to trust.

## Next evidence needed

No candidate remains after correcting the profile proxy. Before further testing, obtain feed-matched OANDA M1 volume/quotes and the custom indicator row settings, or continue with FBS while clearly treating it as a separate broker-specific study. The revised data requirements are in [`FORWARD_VALIDATION.md`](FORWARD_VALIDATION.md).

Detailed protocols, scripts, CSVs and reports are in each linked experiment folder.

The OANDA M1 acquisition and normalization path is prepared in [`oanda_feed/README.md`](oanda_feed/README.md), [`oanda_feed/fetch_candles.py`](oanda_feed/fetch_candles.py), [`oanda_feed/prepare_candles.py`](oanda_feed/prepare_candles.py), [`oanda_feed/backtest_oco_m1.py`](oanda_feed/backtest_oco_m1.py), and [`oanda_feed/BACKTEST_PROTOCOL.md`](oanda_feed/BACKTEST_PROTOCOL.md). No `OANDA_API_TOKEN` is configured in the current environment, so feed-matched historical tests have not been run. The earlier FBS development/validation parameter search is not a substitute for OANDA validation.



## Cross-feed update (2026-10-31)

The 6h lookback is a test parameter, not a factually required limit. Dukascopy bid/ask M1 replay on the same 158-session split tested 3h, 6h, and 12h clusters. No variant met the development-fold and validation selection rule. The best validation result (+2.50R / 12 trades at 12h) had negative development (-6.33R). A later 12h breakout market-entry rule had +20.72R and 3/3 positive development folds, then -12.54R / 21 trades in validation. A 12h sweep/reclaim setup had +2.23R / 24 development trades but -9.13R / 16 validation trades. See the independent [Dukascopy report](dukascopy_crossfeed_2026-10-31/REPORT.md) and [cluster lifecycle report](cluster_lifecycle_2026-10-31/REPORT.md). This is not an OANDA replication; profile allocation is M1 volume spread across candle ranges and execution uses M1 bid/ask OHLC.



The 12h sweep/reclaim signal was also stratified by rejection-candle strength. Requiring a close at least 25% of the candle range back inside the VA left 9 validation trades at -9.81R with no winners. This rejects the stronger-close filter in this sample; details are in the lifecycle trades and report.



A cluster-breakout continuation test was also run to address losses from fading directional moves. After two M5 closes outside the frozen VA, it entered a retest toward a one-VA-width measured target. The 6h and 12h versions returned -3.54R and -7.01R on validation; neither passed the fold consistency rule. Full results: [breakout-retest report](balance_breakout_retest_2026-10-31/REPORT.md).



A market-entry breakout after two M5 closes outside value was also tested. The 12h variant returned +20.72R over development and was positive in all three development folds, then lost -12.54R on 21 validation trades (3 targets, 18 stops). Trend alignment reduced the validation loss to -9.25R / 18, still negative. This is a particularly clear example of in-sample consistency failing in the later regime; see [breakout close-entry report](balance_breakout_close_2026-10-31/REPORT.md).




A partial-target test covering 50%, 70%, 78%, 88%, and 100% of the entry-to-POC path found no robust improvement. The 12h/70% target had the least-negative validation (-1.80R / 23), but all three development folds were negative. The requested 78% and 88% targets were also negative in both periods; see [partial POC target report](partial_poc_targets_2026-10-31/REPORT.md).



Moving the confirmed-breakout stop to entry after +0.5R or +1R did not fix transfer. The 12h development gain disappeared and validation worsened to -13.36R / -17.56R. The 6h +0.5R BE rule improved validation to -7.33R but development was -15.24R with only one positive fold. See [break-even stop report](breakout_breakeven_2026-10-31/REPORT.md).




The user confirmed that no OANDA feed is available and authorized continuing with FBS while clearly stating the feed mismatch. An expanded-coverage replay dropped the dependency on the previous session's coverage and admitted sessions with at least 90% of expected M5 bars; entries still required a fresh FBS quote within 60 seconds. This increased the sample from 158 to 264 sessions and from 58 to 95 trades. The 12h breakout remained negative in validation (-6.02R / 33), with development fold 1 at -7.91R despite +27.51R overall development. This is additional evidence against the breakout setup, not an OANDA result or a selected strategy. Full protocol and output: [expanded FBS breakout report](fbs_breakout_close_2026-11-01/REPORT.md).

Two edge-fade variants were also replayed on the same expanded 264-session coverage. The unfiltered VAL/VAH-to-POC rotation lost -7.04R in development and -12.01R in validation; adding a stable-POC gate produced -24.35R development (all three folds negative) and only +1.50R validation on 32 trades, with four targets. These tests do not support buying/selling profile edges as a standalone rule, even when the profile looks more stationary. See the [expanded edge-rotation report](edge_limit_oco_profile_extreme_stop_2026-10-31/expanded_coverage/REPORT.md) and [expanded stable-POC report](edge_limit_oco_stable_poc_2026-10-31/expanded_coverage/REPORT.md).

To match the 200-bar input suggested by the TradingView indicator more directly, I also tested a profile over the previous 200 completed M5 bars (not a fixed 1,000 wall-clock minutes, so market closures do not distort the count). With the stable-POC/overlap/low-efficiency gate and VAL/VAH-to-POC rotation, 23 sessions traded; all 23 stopped, including all 8 validation trades (-6.56R). This rejects this specific long-window fade rule. Details and reproducible outputs: [200-bar expanded report](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar/REPORT.md).

Using that same 200-bar balance cluster, I also tested a two-close breakout, with a stop just back inside the broken VA edge and a one-VA-width target. It made +3.97R on 18 validation trades, but development lost -11.00R across 20 trades and only 1/3 development folds was positive; price PnL was negative in both splits. The validation gain clustered in Aug 2026. It therefore fails the selection rule and is not a candidate. See [200-bar breakout report](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_breakout/REPORT.md).

To address wider protective stops and possible false breaks, the same 200-bar breakout was also replayed with stops outside the full profile high/low. Target exits rose to 17/38 and stop exits fell to 7, but price PnL was -$80.96/oz development and -$58.04/oz validation; net R was -1.51R and +0.02R respectively, with only one positive development fold. Wider stops did not repair the edge. Full report: [200-bar structural-stop report](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_structstop/REPORT.md).

Responding to the concern about false breaks, I tested a retest-and-reclaim entry after two M5 closes outside the 200-bar value area, allowing up to 12 bars for the first retest and using the wide profile-extreme stop. The rule reduced the sample to 15 trades but returned -1.53R development and -1.49R validation; the wide-stop losers were large. Full report: [200-bar retest report](edge_limit_oco_stable_poc_2026-10-31/expanded_200bar_retest/REPORT.md).

**Paused, no-result run:** A relative-volume breakout filter (signal M5 tick volume >=1.5 times the median of the prior 20 M5 bars) was started after the retest study. The user requested a pause before the chronological replay finished. No trades, summary CSV, or report were produced for this filter, so it has not been evaluated. The script is retained for a future resumption at [`test_breakout_200bar_volfilter.py`](edge_limit_oco_stable_poc_2026-10-31/test_breakout_200bar_volfilter.py).
