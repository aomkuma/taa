# Trade journal - Setup OWN confluence rule (design data only)

Charts: `charts/B0/NNN.png` (rule B0 = confluence.py, real costs; trades of 2025-09 .. 2026-02, 267 in all). Each chart:
M1 from 60 minutes before to 120 after the entry (level blue dashed, entry black, stop red, target green, break-even
trigger dotted, exit X, session open purple, US release orange), M5 for 8 hours (EMA20), H1 for 72 hours (EMA20,
EMA50, the H1 chart-read levels). Times UTC. Kind: 1 wrong way, 2 fell short, 3 too early.

60 trades drawn (stratified at random: 18 winners, 16 kind 1, 14 kind 3, 4 kind 2, 4 break-even, 4 time exits);
all 60 read below. "M5 with / against" = where the M5 close stood against a rising / falling M5 EMA20 at the entry,
read off the M5 panel.

## Round 1 - the baseline (B0), 60 trades

| # | when (UTC) | side | result | what the chart showed before the entry | why it lost / won | what a careful trader would have seen |
|---|---|---|---|---|---|---|
| 6 | 09-03 01:35 Asia | buy | stop, kind 1 | a V-spike up of 9 USD in 15 min (ret15 +7.3 ATR) through an M15 level after a fall | bought the top of a spike; normal noise took the 2.7 stop in 2 min | the "support" was a level the spike had just run through - chasing, not buying support |
| 7 | 09-03 12:55 NY | buy | win | 40 min of tight range (rng15 3 ATR) sitting on the level, H1 strong up, day high near | compression on the level broke with the trend | the clean case: quiet base on the level, M5 above a rising EMA20 |
| 8 | 09-04 00:20 Asia | buy | break-even | M5 falling for 6 hours from a top at 3575 (lower highs), H1 tide up only by lag | reached the BE trigger, came back, then collapsed | the last H1 swing was a top; M5 against |
| 12 | 09-05 08:05 London | buy | stop, kind 1 | M5 lower highs for 2 hours; entry 2.4 ATR above the level, mid-air | price came down to the level after the entry and through the stop | entered before price reached the level; M5 against |
| 18 | 09-10 12:31 NY | buy | stop, kind 1 | US release 1 min before; entry at the top of the release spike | the spike reversed | never the minute after a release spike |
| 20 | 09-12 07:08 London | buy | stop, kind 1 | M5 up for 4 h then rolling over (lower high), H1 EMAs tangled, H1 "now" structure turned down | chop around the round number, then down | M5 against, H1 structure against |
| 23 | 09-16 01:55 Asia | buy | stop, kind 2 | a range after a H1 spike; entry 5 min before the window ends | 0.55 of the target, back to the stop | a range, no trend on M5; late in a thin window |
| 26 | 09-18 01:11 Asia | sell | stop, kind 1 | spike up to 3668 then a red crash bar through the level, ATR x2.5 | whipsaw back above the level took the 3 USD stop in 1 min | stop of ~1 ATR in a tape at 2.5x normal ATR is noise |
| 28 | 09-23 01:11 Asia | buy | stop, kind 2 | rally +3.3 ATR in 15 min through round 3750; H1 chart-read structure DOWN | chased, fell back | H1 structure against; chasing |
| 36 | 10-01 00:45 Asia | buy | stop, kind 3 | a range above the Asian low; stop 1 USD under the range low | the range low was swept, then +11 | the stop sat where the obvious sweep goes |
| 37 | 10-01 07:59 London | buy | win | steady staircase up from the London open (ret60 +11 ATR), break to a new H1 high | momentum with the H1 trend | M5 and H1 with; fresh session |
| 38 | 10-01 13:10 NY | buy | stop, kind 1 | fall of 27 USD from the session high (ret60 -5 ATR), M5 lower highs | bought the first bounce of a falling knife | M5 against; wait for a higher low |
| 41 | 10-06 14:14 NY | buy | stop, kind 3 | new day high (pos 1.0), day range 1.25 ADR, ATR x1.8; entry on the level | stop 1.2 ATR from entry, shaken out, then target | stop too close for the tape |
| 42 | 10-06 14:35 NY | buy | time | jump candle to 3955 late in NY, extended day (1.36 ADR) | drifted for 60 min, target came after | late NY, extended day |
| 43 | 10-07 01:16 Asia | buy | stop, kind 1 | crash of 19 USD in 30 min into today's low; first bounce | retest of the low took the stop | falling knife; M5 against |
| 60 | 10-21 00:02 Asia | buy | win | slow drift down into today's low, rng15 2.6 ATR, Asia open | quick pop | quiet approach, compression |
| 62 | 10-21 07:50 London | buy | stop, kind 1 | crash -7 ATR in 60 min, ATR x2.5, H1 slope only +0.06 with a big red H1 bar | the H1 trend was ending; the crash continued | H1 turning; M5 against |
| 66 | 10-22 07:04 London | sell | win | clear H1 downtrend; rally into round 4150 at the London open, sweep above and rejection | pullback sold at resistance with a rejection | H1 trend strong, sweep + rejection |
| 69 | 10-27 01:30 Asia | sell | win | H1 down; sharp rally into the Asian high, spike rejected | same as #66 | rejection wick at the level |
| 70 | 10-27 08:54 London | sell | win | waterfall bar through round 4050 with the H1 trend | momentum continuation, target in 1 min | lucky spike - same shape lost in #6, #28 |
| 84 | 10-30 01:51 Asia | sell | win | H1 down; 40 min of lower highs pressing the round 3950 | compression broke with the trend | M5 with; compression |
| 86 | 10-31 01:05 Asia | buy | win | sweep 5 USD below the Asian low and a V reclaim | quick pop, then the market fell | sweep + reclaim; a fortunate one |
| 88 | 11-04 00:32 Asia | sell | win | M5 lower highs under a falling EMA; broke the M15 level, small pullback | trend continuation | M5 with |
| 99 | 11-12 01:13 Asia | buy | stop, kind 1 | M5 rolling over from 4144 (lower highs); H1 lower high | bought into a falling M5 | M5 against |
| 103 | 11-13 14:38 NY | buy | stop, kind 1 | price broke down through the M15 level then bounced back up into it from below | bought a retest of broken support from below; crash followed | the level had flipped to resistance; M5 against |
| 104 | 11-13 15:07 NY | buy | stop, kind 3 | crash of 20 USD in minutes, ATR x2.3; first bounce | retest, then +10 later | falling knife; wait for the higher low |
| 120 | 11-25 01:25 Asia | buy | win | pullback of 6 ATR into today's low in a steep H1 uptrend (slope +0.85) | trend resumed | strong H1 trend carries a pullback buy |
| 125 | 11-26 14:00 NY | buy | stop, kind 3 | M5 falling under the EMA; bought mid-fall at an M15 level | the fall went on 30 min, then up to the target | M5 against; too early |
| 126 | 11-26 14:35 NY | buy | stop, kind 3 | same day, same picture | same | the same mistake twice |
| 128 | 11-27 01:30 Asia | buy | time | M5 crash from 4165 (M5 against); first bounce | chop, time exit | falling knife |
| 139 | 12-05 00:01 Asia | buy | stop, kind 2 | H1 flat (slope +0.11, close 0.1 ATR over the EMA50), first minute of Asia | chop | no H1 trend; the tide filter let a flat market through |
| 141 | 12-05 13:29 NY | buy | time | H1 range breakout; entry 2.2 ATR above the level | target reached after the 60-min horizon | not at the level |
| 148 | 12-10 09:22 London | sell | time +0.2R | H1 flat (EMAs tangled), slow grind down | too slow for the horizon | no H1 trend |
| 155 | 12-16 13:15 NY | sell | stop, kind 1 | US release 15 min later; H1 EMA20 crossing up | the release spiked up through the stop | never 15 min before a release |
| 158 | 12-18 01:49 Asia | buy | win | fall to today's low, a double bottom (higher low), M5 turned | rally | higher low after the test |
| 160 | 12-18 16:12 NY | buy | win | a 14 USD spike late in NY | target in 2 min, crash 50 min later | lucky spike |
| 165 | 12-26 14:30 NY | buy | stop, kind 3 | entry at the top of a 1-min spike | the spike's wick took the stop in the same minute; target later | chasing a spike |
| 172 | 12-31 01:30 Asia | sell | stop, kind 3 | H1 down; rally of 20 USD into today's high, M5 above a rising EMA | sold into a rising M5; stopped, then down to the target | M5 against; wait for a lower high |
| 173 | 12-31 01:57 Asia | sell | stop, kind 3 | same move, 27 min later, still rising | same | same |
| 178 | 01-02 13:46 NY | buy | stop, kind 1 | crash of 30 USD; H1 chart-read structure DOWN (EMA tide still up by lag) | the fall continued | H1 structure against, M5 against |
| 179 | 01-02 14:45 NY | buy | break-even | same crash, an hour later | BE, then the fall continued | same |
| 186 | 01-06 14:35 NY | buy | win | strong H1 up; consolidation, then a break to a new day high | breakout with the trend | M5 with; compression |
| 187 | 01-06 15:50 NY | buy | stop, kind 3 | late NY (+155m); deep sweep below the level and a V back; ATR x1.8 | retest wick took the stop, then target | stop inside the swept range |
| 188 | 01-07 00:36 Asia | buy | stop, kind 1 | M5 rolling over from a top; big red H1 bar | the top held | M5 against |
| 196 | 01-13 01:40 Asia | buy | stop, kind 3 | sweep below the Asian low to 4576, reclaim; stop at 4578.7 - ABOVE the swept low | the retest of the sweep low took the stop, then +15 | the stop belongs beyond the swept extreme |
| 199 | 01-14 13:40 NY | buy | stop, kind 2 | 10 min after a release; 6-hour flat M5 range (rng240 5 ATR) | chop then a dump | no M5 trend; after a release |
| 208 | 01-23 15:40 NY | buy | break-even | breakout in a strong trend, late NY | BE at 0.6 shook it out by 0.2 USD, then +30 | the break-even cost a winner |
| 212 | 01-28 08:31 London | buy | win | H1 slope +1.1, breakout through round 5300 | spike to the target | strong H1 trend, breakout |
| 215 | 01-29 09:19 London | buy | win | strong H1 up; a deep sweep to 5475 recovered; higher low on the round | trend resumed | higher low after a sweep |
| 219 | 02-03 00:40 Asia | sell | break-even | H1 flat; selling the top of a 90 USD rally, ATR 7.9 USD | BE | the target was 1.2 ATR: noise |
| 223 | 02-06 13:27 NY | buy | win | M5 above a rising EMA, H1 turning up | quick target | M5 with |
| 233 | 02-10 15:57 NY | buy | stop, kind 3 | late NY; crash below the level, first bounce; H1 flat and structure DOWN | stopped (11 USD), target later | falling knife, H1 against |
| 235 | 02-11 08:29 London | buy | stop, kind 3 | drift down into round 5050; stop 1.7 under the round | swept, then trend | stop under a round number gets hunted |
| 244 | 02-17 14:03 NY | sell | stop, kind 1 | sold the bottom of a 50 USD crash (ATR x4.6) | V bounce | chasing a capitulation spike |
| 245 | 02-17 15:10 NY | sell | stop, kind 1 | an hour later, selling at the crash low (support right below) | bounce | selling into support |
| 246 | 02-18 00:00 Asia | sell | stop, kind 1 | the first minute after the rollover; M15 "now" structure turned up | bounce | rollover minute; structure against |
| 253 | 02-20 08:06 London | buy | stop, kind 3 | sweep below the M15 level to 5006; reclaim; stop at 5012, above the swept low | retest took the stop, then +25 | stop beyond the sweep |
| 255 | 02-20 14:38 NY | buy | win | tight flag on the level after an impulse | break | compression on the level |
| 260 | 02-23 13:35 NY | buy | stop, kind 3 | drifting down inside a range onto round 5150; stop just under the round | swept, then +50 | wait for the low to hold |
| 261 | 02-23 14:07 NY | buy | win | same morning: the sweep low held, a higher low formed, M5 turned up at the EMA | +10 | the entry #260 should have waited for |

