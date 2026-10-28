"""Rasterize the generated line-chart SVG for local visual inspection, using only stdlib."""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "charts_p1" / "audit_contact_sheet.svg"
TARGET = HERE / "charts_p1" / "audit_contact_sheet.png"


def color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def main() -> None:
    root = ET.parse(SOURCE).getroot()  # noqa: S314 - parses only this script's generated local SVG
    width = int(root.attrib["width"])
    height = int(root.attrib["height"])
    pixels = bytearray([255]) * (width * height * 3)

    def dot(x: int, y: int, rgb: tuple[int, int, int], radius: int = 0) -> None:
        for y_now in range(max(0, y - radius), min(height, y + radius + 1)):
            for x_now in range(max(0, x - radius), min(width, x + radius + 1)):
                offset = (y_now * width + x_now) * 3
                pixels[offset : offset + 3] = bytes(rgb)

    def draw_line(element: ET.Element) -> None:
        x1, y1 = float(element.attrib["x1"]), float(element.attrib["y1"])
        x2, y2 = float(element.attrib["x2"]), float(element.attrib["y2"])
        steps = max(1, int(max(abs(x2 - x1), abs(y2 - y1))))
        rgb = color(element.attrib.get("stroke", "#000000"))
        radius = 1 if float(element.attrib.get("stroke-width", "1")) >= 1.3 else 0
        for step in range(steps + 1):
            fraction = step / steps
            dot(round(x1 + fraction * (x2 - x1)), round(y1 + fraction * (y2 - y1)), rgb, radius)

    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "rect":
            x = round(float(element.attrib["x"]))
            y = round(float(element.attrib["y"]))
            rect_width = round(float(element.attrib["width"]))
            rect_height = round(float(element.attrib["height"]))
            fill = color(element.attrib.get("fill", "#ffffff"))
            for y_now in range(max(0, y), min(height, y + rect_height)):
                start = (y_now * width + max(0, x)) * 3
                end = (y_now * width + min(width, x + rect_width)) * 3
                pixels[start:end] = bytes(fill) * ((end - start) // 3)
        elif tag == "line":
            draw_line(element)
        elif tag == "circle":
            dot(
                round(float(element.attrib["cx"])),
                round(float(element.attrib["cy"])),
                color(element.attrib.get("fill", "#000000")),
                max(1, round(float(element.attrib.get("r", "1")))),
            )
    raw = b"".join(b"\x00" + pixels[row * width * 3 : (row + 1) * width * 3] for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, level=9))
    png += chunk(b"IEND", b"")
    TARGET.write_bytes(png)
    print(f"wrote {TARGET} ({width}x{height})")  # noqa: T201


if __name__ == "__main__":
    main()
