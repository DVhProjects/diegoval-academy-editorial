"""Prepara el payload exacto de create_post de Buffer para el carrusel de Instagram (5 imágenes).

Uso:
    python3 scripts/prepare_publish_instagram.py posts/<carpeta> --base-url URL --slot      (producción)
    python3 scripts/prepare_publish_instagram.py posts/<carpeta> --base-url URL --draft     (pruebas, borrador)
    python3 scripts/prepare_publish_instagram.py posts/<carpeta> --base-url URL --mode customScheduled --due ISO

--base-url: carpeta pública de la publicación fijada a un SHA ya subido, SIN barra final, p. ej.
  https://raw.githubusercontent.com/DVhProjects/diegoval-academy-editorial/<sha>/posts/<carpeta>
  (se leen <base-url>/slide-1.png … slide-5.png).

Garantías: validation_instagram.md APROBADA; las 5 URLs públicas devuelven un PNG idéntico byte a byte al local;
la carpeta no figura como publicada/programada EN INSTAGRAM; sin `instagram.enabled=true` en config/publishing.json
sólo se permite --draft. Hora: la misma que LinkedIn (--slot, Europe/Stockholm) o shareNow si ya pasó el límite.
Escribe buffer_payload_instagram.json. Nunca addToQueue ni notificaciones (schedulingType=automatic).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from history import rows_for  # noqa: E402
from prepare_publish import DIAS, fetch_bytes, slot_config, slot_payload  # noqa: E402
from render_carousel import N_SLIDES, texts_of  # noqa: E402

PAYLOAD = "buffer_payload_instagram.json"


def alt_texts(spec: dict) -> list[str]:
    cov = spec["cover"]
    alts = [f"Portada: {cov['title']} {cov.get('subtitle', '')}".strip()]
    for s in spec["slides"]:
        alts.append(f"{s['title']}. " + " ".join(i["text"] for i in s["items"]) + (f" {s['cta']}" if s.get("cta") else ""))
    return [a[:900] for a in alts]


def build(folder: Path, base_url: str, mode: dict, draft: bool, retries: int = 3) -> tuple[dict | None, str]:
    """Devuelve (payload, '') o (None, motivo)."""
    chan = json.loads((ROOT / "config" / "instagram_channel.json").read_text(encoding="utf-8"))
    spec = json.loads((folder / "carousel.json").read_text(encoding="utf-8"))
    text = (folder / "caption_instagram.md").read_text(encoding="utf-8").strip()
    assets = []
    for i, alt in enumerate(alt_texts(spec), start=1):
        url = f"{base_url.rstrip('/')}/slide-{i}.png"
        status, ctype, body, detalle = fetch_bytes(url, intentos=max(1, retries))
        if status != 200:
            return None, f"imagen {i} no accesible ({detalle or status}): {url}"
        if not (ctype.startswith("image/png") or ctype.startswith("application/octet-stream")):
            return None, f"imagen {i}: la URL no sirve un PNG (Content-Type {ctype})"
        local = (folder / f"slide-{i}.png").read_bytes()
        if hashlib.sha256(body).hexdigest() != hashlib.sha256(local).hexdigest():
            return None, f"imagen {i}: la URL pública no coincide byte a byte con slide-{i}.png"
        assets.append({"image": {"url": url, "metadata": {"altText": alt}}})
    payload = {
        "channelId": chan["channel_id"],
        "schedulingType": "automatic",
        "text": text,
        "assets": assets,
        "metadata": {"instagram": {"type": "post", "shouldShareToFeed": True}},
    }
    if draft:
        payload["saveToDraft"] = True
    else:
        payload.update(mode)
    return payload, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--slot", action="store_true")
    ap.add_argument("--mode", choices=["customScheduled", "shareNow"])
    ap.add_argument("--due")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--now", help="ISO 8601 con zona; sólo pruebas")
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()

    def error(msg: str) -> int:
        print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    if sum(bool(x) for x in (a.slot, a.mode, a.draft)) != 1:
        return error("usa exactamente una opción: --slot, --mode o --draft.")
    pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
    if not a.draft and not pub.get("instagram", {}).get("enabled"):
        return error("Instagram no está activado (config/publishing.json: instagram.enabled=false): sólo se permite --draft.")
    val = folder / "validation_instagram.md"
    if not val.exists() or "APROBADA para publicar" not in val.read_text(encoding="utf-8"):
        return error("la carpeta no tiene validación de Instagram aprobada (validate_carousel.py).")
    ya = [r for r in rows_for("instagram") if r.get("folder") == folder.name and r.get("status") in ("published", "scheduled")]
    if ya and not a.draft:
        return error(f"esta carpeta ya figura como {ya[0]['status']} en Instagram (Buffer {ya[0].get('buffer_post_id') or '?'}); no se repite.")

    tz = ZoneInfo(pub["timezone"])
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(tz)
    meta_p = folder / "metadata.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    if meta.get("do_not_publish") and not a.draft:
        return error("la carpeta está marcada do_not_publish (borrador de revisión): sólo se permite --draft.")
    dias = pub["instagram"].get("days", ["miercoles", "viernes", "sabado"])
    if a.slot and DIAS[now.astimezone(tz).weekday()] not in dias:
        return error(f"hoy no es día de publicación de Instagram ({', '.join(dias)}).")
    mode: dict = {}
    if a.slot:
        mode = slot_payload(now, slot_config(now, pub))
    elif a.mode:
        mode = {"mode": a.mode}
        if a.mode == "customScheduled":
            if not a.due:
                return error("--due es obligatorio con customScheduled.")
            due = datetime.fromisoformat(a.due)
            if due <= now:
                return error("--due debe estar en el futuro.")
            mode["dueAt"] = due.isoformat(timespec="seconds")
    payload, why = build(folder, a.base_url, mode, a.draft, a.retries)
    if payload is None:
        return error(why)
    (folder / PAYLOAD).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cuando = payload.get("dueAt", "borrador" if a.draft else "ahora (shareNow)")
    print(f"OK: {N_SLIDES} imágenes públicas verificadas byte a byte, caption {len(payload['text'])} caracteres, "
          f"publicación: {cuando}. Payload en {folder / PAYLOAD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