### Tally of the 60 (by eye)

- M5 against the trade at the entry (close on the wrong side of a falling/rising M5 EMA20): losers 19 of 34
  stopped (#8 12 20 38 43 62 99 103 104 125 126 128 172 173 178 179 188 233 245), winners 2 of 18 (#69 #86).
- Falling knife / chasing a spike (the move into the level > 4-5 ATR in 15-60 min): losers #6 18 28 38 43 62 104
  128 178 233 244 165; winners #70 #160 (both lucky spikes) and #66 #69 #120 #215 (pullbacks *with a rejection* in
  a strong H1 trend).
- H1 chart-read structure against the side while the EMA tide still says "with" (lag): #28 #178 #179 #233 (all
  losers); no winner.
- News: #18 (1 min after), #155 (15 min before), #199 (10 min after) - all losers.
- The stop placed inside the swept range (above the sweep's low for a buy) or 1-2 USD under a round number: #36 #196
  #235 #253 #260 #187 - all kind 3 (stopped, then the target).
- Flat H1 (EMAs tangled, slope ~0): #139 #148 #219 - chop.
- Winners' common shape: quiet approach / compression on the level (#7 #60 #84 #186 #255), or a higher low after a
  sweep (#158 #215 #261), with the M5 on their side.

### Lessons (to test on the earlier design half-years first)

1. **M5 must be with the trade**: for a buy the M5 close above the M5 EMA20 and the EMA20 not falling (mirror for a
   sell). The confluence's "2 of 3 M5 indicators" fire on any small bounce inside an M5 fall; they do not say the
   M5 swing turned.
2. **H1 structure not against**: the chart-read H1 structure (and its "now" read) must not be against the side.
3. **No falling knives / spike chasing**: skip when the last 15 minutes moved more than ~4 ATR (either way) or the
   M1 ATR is over 2x its day median.
4. **No entries from 15 min before to 15 min after a US release.**
5. **The stop beyond the swept extreme**: stop = min(level - 1 ATR, the lowest low of the last 15 min - 0.5 ATR)
   for a buy (mirror for a sell) - still capped at 10 U.
6. Late in the windows (NY after +150m, Asia after +110m) and the rollover minute looked bad - small samples.
