"""Prepara el payload exacto para la herramienta create_post de Buffer MCP.

Uso:
    python scripts/prepare_publish.py posts/<carpeta> --image-url URL \
        [--mode customScheduled --due 2026-10-28T12:30:00+01:00 | --mode shareNow | --draft]

Comprueba que la URL de la imagen es pública y que sus bytes son idénticos a post.png
(Buffer no admite subir archivos locales). Escribe buffer_payload.json en la carpeta.
Requiere que validate_post.py haya aprobado la carpeta.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def fetch_bytes(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "DiegoValAcademy/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--image-url", required=True)
    ap.add_argument("--mode", choices=["customScheduled", "shareNow"], default="customScheduled")
    ap.add_argument("--due", help="ISO 8601 con zona (obligatorio con customScheduled)")
    ap.add_argument("--draft", action="store_true", help="guardar como borrador en Buffer (prueba)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()

    val = folder / "validation.md"
    if not val.exists() or "APROBADA para publicar" not in val.read_text(encoding="utf-8"):
        print("ERROR: la carpeta no tiene una validación aprobada (validate_post.py).", file=sys.stderr)
        return 1

    chan = json.loads((ROOT / "config" / "buffer_channel.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    text = (folder / "caption.md").read_text(encoding="utf-8").strip()

    status, ctype, body = fetch_bytes(a.image_url)
    local = (folder / "post.png").read_bytes()
    if status != 200 or not ctype.startswith("image/png") and not ctype.startswith("application/octet-stream"):
        print(f"ERROR: imagen no servida como PNG público (HTTP {status}, {ctype}).", file=sys.stderr)
        return 1
    if hashlib.sha256(body).hexdigest() != hashlib.sha256(local).hexdigest():
        print("ERROR: la imagen pública no coincide byte a byte con post.png.", file=sys.stderr)
        return 1

    payload = {
        "channelId": chan["channel_id"],
        "schedulingType": "automatic",
        "text": text,
        "assets": [{"image": {"url": a.image_url, "metadata": {"altText": meta["alt_text"]}}}],
    }
    if a.draft:
        payload["saveToDraft"] = True
    else:
        payload["mode"] = a.mode
        if a.mode == "customScheduled":
            if not a.due:
                print("ERROR: --due es obligatorio con customScheduled.", file=sys.stderr)
                return 1
            due = datetime.fromisoformat(a.due)
            if due <= datetime.now(ZoneInfo(chan["timezone"])):
                print("ERROR: --due debe estar en el futuro.", file=sys.stderr)
                return 1
            payload["dueAt"] = due.isoformat(timespec="seconds")
    (folder / "buffer_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: imagen pública verificada (sha256 {hashlib.sha256(local).hexdigest()[:12]}…), "
          f"texto {len(text)} caracteres. Payload en {folder / 'buffer_payload.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
