"""Build a concise Thai week-by-week learning report from the historical replay."""

# ruff: noqa: E501, T201

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "historical_diagnostic"
SOURCE = DATA / "atr_regime_trade_learning.csv"


def r_total(frame: pd.DataFrame, column: str) -> float:
    return float(frame[column].sum())


def result_text(row: pd.Series, column: str) -> str:
    count = int(row[f"{column}_n"])
    total = float(row[f"{column}_r"])
    return f"{total:+.2f}R จาก {count} ไม้" if count else "ไม่มีไม้ปิด"


def main() -> None:
    trades = pd.read_csv(SOURCE, parse_dates=["source_stop_time_utc"])
    trades["source_stop_time_utc"] = pd.to_datetime(trades["source_stop_time_utc"], utc=True)
    trades["week_start"] = trades["source_stop_time_utc"].dt.normalize() - pd.to_timedelta(
        trades["source_stop_time_utc"].dt.weekday, unit="D"
    )
    weekly_groups = trades.groupby("week_start", sort=True)
    cumulative = {"candidate_r": 0.0, "fixed_atr_selected_r": 0.0, "selected_r": 0.0}
    completed_all = trades[trades["candidate_r"].notna()]
    best_total = completed_all.nlargest(1, "candidate_r").iloc[0]
    worst_total = completed_all.nsmallest(1, "candidate_r").iloc[0]
    lines = [
        "# รายงานเรียนรู้กลยุทธ์รายสัปดาห์ — historical replay",
        "",
        f"ช่วงข้อมูล: {trades['week_start'].min():%Y-%m-%d} ถึง {trades['week_start'].max():%Y-%m-%d} UTC · {len(weekly_groups)} สัปดาห์ · {len(trades)} เหตุการณ์ · ปิดเป็นไม้สมบูรณ์ {len(completed_all)} ไม้",
        "",
        "## สรุปผลตลอดชุดข้อมูล",
        "",
        f"- กฎ V1 เดิม: {r_total(completed_all, 'candidate_r'):+.2f}R จาก {len(completed_all)} ไม้ (เฉลี่ย +{completed_all['candidate_r'].mean():.3f}R/ไม้)",
        f"- screen ตาม ATR ณ source stop (ไม่ใช่ gate ณ เวลา re-entry): {r_total(completed_all, 'fixed_atr_selected_r'):+.2f}R จาก {int(completed_all['fixed_atr_selected_r'].count())} ไม้; บล็อก 15 ไม้ซึ่งผลรวมเดิม -2.72R",
        f"- ตัวเรียนรู้ค่าเฉลี่ยย้อนหลัง 52 สัปดาห์: {r_total(completed_all, 'selected_r'):+.2f}R จาก {int(completed_all['selected_r'].count())} ไม้; บล็อก 44 ไม้ที่ภายหลังรวมกันได้ +3.23R จึงยังไม่ควรใช้",
        f"- ไม้บวกสูงสุด: {best_total['trade_key']} {best_total['candidate_r']:+.2f}R · ไม้ลบมากสุด: {worst_total['trade_key']} {worst_total['candidate_r']:+.2f}R",
        "- USD/ยอดบัญชี: ไม่คำนวณใน replay นี้ เพราะไม่มีการกำหนด lot/risk ต่อไม้และมีเหตุการณ์ซ้อนกัน; ค่า R เป็นผล event-level ไม่ใช่ equity curve",
        "- ต้นทุน: รวม spread ตามข้อมูล; ไม่รวม slippage; ช่วง exam ที่ล็อกไว้ถูกตัดออก",
        "",
        "ทุกสัปดาห์ด้านล่างเรียงตามเวลา การตัดสินใจ trailing ATR ใช้เฉพาะผลของไม้ที่ปิดก่อนเหตุการณ์นั้น; ผลสมมติของไม้ที่ถูกบล็อกไม่ถูกนำไปเรียนรู้. ATR screen ในตารางนี้วัด ณ source stop จึงไม่ใช่การทดสอบล็อก ณ เวลาเข้า re-entry; ผลที่ถูกต้องของ entry-time lock อยู่ใน historical_holdout_2021_2023/.",
        "",
        "## รายงานทีละสัปดาห์",
    ]
    for number, (week_start, frame) in enumerate(weekly_groups, start=1):
        week_end = week_start + pd.Timedelta(days=6)
        completed = frame[frame["candidate_r"].notna()]
        high = completed[completed["atr_regime"].eq("HIGH")]
        normal = completed[completed["atr_regime"].ne("HIGH")]
        cumulative["candidate_r"] += r_total(frame, "candidate_r")
        cumulative["fixed_atr_selected_r"] += r_total(frame, "fixed_atr_selected_r")
        cumulative["selected_r"] += r_total(frame, "selected_r")
        fixed_blocked = frame[frame["fixed_atr_blocked_r"].notna()]
        trailing_blocked = frame[frame["blocked_counterfactual_r"].notna()]
        warmup = int(frame["action"].eq("ALLOW_WARMUP").sum())
        trailing_allow = int(frame["action"].eq("ALLOW_POSITIVE_TRAILING").sum())
        trailing_block = int(frame["action"].eq("BLOCK_NONPOSITIVE_TRAILING").sum())
        if len(completed):
            best = completed.loc[completed["candidate_r"].idxmax()]
            worst = completed.loc[completed["candidate_r"].idxmin()]
            standout = (
                f"ไม้เด่น: {best['trade_key']} {best['side']} {best['window']} {best['candidate_r']:+.2f}R"
                if best["candidate_r"] > 0
                else f"ไม่มีไม้บวก; ไม้ดีที่สุด {best['trade_key']} {best['candidate_r']:+.2f}R"
            )
            if worst["trade_key"] != best["trade_key"]:
                standout += f" · ไม้เสียสุด {worst['trade_key']} {worst['candidate_r']:+.2f}R"
        else:
            standout = "สัปดาห์นี้ไม่มีไม้ปิด; ดูเหตุผลที่ไม่มี entry ใน journal รายเหตุการณ์"
        if len(high) + len(normal):
            market_note = (
                f"สภาวะ ATR ของไม้ที่ปิด: HIGH {len(high)} ไม้ {r_total(high, 'candidate_r'):+.2f}R; "
                f"NORMAL/LOW {len(normal)} ไม้ {r_total(normal, 'candidate_r'):+.2f}R"
            )
        else:
            market_note = f"เหตุการณ์ ATR สูง {int(frame['atr_regime'].eq('HIGH').sum())}/{len(frame)}; ยังไม่มีไม้ปิดใช้ประเมินผลสภาวะ"
        fixed_effect = (
            f"ล็อก ATR สูงบล็อก {len(fixed_blocked)} ไม้ ผลย้อนหลัง {r_total(frame, 'fixed_atr_blocked_r'):+.2f}R"
            if len(fixed_blocked)
            else "ล็อก ATR สูงไม่บล็อกไม้ที่ปิดในสัปดาห์นี้"
        )
        trailing_effect = (
            f"ตัวเรียนรู้บล็อก {len(trailing_blocked)} ไม้ ผลย้อนหลัง {r_total(frame, 'blocked_counterfactual_r'):+.2f}R"
            if len(trailing_blocked)
            else "ตัวเรียนรู้ไม่บล็อกไม้ที่ปิดในสัปดาห์นี้"
        )
        lines += [
            "",
            f"### สัปดาห์ {number} ({week_start:%Y-%m-%d}–{week_end:%Y-%m-%d} UTC)",
            "",
            f"- ผล V1 ตามกฎเดิม: {result_text(pd.Series({'candidate_r_n': completed['candidate_r'].count(), 'candidate_r_r': r_total(frame, 'candidate_r')}), 'candidate_r')}",
            f"- ผล benchmark ล็อก ATR สูง: {result_text(pd.Series({'fixed_atr_selected_r_n': frame['fixed_atr_selected_r'].count(), 'fixed_atr_selected_r_r': r_total(frame, 'fixed_atr_selected_r')}), 'fixed_atr_selected_r')} · สะสม {cumulative['fixed_atr_selected_r']:+.2f}R",
            f"- ผลตัวเรียนรู้ trailing 52 สัปดาห์: {result_text(pd.Series({'selected_r_n': frame['selected_r'].count(), 'selected_r_r': r_total(frame, 'selected_r')}), 'selected_r')} · สะสม {cumulative['selected_r']:+.2f}R",
            f"- V1 สะสม: {cumulative['candidate_r']:+.2f}R · USD/บัญชี: ไม่ได้จำลอง",
            f"- ตลาด/ไม้สำคัญ: {market_note}; {standout}",
            f"- สิ่งที่ได้เรียนรู้หลังสัปดาห์นี้: {fixed_effect}; {trailing_effect}",
            f"- กฎสำหรับสัปดาห์ถัดไป: ไม่แก้ V1 จากผลสัปดาห์เดียว; คง ATR lock เป็นสมมติฐานวิจัยแยกไว้ และให้ trailing replay ใช้เฉพาะไม้ที่ปิดแล้ว ({warmup} warm-up, {trailing_allow} อนุญาตจากค่าเฉลี่ยบวก, {trailing_block} บล็อก) ไม่ป้อนผล counterfactual กลับเข้าโมเดล",
        ]
    lines += [
        "",
        "## ข้อสรุปและขั้นถัดไป",
        "",
        "ตัวล็อก ATR สูงแบบคงที่ให้ผลย้อนหลังดีกว่า V1 (+30.96R vs +28.25R) แต่มีไม้ ATR สูงเพียง 15 ไม้ และเกณฑ์ percentile 80 เคยถูกสำรวจจากข้อมูลชุดพัฒนาเดียวกัน จึงยังสรุปว่าทำกำไรในอนาคตไม่ได้และยังไม่เพิ่มเข้ากลยุทธ์ ขั้นถัดไปคือแช่แข็งกฎนี้และทดสอบกับข้อมูลที่ไม่เคยใช้เลือกเกณฑ์ โดยไม่จูนซ้ำบนชุดนี้; หากยังไม่มีข้อมูลอิสระ ให้รายงานว่าเป็นสมมติฐาน ไม่สร้างความแน่นอนจาก backtest เดิม",
        "",
        "รายละเอียดทุกเหตุการณ์, ATR M15/M30/H1, จำนวน/ค่าเฉลี่ยผลลัพธ์ก่อนหน้า, action และผล counterfactual อยู่ใน `atr_regime_trade_learning.csv` และ `ATR_WEEKLY_SEQUENTIAL_REPLAY.md`",
        "",
    ]
    output = DATA / "WEEKLY_LEARNING_REPORT_TH.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output} ({len(weekly_groups)} weeks)")


if __name__ == "__main__":
    main()
