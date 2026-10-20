"""A minimal .xlsx sheet reader (stdlib zip + xml; the venv has no openpyxl). Returns the rows of one sheet as lists of
cell values (shared strings resolved, numbers as float, empty cells as None), in sheet order."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def rows(path: str, sheet_file: str) -> list[list]:
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    out = []
    for r in ET.fromstring(z.read(sheet_file)).iter("{%s}row" % NS["m"]):
        vals: dict[int, object] = {}
        for c in r.findall("m:c", NS):
            t, v = c.get("t"), c.find("m:v", NS)
            if t == "inlineStr":
                x = "".join(e.text or "" for e in c.iter("{%s}t" % NS["m"]))
            elif v is None:
                x = None
            elif t == "s":
                x = shared[int(v.text)]
            elif t in ("str", "b", "e"):
                x = v.text
            else:
                try:
                    x = float(v.text)
                except ValueError:
                    x = v.text
            vals[_col(c.get("r"))] = x
        if vals:
            out.append([vals.get(i) for i in range(max(vals) + 1)])
    return out
