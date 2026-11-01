"""Download OANDA v20 M1 candles with mid, bid, ask and price-update volume.

Authentication is read only from OANDA_API_TOKEN in the process environment.
The token is never written to disk or printed. This script only reads pricing data.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}
PAGE_DAYS = 3  # 4,320 possible M1 bars, below OANDA's 5,000-candle page limit.
FIELDS = [
    "time", "complete", "volume",
    "mid_o", "mid_h", "mid_l", "mid_c",
    "bid_o", "bid_h", "bid_l", "bid_c",
    "ask_o", "ask_h", "ask_l", "ask_c",
]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamps must include a UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class OandaClient:
    def __init__(self, environment: str, token: str, timeout: int = 45):
        self.base_url = BASE_URLS[environment]
        self.token = token
        self.timeout = timeout

    def get_json(self, path: str, params: dict[str, str] | None = None) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query}"
        for attempt in range(5):
            request = Request(
                url,
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                method="GET",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
                if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else 2 ** attempt
                    except ValueError:
                        delay = 2 ** attempt
                    time.sleep(min(max(delay, 1.0), 30.0))
                    continue
                raise RuntimeError(f"OANDA returned HTTP {exc.code}: {detail}") from None
            except URLError as exc:
                if attempt < 4:
                    time.sleep(min(2 ** attempt, 30))
                    continue
                raise RuntimeError(f"Could not reach OANDA: {exc.reason}") from None
        raise RuntimeError("OANDA request failed after retries")

    def account_id(self, configured: str | None) -> str:
        if configured:
            return configured
        response = self.get_json("/v3/accounts")
        ids = [str(account["id"]) for account in response.get("accounts", []) if account.get("id")]
        if len(ids) != 1:
            raise RuntimeError(
                "Set OANDA_ACCOUNT_ID when the token has zero or multiple accounts; "
                "the account ID is read from the environment and is not printed."
            )
        return ids[0]

    def candles(self, account_id: str, instrument: str, start: datetime, end: datetime) -> list[dict]:
        params = {
            "price": "MBA",
            "granularity": "M1",
            "from": iso_z(start),
            "to": iso_z(end),
            "includeFirst": "true",
            "smooth": "false",
        }
        path = f"/v3/accounts/{account_id}/instruments/{instrument}/candles"
        response = self.get_json(path, params)
        return response.get("candles", [])


def flatten(candle: dict) -> dict[str, object]:
    row: dict[str, object] = {
        "time": candle["time"],
        "complete": bool(candle.get("complete", False)),
        "volume": int(candle.get("volume", 0)),
    }
    for component in ("mid", "bid", "ask"):
        values = candle.get(component, {})
        for short, key in zip(("o", "h", "l", "c"), ("open", "high", "low", "close")):
            value = values.get(short)
            row[f"{component}_{short}"] = float(value) if value is not None else ""
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=parse_utc, help="UTC start, e.g. 2026-01-01T00:00:00Z")
    parser.add_argument("--end", required=True, type=parse_utc, help="UTC end, exclusive")
    parser.add_argument("--instrument", default="XAU_USD")
    parser.add_argument("--environment", choices=sorted(BASE_URLS), default=os.getenv("OANDA_ENVIRONMENT", "practice"))
    parser.add_argument("--out", type=Path, required=True, help="Output CSV path; must not already exist")
    args = parser.parse_args()
    if args.end <= args.start:
        parser.error("--end must be later than --start")
    if args.environment not in BASE_URLS:
        parser.error("OANDA_ENVIRONMENT must be 'practice' or 'live'")
    token = os.getenv("OANDA_API_TOKEN")
    if not token:
        parser.error("OANDA_API_TOKEN is not set in this process environment")
    if args.out.exists():
        parser.error(f"output already exists; choose a new path: {args.out}")
    partial_out = args.out.with_name(f"{args.out.stem}.partial{args.out.suffix}")
    if partial_out.exists():
        parser.error(f"partial output already exists; inspect or rename it first: {partial_out}")

    client = OandaClient(args.environment, token)
    account_id = client.account_id(os.getenv("OANDA_ACCOUNT_ID"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    last_time: str | None = None
    written = 0
    cursor = args.start
    with partial_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        while cursor < args.end:
            chunk_end = min(cursor + timedelta(days=PAGE_DAYS), args.end)
            candles = client.candles(account_id, args.instrument, cursor, chunk_end)
            for candle in candles:
                if not candle.get("complete", False):
                    continue
                timestamp = str(candle["time"])
                if parse_utc(timestamp) >= args.end:
                    continue
                if last_time is not None and timestamp <= last_time:
                    continue
                writer.writerow(flatten(candle))
                last_time = timestamp
                written += 1
            cursor = chunk_end
            handle.flush()
            print(f"Fetched through {iso_z(cursor)}; complete candles written: {written}")
            time.sleep(0.25)

    partial_out.replace(args.out)
    metadata = {
        "provider": "OANDA v20 REST",
        "environment": args.environment,
        "instrument": args.instrument,
        "granularity": "M1",
        "price_components": ["mid", "bid", "ask"],
        "volume_definition": "number of prices created during each candle",
        "requested_start_utc": iso_z(args.start),
        "requested_end_utc_exclusive": iso_z(args.end),
        "complete_candles_written": written,
        "file": args.out.name,
        "credential_stored": False,
    }
    args.out.with_suffix(args.out.suffix + ".meta.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Finished. Wrote {written} complete candles to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
