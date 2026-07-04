# Etiketten-Druck-Station (Brother QL-800)

Einfache Flask-Kiosk-App für einen Raspberry Pi mit Touch-Bildschirm und
angeschlossenem **Brother P-Touch QL-800**. Per Knopfdruck wird ein Etikett gedruckt:

- **📅 Datum heute** → druckt nur das aktuelle Datum (z. B. „4. Juli 2026").
- **Namens-Knöpfe** (aus `.env`) → druckt Datum **und** Name.

Etikette: **DK-22210** (29 mm Endlosband, schwarz/weiss).

## Installation auf dem Pi

```bash
git clone <REPO-URL> ~/printDate
cd ~/printDate
bash setup.sh
nano .env          # NAMES eintragen
sudo reboot
```

`setup.sh` legt ein venv an, installiert die Abhängigkeiten, fügt den User zur
Gruppe `lp` hinzu (Schreibrecht auf `/dev/usb/lp0`), entfernt die alte
Podcast-Kiosk-App und richtet `printdate.service` + Chromium-Kiosk-Autostart ein.

## Konfiguration (`.env`)

| Variable | Bedeutung |
|----------|-----------|
| `NAMES` | Kommaseparierte Namen für die Knöpfe |
| `LABEL_SIZE` | brother_ql Label-Grösse (`29` für DK-22210) |
| `PRINTER_MODEL` | `QL-800` |
| `PRINTER_BACKEND` / `PRINTER_DEVICE` | `linux_kernel` / `file:///dev/usb/lp0` |
| `TAPE_WIDTH_PX` | Druckbare Breite quer zum Band (306 px bei 29 mm) |
| `PORT` | Flask-Port (Standard 5000) |

## Testen ohne UI

```bash
.venv/bin/python printer.py date          # nur Datum
.venv/bin/python printer.py name Anna      # Datum + Name
```

## Hinweise

- Die **Editor-Lite-LED** am QL-800 muss **aus** sein, sonst arbeitet der Drucker
  im USB-Massenspeicher-Modus und nimmt keinen Rasterdruck an.
- Nach dem Hinzufügen zur Gruppe `lp` ist ein **Reboot** nötig.
- Logs: `journalctl -u printdate -f`
