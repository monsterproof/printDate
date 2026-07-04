#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Etiketten-Druck-Station – Setup auf dem Raspberry Pi
#  Ausführen mit:  cd ~/printDate && bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "== [1/6] Python-venv & Abhängigkeiten =="
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt -q

echo "== [2/6] .env vorbereiten =="
if [ ! -f .env ]; then
  cp .env.example .env
  echo "   -> .env aus .env.example erstellt. Bitte NAMES darin anpassen!"
else
  echo "   -> .env existiert bereits, unverändert gelassen."
fi

echo "== [3/6] Schreibrecht auf den Drucker (Gruppe lp) =="
if id -nG "$USER" | grep -qw lp; then
  echo "   -> $USER ist bereits in Gruppe lp."
else
  sudo usermod -aG lp "$USER"
  echo "   -> $USER zur Gruppe lp hinzugefügt (Reboot nötig, s. u.)."
fi

echo "== [4/6] Alte Podcast-Kiosk-App entfernen =="
sudo systemctl disable --now podcast.service 2>/dev/null || true
rm -f "$HOME/.config/autostart/podcast-kiosk.desktop"
echo "   -> podcast.service deaktiviert, alter Autostart entfernt."

echo "== [5/6] systemd-Dienst installieren =="
# ExecStart/WorkingDirectory zur Laufzeit auf das echte Verzeichnis setzen.
sed "s#/home/jonas/printDate#${DIR}#g" printdate.service | sudo tee /etc/systemd/system/printdate.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now printdate.service
echo "   -> printdate.service aktiviert."

echo "== [6/6] Kiosk-Autostart installieren =="
mkdir -p "$HOME/.config/autostart"
cp printdate-kiosk.desktop "$HOME/.config/autostart/printdate-kiosk.desktop"
echo "   -> Chromium-Kiosk-Autostart installiert."

echo ""
echo "──────────────────────────────────────────────────────────────"
echo " Fertig. Bitte jetzt:"
echo "   1) Namen in  ${DIR}/.env  eintragen (NAMES=...)"
echo "   2) Editor-Lite-LED am QL-800 muss AUS sein"
echo "   3) sudo reboot   (damit lp-Gruppe & Kiosk aktiv werden)"
echo "──────────────────────────────────────────────────────────────"
