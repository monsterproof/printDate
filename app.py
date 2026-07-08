#!/usr/bin/env python3
"""Etiketten-Druck-Station – Flask-App für den Raspberry Pi (QL-800)."""

import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

import printer

load_dotenv()

app = Flask(__name__)

NAMES = [n.strip() for n in os.environ.get("NAMES", "").split(",") if n.strip()]
PORT = int(os.environ.get("PORT", "5000"))


@app.route("/")
def index():
    return render_template(
        "index.html",
        names=NAMES,
        today=printer.format_date_de(),
    )


@app.route("/print", methods=["POST"])
def do_print():
    data = request.get_json(silent=True) or {}
    kind = data.get("type")
    name = data.get("name")

    if kind not in ("date", "name"):
        return jsonify(ok=False, message="Unbekannter Druckauftrag"), 400
    if kind == "name" and name not in NAMES:
        return jsonify(ok=False, message="Unbekannter Name"), 400

    try:
        label = printer.print_label(kind, name)
        return jsonify(ok=True, message=f"Gedruckt: {label}")
    except printer.PrinterOffError as exc:  # Drucker aus/Standby → klarer Hinweis
        return jsonify(ok=False, message=str(exc)), 503
    except Exception as exc:  # sonstige Fehler sauber als JSON an die UI
        app.logger.exception("Druckfehler")
        return jsonify(ok=False, message=f"Druckfehler: {exc}"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
