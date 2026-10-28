"""Render the fixed-ATR holdout results in the user's weekly review format."""

# ruff: noqa: E501, T201

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "historical_holdout_2021_2023"
SOURCE = DATA / "holdout_trade_journal.csv"


def main() -> None:
    trades = pd.read_csv(SOURCE, parse_dates=["source_stop_time_utc", "entry_time_utc"])
    trades["source_stop_time_utc"] = pd.to_datetime(trades["source_stop_time_utc"], utc=True)
    trades["entry_time_utc"] = pd.to_datetime(trades["entry_time_utc"], utc=True, errors="coerce")
    trades["report_time"] = trades["entry_time_utc"].fillna(trades["source_stop_time_utc"])
    trades["week_start"] = trades["report_time"].dt.normalize() - pd.to_timedelta(
        trades["report_time"].dt.weekday, unit="D"
    )
    groups = trades.groupby("week_start", sort=True)
    lines = [
        "# รายงาน Holdout ล็อก ATR — สรุปทีละสัปดาห์",
        "",
        "ช่วงข้อมูล: XAUUSD M1 2021-09-01 ถึง 2023-10-02 UTC; ใช้ source signal จาก frozen TR1 และ candidate RETEST-CONTINUATION V1. ช่วง exam 2026 ไม่ได้เปิด.",
        "",
        "กฎที่ freeze: วัด median percentile ของ ATR(14) จากแท่ง M15/M30/H1 ที่ปิดแล้ว ณ เวลาเข้า re-entry จริง แต่ละ percentile เทียบกับ ATR ย้อนหลัง 120 ชั่วโมงโดยไม่นับแท่งปัจจุบัน; บล็อกเฉพาะเมื่อ composite >80th percentile และอนุญาตเมื่อ <=80. ไม่ปรับ threshold จาก holdout.",
        "",
        "ผลทั้งหมดเป็น R ต่อ event ไม่ใช่ equity บัญชี; ไม่กำหนด lot/risk USD และเส้นทาง event อาจซ้อนกัน. รวม spread จาก M1, ไม่รวม slippage.",
        "",
        "## สรุป Holdout",
        "",
        "ดูตัวเลขและเกณฑ์ตัดสินใน `HOLDOUT_RESULTS.md`. ข้อสรุป: กฎ ATR ยังไม่ผ่านเกณฑ์วิจัยและไม่เพิ่มเข้ากลยุทธ์.",
        "",
        "## รายสัปดาห์",
    ]
    cumulative_base = 0.0
    cumulative_gate = 0.0
    for number, (week, frame) in enumerate(groups, start=1):
        done = frame[frame["candidate_r"].notna()]
        gate = done[done["gate_r"].notna()]
        blocked = done[done["blocked_r"].notna()]
        base_r = float(done["candidate_r"].sum())
        gate_r = float(gate["gate_r"].sum())
        blocked_r = float(blocked["blocked_r"].sum())
        cumulative_base += base_r
        cumulative_gate += gate_r
        if len(done):
            best = done.loc[done["candidate_r"].idxmax()]
            worst = done.loc[done["candidate_r"].idxmin()]
            standout = f"ดีที่สุด {best['trade_key']} {best['candidate_r']:+.2f}R; เสียสุด {worst['trade_key']} {worst['candidate_r']:+.2f}R"
        else:
            standout = "ไม่มี candidate ที่ปิดผลได้"
        statuses = frame["status"].value_counts().to_dict()
        reasons = ", ".join(f"{key} {value}" for key, value in sorted(statuses.items()))
        high = done[done["atr_gate_status"].eq("BLOCK_HIGH_ATR")]
        if len(blocked):
            lesson = f"กฎบล็อก {len(blocked)} ไม้ ซึ่งผลจริงย้อนหลัง {blocked_r:+.2f}R " + (
                "(กันขาดทุนสุทธิ)" if blocked_r < 0 else "(พลาดกำไรสุทธิ)"
            )
        else:
            lesson = "ไม่มีไม้ปิดที่ถูกกฎ ATR สูงบล็อก"
        lines += [
            "",
            f"### สัปดาห์ {number} ({week:%Y-%m-%d} UTC)",
            "",
            f"- V1 ตามกฎเดิม: {base_r:+.2f}R จาก {len(done)} ไม้ · สะสม {cumulative_base:+.2f}R",
            f"- ล็อก ATR ณ เวลาเข้า: {gate_r:+.2f}R จาก {len(gate)} ไม้ · สะสม {cumulative_gate:+.2f}R",
            f"- ไม้ที่บล็อกเพราะ ATR >80th percentile: {len(blocked)} ไม้ · ผล counterfactual {blocked_r:+.2f}R",
            f"- สภาวะ/ผลสำคัญ: ATR สูงในไม้ที่ปิด {len(high)} ไม้; {standout}; สถานะ source: {reasons}",
            f"- บทเรียนและกฎสัปดาห์ถัดไป: {lesson}; คง threshold ที่ freeze ไว้ ไม่แก้กฎจากผลสัปดาห์เดียว",
        ]
    lines += [
        "",
        "## ข้อสรุป",
        "",
        "กฎนี้ถูกตรวจบนช่วงก่อน development cohort แต่ช่วง 2021–2023 เคยใช้ในงานวิจัยทองคำอื่นใน workspace จึงไม่เรียกว่า virgin market data. สำหรับ setup นี้ ผล holdout ยังไม่ผ่านจำนวนไม้และความสม่ำเสมอที่กำหนด; ห้ามไล่เปลี่ยน threshold แล้วทดสอบซ้ำบนช่วงเดิม. ต้องออกแบบกฎรุ่นใหม่จาก development data แล้วหา holdout ใหม่ที่ยังไม่เคยเปิด หรือรอข้อมูลใหม่ตามแผน.",
        "",
    ]
    out = DATA / "HOLDOUT_WEEKLY_REPORT_TH.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({len(groups)} weeks, {len(trades)} events)")


if __name__ == "__main__":
    main()
