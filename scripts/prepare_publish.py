"""Prepara el payload exacto para la herramienta create_post de Buffer MCP.

Uso:
    python3 scripts/prepare_publish.py posts/<carpeta> --image-url URL --slot        (formato imagen)
    python3 scripts/prepare_publish.py posts/<carpeta> --slot                        (formato vídeo: sin --image-url)
    python3 scripts/prepare_publish.py posts/<carpeta> --image-url URL \
        [--mode customScheduled --due 2026-10-28T12:30:00+01:00 | --mode shareNow | --draft]

--slot: hoy a la hora de config/publishing.json (12:30 Europe/Stockholm, con el desfase
CET/CEST correcto); si ya pasó la hora límite (12:15) usa shareNow.

Comprueba que la URL de la imagen es pública y que sus bytes son idénticos a post.png
(Buffer no admite subir archivos locales), con reintentos porque raw.githubusercontent.com
puede tardar unos segundos tras el push. Se niega si la carpeta ya está registrada como
publicada o programada (evita duplicados tras un fallo parcial). Escribe buffer_payload.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from history import read_history  # noqa: E402
import video as videomod  # noqa: E402


def fetch_bytes(url: str, intentos: int = 3, espera: float = 10.0) -> tuple[int | None, str, bytes, str]:
    ultimo = ""
    for i in range(intentos):
        req = urllib.request.Request(url, headers={"User-Agent": "DiegoValAcademy/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read(), ""
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
        except Exception as e:  # red, DNS, TLS, proxy
            ultimo = f"{type(e).__name__}: {e}"
        if i < intentos - 1:
            time.sleep(espera)
    return None, "", b"", ultimo


def slot_payload(now: datetime, pub: dict) -> dict:
    """customScheduled hoy a la hora configurada, o shareNow si ya pasó la hora límite."""
    tz = ZoneInfo(pub["timezone"])
    now = now.astimezone(tz)
    hh, mm = map(int, pub.get("publish_time", "12:30").split(":"))
    lh, lm = map(int, pub.get("share_now_after", "12:15").split(":"))
    if now.time() >= dtime(lh, lm):
        return {"mode": "shareNow"}
    due = datetime.combine(now.date(), dtime(hh, mm), tzinfo=tz)
    return {"mode": "customScheduled", "dueAt": due.isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--image-url", help="URL pública de post.png (obligatoria en formato imagen)")
    ap.add_argument("--slot", action="store_true", help="hora de publicación del calendario (recomendado)")
    ap.add_argument("--mode", choices=["customScheduled", "shareNow"])
    ap.add_argument("--due", help="ISO 8601 con zona (con --mode customScheduled)")
    ap.add_argument("--draft", action="store_true", help="guardar como borrador en Buffer (pruebas)")
    ap.add_argument("--now", help="ISO 8601 con zona; sólo para pruebas")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--skip-video-check", action="store_true", help="sólo para pruebas sin red")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()

    def error(msg: str) -> int:
        print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    val = folder / "validation.md"
    if not val.exists() or "APROBADA para publicar" not in val.read_text(encoding="utf-8"):
        return error("la carpeta no tiene una validación aprobada (validate_post.py).")
    if sum(bool(x) for x in (a.slot, a.mode, a.draft)) != 1:
        return error("usa exactamente una opción: --slot, --mode o --draft.")

    ya = [r for r in read_history() if r.get("folder") == folder.name and r.get("status") in ("published", "scheduled")]
    if ya and not a.draft:
        return error(f"esta carpeta ya figura como {ya[0]['status']} (Buffer {ya[0].get('buffer_post_id') or '?'}); no se repite.")

    chan = json.loads((ROOT / "config" / "buffer_channel.json").read_text(encoding="utf-8"))
    pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    text = (folder / "caption.md").read_text(encoding="utf-8").strip()
    tz = ZoneInfo(pub["timezone"])
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(tz)

    is_video = meta.get("format") == "video"
    if is_video:
        # Formato vídeo: el enlace con vista previa es el contenido principal; nunca se sube un archivo de vídeo.
        canon = videomod.canonical_video_url((meta.get("video") or {}).get("url", ""))
        if not canon:
            return error("metadata.video.url no es un enlace de YouTube válido.")
        info = {}
        if not a.skip_video_check:
            info = videomod.inspect(canon, now.date())
            if info["errors"] or not info.get("title"):
                return error(f"el vídeo no es accesible ({info['errors']}).")
        payload = {
            "channelId": chan["channel_id"],
            "schedulingType": "automatic",
            "text": text,
            "metadata": {"linkedin": {"linkAttachment": {"url": canon}}},
        }
        local = b""
    else:
        if not a.image_url:
            return error("--image-url es obligatorio en el formato imagen.")
        status, ctype, body, detalle = fetch_bytes(a.image_url, intentos=max(1, a.retries))
        if status != 200:
            return error(f"imagen pública no accesible ({detalle or status}): {a.image_url}")
        if not (ctype.startswith("image/png") or ctype.startswith("application/octet-stream")):
            return error(f"la URL no sirve un PNG (Content-Type {ctype}).")
        local = (folder / "post.png").read_bytes()
        if hashlib.sha256(body).hexdigest() != hashlib.sha256(local).hexdigest():
            return error("la imagen pública no coincide byte a byte con post.png.")
        payload = {
            "channelId": chan["channel_id"],
            "schedulingType": "automatic",
            "text": text,
            "assets": [{"image": {"url": a.image_url, "metadata": {"altText": meta["alt_text"]}}}],
        }
    if a.draft:
        payload["saveToDraft"] = True
    elif a.slot:
        payload.update(slot_payload(now, pub["calendar_defaults"] | {"timezone": pub["timezone"]}))
    else:
        payload["mode"] = a.mode
        if a.mode == "customScheduled":
            if not a.due:
                return error("--due es obligatorio con customScheduled.")
            due = datetime.fromisoformat(a.due)
            if due <= now:
                return error("--due debe estar en el futuro.")
            payload["dueAt"] = due.isoformat(timespec="seconds")
    (folder / "buffer_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cuando = payload.get("dueAt", "borrador" if a.draft else "ahora (shareNow)")
    what = "vídeo verificado (enlace con vista previa)" if is_video else f"imagen pública verificada (sha256 {hashlib.sha256(local).hexdigest()[:12]}…)"
    print(f"OK: {what}, texto {len(text)} caracteres, publicación: {cuando}. Payload en {folder / 'buffer_payload.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
