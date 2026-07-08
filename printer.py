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

# Keine Drehung: die Zeilen laufen quer über die 29-mm-Bandbreite.
# Auf "180" ändern, falls das Etikett kopfsteht.
ROTATE = os.environ.get("ROTATE", "0")

# Druckbare Breite quer zum Band (29-mm-Endlos = 306 px bei 300 dpi).
# Bildbreite = Bandbreite (fix); die Länge (Vorschub) wächst nur mit der Zeilenzahl.
TAPE_WIDTH_PX = int(os.environ.get("TAPE_WIDTH_PX", "306"))
MARGIN_PX = int(os.environ.get("MARGIN_PX", "16"))

# Mindest-Etikettenlänge in px (der QL-800 verlangt >= 150 Rasterzeilen).
MIN_LABEL_LEN = int(os.environ.get("MIN_LABEL_LEN", "160"))

# Grösster erlaubter Schriftgrad; die tatsächliche Grösse wird zusätzlich so
# verkleinert, dass jede Zeile in die 29-mm-Breite passt.
MAX_FONT = int(os.environ.get("MAX_FONT", "80"))

# Kandidaten für eine systemweit vorhandene, fette TrueType-Schrift.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


class PrinterOffError(RuntimeError):
    """Drucker nicht erreichbar (aus/Standby → USB-Gerät /dev/usb/lp0 fehlt)."""


def _device_path():
    """Gerätepfad aus PRINTER_DEVICE (file:///dev/usb/lp0 -> /dev/usb/lp0)."""
    if PRINTER_DEVICE.startswith("file://"):
        return PRINTER_DEVICE[len("file://"):]
    return None


def clock_synced():
    """True, wenn systemd-timesyncd die Systemuhr synchronisiert hat.

    Der Pi hat keine Hardware-Uhr (RTC); ohne Sync (z. B. Boot ohne Netz) kann
    das Datum falsch sein. Der Marker existiert erst nach erfolgreichem NTP-Sync.
    """
    return os.path.exists("/run/systemd/timesync/synchronized")


def format_date_de(d=None):
    """Formatiert ein Datum numerisch als '04.07.2026' (feste, vorhersehbare Länge)."""
    d = d or datetime.date.today()
    return d.strftime("%d.%m.%Y")


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _font_for_width(texts, max_width):
    """Grösste Schrift (bis MAX_FONT), bei der alle Zeilen in max_width passen."""
    size = MAX_FONT
    while size > 8:
        font = _load_font(size)
        if all((font.getbbox(t)[2] - font.getbbox(t)[0]) <= max_width for t in texts):
            return font
        size -= 2
    return _load_font(8)


def render_label(date_str, name=None):
    """Rendert das Etikett quer: die Zeilen laufen über die 29-mm-Bandbreite.

    Bildbreite = Bandbreite (306 px, fix); die Länge wächst nur mit der
    Zeilenzahl → kurze Etiketten. Ohne Name eine Zeile (Datum), mit Name zwei
    Zeilen (Datum oben, Name unten), beide auf die Breite gefittet.
    """
    texts = [date_str] if not name else [date_str, name]
    max_w = TAPE_WIDTH_PX - 2 * MARGIN_PX
    font = _font_for_width(texts, max_w)

    dims = [font.getbbox(t) for t in texts]
    heights = [b[3] - b[1] for b in dims]
    gap = int(max(heights) * 0.35) if len(texts) > 1 else 0

    content_h = sum(heights) + gap * (len(texts) - 1)
    img_h = max(content_h + 2 * MARGIN_PX, MIN_LABEL_LEN)

    # Breite = Bandbreite (fix); Höhe = Vorschublänge (klein).
    img = Image.new("RGB", (TAPE_WIDTH_PX, img_h), "white")
    draw = ImageDraw.Draw(img)

    y = (img_h - content_h) // 2
    for text, b, h in zip(texts, dims, heights):
        x = (TAPE_WIDTH_PX - (b[2] - b[0])) // 2 - b[0]
        draw.text((x, y - b[1]), text, fill="black", font=font)
        y += h + gap

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
    # Der QL-800 geht nach einer Weile in Standby/aus und verschwindet dann als
    # USB-Gerät (/dev/usb/lp0). Über USB lässt er sich nicht aufwecken – deshalb
    # eine klare Meldung statt eines kryptischen Fehlers.
    dev = _device_path()
    if dev and not os.path.exists(dev):
        raise PrinterOffError(
            "Drucker nicht gefunden – bitte Drucker einschalten und erneut drücken."
        )
    try:
        send(
            instructions=instructions,
            printer_identifier=PRINTER_DEVICE,
            backend_identifier=PRINTER_BACKEND,
            blocking=True,
        )
    except Exception as exc:
        raise PrinterOffError(
            f"Drucker antwortet nicht – bitte einschalten und erneut drücken. ({exc})"
        )
    return label_text


if __name__ == "__main__":
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else "date"
    who = sys.argv[2] if len(sys.argv) > 2 else None
    print("Gedruckt:", print_label(what, who))
