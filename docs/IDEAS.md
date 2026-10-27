# Ideas parked for later

Ideas the owner and I discussed that are not tickets yet. Each one says where it came from, what it is, the open
questions and when to come back to it. Nothing here is built or promised.

## 1. Several AI traders, like a fund with a trading desk (2026-10-24)

**From:** the owner, while day 2 of the AI trader replay ran: "can we have several bots watching the charts
together, as if we had a fund with several traders?"

**What already exists:** the engine trades several lanes in one account, with one risk budget, one daily-loss
breaker, correlation groups, a per-symbol position limit and a magic number per strategy (PLAN §A7, TAA-507).

Three ways to staff the desk:

| Way | What it is | Example |
|---|---|---|
| 1. One trader per market | each AI trader watches its own symbol | one on gold, one on EURUSD, one on GBPUSD (the owner's gold + FX majors) |
| 2. Specialists on one market, with a head trader | gold only, split by style; the head trader decides when they disagree | an M1-M5 scalper, an H1 trend trader, a news trader |
| 3. Analysts + one decision maker | several cheaper models each read one angle; the main trader decides | analysts summarise the picture per timeframe or per weapon; the trader picks |

**Open questions:**
- Combined risk: gold and the dollar pairs move together; a risk manager must cap the total when every trader
  leans the same way (correlation groups and the daily-loss breaker exist; their limits for several AI traders
  are not set).
- AI quota: each trader asks about 30-60 questions a day through the CLI (tier 1); several traders hit the plan's
  limit sooner and fall back to the paid API (tier 2) more often.
- One trader first: adding traders before the first one makes money only adds complexity.

**Order I proposed:** (1) make the gold AI trader work (the replay journal now running, TAA-1807); (2) add one
trader per FX major (way 1 - the same code with another symbol); (3) split gold into specialists with a head
trader (way 2) when the journal shows styles that pay in different phases.

## 2. Several trading accounts, one engine per account (2026-10-24)

**From:** the owner: "say I have 5 accounts of 100 USD each - can we log in to 5 MT5 terminals at once and split
the work?"

**It works with the current design:** one MT5 terminal is logged in to one account, and the MetaTrader5 Python
package talks to one terminal per process. So:
1. Install 5 MT5 terminals in their own folders (portable mode), each logged in to its account.
2. Run 5 engines, each with its own `.env`: `MT5_TERMINAL_PATH`, `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER`,
   `ENGINE_DB_URL` (its own SQLite), `health_port`, `ENGINE_ID` / `ENGINE_HMAC_SECRET`.
3. Register each engine for the PWA (`app.cli web engine add`); every account shows in the app.

Ways to split the accounts:

| Split | Example |
|---|---|
| One market per account | account 1 gold, account 2 EURUSD, account 3 GBPUSD, ... |
| One style per account | all gold: account 1 scalps, account 2 trends, account 3 trades the news |
| One risk level per account | the same trader at 3 % / 5 % / 7.5 % a trade, to see which survives better |

Separate accounts keep each portfolio apart (one blown account does not touch the others) and measure each
trader cleanly.

**Open questions:** the machine (an MT5 terminal plus an engine is roughly 300-500 MB; heavy runs next to the
engine crashed it once, 2026-10-07); the AI quota grows with each trader; DEMO is paused and LIVE stays off until
Phase 14 is finished and the owner says so - several real accounts come after that, not before.

**Come back when:** the gold AI trader's replay journal shows it works (idea 1, step 1).
