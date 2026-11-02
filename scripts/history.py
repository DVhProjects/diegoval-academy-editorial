"""Historial de publicaciones y deduplicación (data/publication_history.csv).

Uso:
    python3 scripts/history.py check <url> [<topic_key>] [--platform linkedin|instagram] [--date AAAA-MM-DD] [--folder NOMBRE]
    python3 scripts/history.py recent [--days N]   # temas usados (todas las plataformas) para descartar candidatos
    python3 scripts/history.py add posts/<carpeta> --status published|scheduled|skipped|draft-test|deleted \
        [--platform linkedin|instagram] [--buffer-post-id ID] [--linkedin-url URL] [--external-url URL] \
        [--image-url URL] [--reason TEXTO]
    python3 scripts/history.py reconcile --buffer-post-id ID --status published|scheduled|deleted \
        [--linkedin-url URL] [--external-url URL] [--date AAAA-MM-DD] [--topic TEXTO]
    python3 scripts/history.py pending [--platform linkedin|instagram]

Política de repetición (2026-11-02; columna `platform`; vacía = linkedin, filas anteriores a Instagram):
- LinkedIn e Instagram pueden publicar el MISMO tema el MISMO día (dos presentaciones de una investigación).
- Un tema ya publicado/programado en CUALQUIER plataforma en un día ANTERIOR no se repite, salvo información nueva
  y relevante (`metadata.repeat_justification`, ≥ 40 caracteres).
- En la misma plataforma un tema no se repite nunca el mismo día ni después (sin justificación, tampoco antes).
`find_repeats` es la única función que decide; `check`, los validadores y `plan_day.py` la usan.
Una fila por (carpeta, plataforma).

Reglas: `published` exige buffer_post_id y linkedin_url (confirmados con get_post);
`scheduled` exige buffer_post_id. Así nada cuenta como publicado sin confirmación de Buffer.
`reconcile` actualiza (o crea) la fila de un post de Buffer aunque falte su carpeta,
para recuperar el estado tras una interrupción. `pending` lista lo programado sin confirmar.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import video as videomod

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "publication_history.csv"
FIELDS = ["publication_date", "weekday", "type", "category", "topic", "topic_key", "official_url",
          "deadline", "buffer_channel_id", "buffer_post_id", "linkedin_url", "image_url",
          "status", "verified_date", "folder", "reason", "format", "video_url", "platform", "external_url"]
STATUSES = ["published", "scheduled", "skipped", "draft-test", "deleted"]
PLATFORMS = ["linkedin", "instagram"]


class HistoryError(Exception):
    pass


def canonical_url(url: str) -> str:
    """Esquema y www fuera, minúsculas en host, sin query/fragment ni barra final."""
    if not url:
        return ""
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def read_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    with HISTORY.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_history(rows: list[dict]) -> None:
    with HISTORY.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def row_platform(row: dict) -> str:
    """Plataforma de una fila; vacía = linkedin (filas anteriores a Instagram)."""
    return (row.get("platform") or "linkedin").strip().lower()


def rows_for(platform: str = "linkedin") -> list[dict]:
    return [r for r in read_history() if row_platform(r) == platform]


MIN_JUSTIFICATION = 40


def repeat_justified(meta: dict) -> bool:
    """True si el metadata justifica repetir un tema de un día anterior con información nueva y relevante."""
    return len(str((meta or {}).get("repeat_justification", "")).strip()) >= MIN_JUSTIFICATION


def today_stockholm() -> str:
    return datetime.now(ZoneInfo("Europe/Stockholm")).date().isoformat()


def find_repeats(url: str, topic_key: str | None, platform: str = "linkedin", on_date: str | None = None,
                 folder: str | None = None, video_url: str | None = None, justified: bool = False,
                 rows: list[dict] | None = None) -> list[dict]:
    """Filas del historial que BLOQUEAN publicar este tema en `platform` con fecha `on_date`.

    Coincide por URL canónica, topic_key o vídeo. Bloquea (solo filas published/scheduled de otra carpeta):
    - misma plataforma: cualquier fecha (el mismo día también es repetición);
    - otra plataforma: solo si su fecha es ANTERIOR a `on_date` (o desconocida). El mismo día, o posterior, es
      la publicación simultánea de la misma investigación y se permite.
    Con `justified=True` (información nueva documentada) se permiten las filas de días anteriores, pero nunca una
    repetición en la misma plataforma el mismo día.
    """
    on_date = on_date or today_stockholm()
    cu = canonical_url(url)
    vid = videomod.video_id(video_url or "") or videomod.video_id(url or "")
    out = []
    for r in (read_history() if rows is None else rows):
        if r.get("status") not in ("published", "scheduled") or (folder and r.get("folder") == folder):
            continue
        if not (cu and canonical_url(r.get("official_url", "")) == cu
                or (topic_key and r.get("topic_key") == topic_key)
                or (vid and videomod.video_id(r.get("video_url", "")) == vid)):
            continue
        rdate = (r.get("publication_date") or "").strip()
        earlier = not rdate or rdate < on_date
        if row_platform(r) == platform:
            if justified and earlier:
                continue
            out.append(r)
        elif earlier and not justified:
            out.append(r)
    return out


def describe_repeats(rows: list[dict]) -> str:
    return "; ".join(f"{r.get('publication_date') or 'sin fecha'} {row_platform(r)}: {r.get('topic') or r.get('folder')}"
                     for r in rows)


def check(url: str, topic_key: str | None, platform: str = "linkedin", on_date: str | None = None,
          folder: str | None = None, justified: bool = False) -> list[dict]:
    return find_repeats(url, topic_key, platform, on_date, folder, justified=justified)


def recent(days: int = 90) -> list[dict]:
    """Temas publicados/programados en cualquier plataforma en los últimos `days` días (para descartar candidatos)."""
    since = (datetime.now(ZoneInfo("Europe/Stockholm")).date() - timedelta(days=days)).isoformat()
    return sorted((r for r in read_history() if r.get("status") in ("published", "scheduled")
                   and (r.get("publication_date") or "") >= since),
                  key=lambda r: r.get("publication_date", ""))


def require_confirmation(status: str, buffer_post_id: str | None, linkedin_url: str | None,
                         platform: str = "linkedin", external_url: str | None = None) -> None:
    if status in ("published", "scheduled") and not buffer_post_id:
        raise HistoryError(f"'{status}' exige --buffer-post-id confirmado con get_post")
    if status == "published" and platform == "linkedin" and not linkedin_url:
        raise HistoryError("'published' exige --linkedin-url (externalLink de get_post)")
    if status == "published" and platform == "instagram" and not external_url:
        raise HistoryError("'published' en instagram exige --external-url (externalLink de get_post)")


def add(folder: Path, status: str, platform: str = "linkedin", **extra) -> dict:
    if platform not in PLATFORMS:
        raise HistoryError(f"plataforma desconocida: {platform}")
    require_confirmation(status, extra.get("buffer_post_id"), extra.get("linkedin_url"), platform,
                         extra.get("external_url"))
    mpath = folder / "metadata.json"
    meta = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    if not meta and status not in ("skipped", "draft-test"):
        raise HistoryError(f"falta {mpath}")
    if meta.get("do_not_publish") and status in ("scheduled", "published"):
        raise HistoryError(f"{folder.name} está marcada do_not_publish (borrador de revisión): no puede figurar como {status}.")
    row = {
        "publication_date": meta.get("date", folder.name[:10]), "weekday": meta.get("weekday", ""),
        "type": meta.get("type", ""), "category": meta.get("category", ""), "topic": meta.get("topic", folder.name),
        "topic_key": meta.get("topic_key", ""), "official_url": meta.get("primary_url", ""),
        "deadline": meta.get("deadline") or "", "buffer_channel_id": meta.get("buffer_channel_id", ""),
        "status": status, "verified_date": meta.get("verified_date", ""), "folder": folder.name,
        "format": meta.get("format", "image"), "video_url": (meta.get("video") or {}).get("url", ""),
        "platform": platform,
    }
    if platform == "instagram":  # el canal de Instagram es otro: no heredar el de LinkedIn del metadata
        row["buffer_channel_id"] = meta.get("instagram_channel_id", "")
    row.update({k: v for k, v in extra.items() if v})
    rows = [r for r in read_history()
            if not (r.get("folder") == folder.name and row_platform(r) == platform)]  # una fila por carpeta y plataforma
    rows.append(row)
    write_history(rows)
    return row


def reconcile(buffer_post_id: str, status: str, linkedin_url: str | None = None,
              date: str | None = None, topic: str | None = None, platform: str = "linkedin",
              external_url: str | None = None) -> dict:
    require_confirmation(status, buffer_post_id, linkedin_url, platform, external_url)
    rows = read_history()
    row = next((r for r in rows if r.get("buffer_post_id") == buffer_post_id), None)
    if row is None:
        row = {k: "" for k in FIELDS} | {"buffer_post_id": buffer_post_id, "publication_date": date or "",
                                          "topic": topic or "", "platform": platform,
                                          "reason": "reconciliado desde Buffer (sin carpeta)"}
        rows.append(row)
    row["status"] = status
    if linkedin_url:
        row["linkedin_url"] = linkedin_url
    if external_url:
        row["external_url"] = external_url
    write_history(rows)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("url")
    c.add_argument("topic_key", nargs="?")
    c.add_argument("--platform", choices=PLATFORMS, default="linkedin")
    c.add_argument("--date", help="fecha de publicación AAAA-MM-DD (por defecto hoy, Europe/Stockholm)")
    c.add_argument("--folder", help="carpeta propia (se ignora al buscar coincidencias)")
    c.add_argument("--justified", action="store_true", help="hay información nueva documentada (repeat_justification)")
    rc = sub.add_parser("recent")
    rc.add_argument("--days", type=int, default=90)
    a = sub.add_parser("add")
    a.add_argument("--platform", choices=PLATFORMS, default="linkedin")
    a.add_argument("--external-url", dest="external_url")
    a.add_argument("folder", type=Path)
    a.add_argument("--status", required=True, choices=STATUSES)
    a.add_argument("--buffer-post-id", dest="buffer_post_id")
    a.add_argument("--linkedin-url", dest="linkedin_url")
    a.add_argument("--image-url", dest="image_url")
    a.add_argument("--reason")
    r = sub.add_parser("reconcile")
    r.add_argument("--buffer-post-id", dest="buffer_post_id", required=True)
    r.add_argument("--status", required=True, choices=["published", "scheduled", "deleted"])
    r.add_argument("--linkedin-url", dest="linkedin_url")
    r.add_argument("--date")
    r.add_argument("--topic")
    r.add_argument("--platform", choices=PLATFORMS, default="linkedin")
    r.add_argument("--external-url", dest="external_url")
    pe = sub.add_parser("pending")
    pe.add_argument("--platform", choices=PLATFORMS, default="linkedin")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.cmd == "check":
            dups = check(args.url, args.topic_key, args.platform, args.date, args.folder, args.justified)
            print(json.dumps(dups, ensure_ascii=False, indent=2) if dups else "SIN DUPLICADOS")
            return 1 if dups else 0
        if args.cmd == "recent":
            for r in recent(args.days):
                print(f"{r.get('publication_date')} {row_platform(r):9} {r.get('topic_key') or '-':40} {r.get('official_url')}")
            return 0
        if args.cmd == "pending":
            for row in rows_for(args.platform):
                if row.get("status") == "scheduled":
                    print(f"{row['publication_date']} {row['buffer_post_id']} {row['folder']}")
            return 0
        if args.cmd == "reconcile":
            row = reconcile(args.buffer_post_id, args.status, args.linkedin_url, args.date, args.topic,
                            args.platform, args.external_url)
        else:
            row = add(args.folder.resolve(), args.status, platform=args.platform, buffer_post_id=args.buffer_post_id,
                      linkedin_url=args.linkedin_url, external_url=args.external_url,
                      image_url=args.image_url, reason=args.reason)
    except HistoryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
