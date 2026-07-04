#!/usr/bin/env python3
"""Etiketten-Rendering und Versand an den Brother QL-800.

Rendert Datum (und optional Name) mit PIL zu einem Bild und schickt es via
brother_ql über das linux_kernel-Backend direkt an /dev/usb/lp0.
"""

import os
import datetime

from PIL import Image, ImageDraw, ImageFont
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send

# ── Konfiguration (aus .env, mit Defaults) ────────────────────────────────────
LABEL_SIZE = os.environ.get("LABEL_SIZE", "29")
PRINTER_MODEL = os.environ.get("PRINTER_MODEL", "QL-800")
PRINTER_BACKEND = os.environ.get("PRINTER_BACKEND", "linux_kernel")
PRINTER_DEVICE = os.environ.get("PRINTER_DEVICE", "file:///dev/usb/lp0")

# Drehung des (waagrecht gerenderten) Bildes für den Bandvorschub.
# "90" ist Standard; auf "270" ändern, falls die Schrift kopfsteht.
ROTATE = os.environ.get("ROTATE", "90")

# Druckbare Breite quer zum Band für 29-mm-Endlos = 306 px (bei 300 dpi).
# Das Bild ist so hoch wie die Bandbreite; die Länge wächst mit dem Text.
TAPE_WIDTH_PX = int(os.environ.get("TAPE_WIDTH_PX", "306"))
MARGIN_PX = 18

# Ziel-Texthöhe (px) je Zeile – zum Justieren der Grösse ohne Code-Änderung.
# Nur-Datum füllt eine Zeile; mit Name zwei kleinere Zeilen (Datum + Name).
SINGLE_LINE_H = int(os.environ.get("SINGLE_LINE_H", "150"))
DOUBLE_LINE_H = int(os.environ.get("DOUBLE_LINE_H", "120"))

# Kandidaten für eine systemweit vorhandene, fette TrueType-Schrift.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def format_date_de(d=None):
    """Formatiert ein Datum numerisch als '04.07.2026' (feste, vorhersehbare Länge)."""
    d = d or datetime.date.today()
    return d.strftime("%d.%m.%Y")


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _font_for_height(text, target_h):
    """Grösste Schriftgrösse, deren Texthöhe target_h nicht überschreitet."""
    size = int(target_h * 1.5)
    while size > 12:
        font = _load_font(size)
        bbox = font.getbbox(text)
        if (bbox[3] - bbox[1]) <= target_h:
            return font
        size -= 4
    return _load_font(12)


def render_label(date_str, name=None):
    """Rendert das Etikett waagrecht (wird beim Druck um 90° gedreht).

    Höhe = Bandbreite (306 px = 29 mm); die Länge wächst mit dem Text.
    Ohne Name: nur das Datum, eine Zeile. Mit Name: Datum + Name je auf einer
    eigenen Zeile, quer über die Bandbreite gestapelt.
    """
    usable_h = TAPE_WIDTH_PX - 2 * MARGIN_PX

    if name:
        gap = 18
        line_h = min((usable_h - gap) // 2, DOUBLE_LINE_H)
        lines = [(date_str, _font_for_height(date_str, line_h)),
                 (name, _font_for_height(name, line_h))]
    else:
        gap = 0
        line_h = min(usable_h, SINGLE_LINE_H)
        lines = [(date_str, _font_for_height(date_str, line_h))]

    heights, widths = [], []
    for text, font in lines:
        bbox = font.getbbox(text)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])

    content_w = max(widths)
    img_w = content_w + 2 * MARGIN_PX
    # Bildhöhe = Bandbreite (fix), Inhalt vertikal zentriert.
    img = Image.new("RGB", (img_w, TAPE_WIDTH_PX), "white")
    draw = ImageDraw.Draw(img)

    total_h = sum(heights) + gap * (len(lines) - 1)
    y = (TAPE_WIDTH_PX - total_h) // 2
    for i, (text, font) in enumerate(lines):
        bbox = font.getbbox(text)
        x = (img_w - (bbox[2] - bbox[0])) // 2 - bbox[0]
        draw.text((x, y - bbox[1]), text, fill="black", font=font)
        y += heights[i] + gap

    return img


def print_label(kind, name=None):
    """Rendert und druckt ein Etikett. kind: 'date' oder 'name'.

    Gibt eine kurze Statusmeldung zurück. Wirft bei Druckerfehlern.
    """
    date_str = format_date_de()
    if kind == "name":
        if not name:
            raise ValueError("Name fehlt")
        img = render_label(date_str, name=name)
        label_text = f"{name} / {date_str}"
    else:
        img = render_label(date_str)
        label_text = date_str

    qlr = BrotherQLRaster(PRINTER_MODEL)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=[img],
        label=LABEL_SIZE,
        rotate=ROTATE,
        threshold=70,
        dither=False,
        cut=True,
        hq=True,
    )
    send(
        instructions=instructions,
        printer_identifier=PRINTER_DEVICE,
        backend_identifier=PRINTER_BACKEND,
        blocking=True,
    )
    return label_text


if __name__ == "__main__":
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else "date"
    who = sys.argv[2] if len(sys.argv) > 2 else None
    print("Gedruckt:", print_label(what, who))
