"""Hand-worked tests of row 52: the publication lag, the readings, and the stdlib xlsx reader."""

import zipfile

import numpy as np
import pandas as pd
import pytest

import etf52
import xlsx_min


def test_public_from_next_weekday_1600_new_york():
    # Wed 2025-11-05 -> Thu 2025-11-06 16:00 EST = 21:00 UTC
    assert etf52.public_from(pd.Timestamp("2025-11-05")) == pd.Timestamp("2025-11-06 21:00", tz="UTC")
    # Fri 2025-06-06 -> Mon 2025-06-09 16:00 EDT = 20:00 UTC
    assert etf52.public_from(pd.Timestamp("2025-06-06")) == pd.Timestamp("2025-06-09 20:00", tz="UTC")


def test_features():
    t = np.r_[np.full(20, 100.0), 110.0, 105.0]  # days 0..21
    F = etf52.features(t)
    # day 20: 110 / day 0 (100) - 1 = 0.10; day 21: 105 / day 1 (100) - 1 = 0.05
    assert F.ch20.iloc[20] == pytest.approx(0.10) and F.ch20.iloc[21] == pytest.approx(0.05)
    # up20 at day 21: diffs of days 2..21: one rise (day 20) -> 1; day 20 window days 1..20 -> 1
    assert F.up20.iloc[21] == 1 and F.up20.iloc[20] == 1
    assert np.isnan(F.up20.iloc[19])  # day 0's diff is missing -> the window 0..19 is incomplete
    assert np.isnan(F.ch60.iloc[21])


def test_vs52():
    t = np.r_[np.full(199, 50.0), 100.0, 80.0]
    F = etf52.features(t)
    # day 199: 200 values, max 100 -> 0; day 200: 80 / 100 - 1 = -0.2
    assert F.vs52.iloc[199] == pytest.approx(0.0) and F.vs52.iloc[200] == pytest.approx(-0.2)
    assert np.isnan(F.vs52.iloc[198])  # fewer than 200 days


def test_xlsx_min(tmp_path):
    p = tmp_path / "t.xlsx"
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>Date</t></si><si><t>05-Nov-2025</t></si></sst>')
        z.writestr("xl/worksheets/sheet2.xml",
                   f'<worksheet {ns}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>1.5</v></c></row>'
                   f'<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>1053.91</v></c></row></sheetData></worksheet>')
    R = xlsx_min.rows(str(p), "xl/worksheets/sheet2.xml")
    assert R == [["Date", None, 1.5], ["05-Nov-2025", 1053.91]]


def test_ch20_is_exactly_20_days_back():
    F = etf52.features(np.arange(1.0, 23.0))  # day i holds i + 1
    # day 20: 21 / 1 - 1 = 20 (19 days back would give 21 / 2 - 1 = 9.5)
    assert F.ch20.iloc[20] == pytest.approx(20.0)
