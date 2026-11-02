"""Prepara el payload exacto de create_post de Buffer para un Reel original de Instagram.

Uso:
    python3 scripts/prepare_publish_reel.py posts/<carpeta> --video-url URL --draft      (pruebas: borrador, SIEMPRE permitido)
    python3 scripts/prepare_publish_reel.py posts/<carpeta> --video-url URL --slot       (producción: exige reels.enabled=true)
    python3 scripts/prepare_publish_reel.py posts/<carpeta> --video-url URL --mode customScheduled --due ISO

--video-url: URL pública de reel.mp4 fijada a un SHA de commit ya subido, p. ej.
  https://raw.githubusercontent.com/DVhProjects/diegoval-academy-editorial/<sha>/posts/<carpeta>/reel.mp4

Garantías: validation_reel.md APROBADA (que a su vez exige el carrusel aprobado); la URL pública devuelve un MP4 idéntico
byte a byte al local; la carpeta no figura como publicada/programada EN INSTAGRAM (ni como carrusel ni como Reel);
sin `instagram.reels.enabled=true` en config/publishing.json sólo se permite --draft (la publicación automática de Reels
está APAGADA hasta que el propietario la active). Nunca addToQueue ni notificaciones (schedulingType=automatic).
Escribe buffer_payload_reel.json.
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
from render_reel import OUT_META, OUT_VIDEO  # noqa: E402

PAYLOAD = "buffer_payload_reel.json"


def build(folder: Path, video_url: str, mode: dict, draft: bool, retries: int = 3) -> tuple[dict | None, str]:
    """Devuelve (payload, '') o (None, motivo)."""
    chan = json.loads((ROOT / "config" / "instagram_channel.json").read_text(encoding="utf-8"))
    render = json.loads((folder / OUT_META).read_text(encoding="utf-8"))
    text = (folder / "caption_instagram.md").read_text(encoding="utf-8").strip()
    status, ctype, body, detalle = fetch_bytes(video_url, intentos=max(1, retries))
    if status != 200:
        return None, f"vídeo no accesible ({detalle or status}): {video_url}"
    if not (ctype.startswith("video/") or ctype.startswith("application/octet-stream")):
        return None, f"la URL no sirve un vídeo (Content-Type {ctype})"
    if hashlib.sha256(body).hexdigest() != hashlib.sha256((folder / OUT_VIDEO).read_bytes()).hexdigest():
        return None, f"la URL pública no coincide byte a byte con {OUT_VIDEO}"
    first = render["scenes"][0]  # miniatura: cuando la portada ya está completa
    thumb_ms = max(0, round((first["start_s"] + first["duration_s"] - 0.3) * 1000))
    payload = {
        "channelId": chan["channel_id"],
        "schedulingType": "automatic",
        "text": text,
        "assets": [{"video": {"url": video_url, "metadata": {"thumbnailOffset": thumb_ms}}}],
        "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True}},
    }
    if draft:
        payload["saveToDraft"] = True
    else:
        payload.update(mode)
    return payload, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--video-url", required=True)
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
    ig = pub.get("instagram", {})
    if not a.draft:
        if not ig.get("enabled"):
            return error("Instagram no está activado (instagram.enabled=false): sólo se permite --draft.")
        if not (ig.get("reels") or {}).get("enabled"):
            return error("la publicación automática de Reels está APAGADA (config/publishing.json: instagram.reels.enabled=false): "
                         "sólo se permite --draft. Publica el carrusel.")
    val = folder / "validation_reel.md"
    if not val.exists() or "APROBADA para publicar" not in val.read_text(encoding="utf-8"):
        return error("la carpeta no tiene validación de Reel aprobada (validate_reel.py).")
    ya = [r for r in rows_for("instagram") if r.get("folder") == folder.name and r.get("status") in ("published", "scheduled")]
    if ya and not a.draft:
        return error(f"esta carpeta ya figura como {ya[0]['status']} en Instagram (Buffer {ya[0].get('buffer_post_id') or '?'}); "
                     "un tema se publica una sola vez por plataforma: no se publica además como Reel.")

    tz = ZoneInfo(pub["timezone"])
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(tz)
    meta_p = folder / "metadata.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    if meta.get("do_not_publish") and not a.draft:
        return error("la carpeta está marcada do_not_publish (borrador de revisión): sólo se permite --draft.")
    dias = ig.get("days", ["lunes", "miercoles", "viernes", "sabado"])
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
    payload, why = build(folder, a.video_url, mode, a.draft, a.retries)
    if payload is None:
        return error(why)
    (folder / PAYLOAD).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cuando = payload.get("dueAt", "borrador" if a.draft else "ahora (shareNow)")
    print(f"OK: vídeo público verificado byte a byte, caption {len(payload['text'])} caracteres, publicación: {cuando}. "
          f"Payload en {folder / PAYLOAD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
