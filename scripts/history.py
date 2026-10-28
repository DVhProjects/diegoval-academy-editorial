"""Historial de publicaciones y deduplicación (data/publication_history.csv).

Uso:
    python3 scripts/history.py check <url> [<topic_key>]
    python3 scripts/history.py add posts/<carpeta> --status published|scheduled|skipped|draft-test|deleted \
        [--buffer-post-id ID] [--linkedin-url URL] [--image-url URL] [--reason TEXTO]
    python3 scripts/history.py reconcile --buffer-post-id ID --status published|scheduled|deleted \
        [--linkedin-url URL] [--date AAAA-MM-DD] [--topic TEXTO]
    python3 scripts/history.py pending

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
from pathlib import Path
from urllib.parse import urlsplit

import video as videomod

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "publication_history.csv"
FIELDS = ["publication_date", "weekday", "type", "category", "topic", "topic_key", "official_url",
          "deadline", "buffer_channel_id", "buffer_post_id", "linkedin_url", "image_url",
          "status", "verified_date", "folder", "reason", "format", "video_url"]
STATUSES = ["published", "scheduled", "skipped", "draft-test", "deleted"]


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


def check(url: str, topic_key: str | None) -> list[dict]:
    cu = canonical_url(url)
    vid = videomod.video_id(url)
    return [r for r in read_history() if r.get("status") in ("published", "scheduled")
            and (canonical_url(r.get("official_url", "")) == cu or (topic_key and r.get("topic_key") == topic_key)
                 or (vid and videomod.video_id(r.get("video_url", "")) == vid))]


def require_confirmation(status: str, buffer_post_id: str | None, linkedin_url: str | None) -> None:
    if status in ("published", "scheduled") and not buffer_post_id:
        raise HistoryError(f"'{status}' exige --buffer-post-id confirmado con get_post")
    if status == "published" and not linkedin_url:
        raise HistoryError("'published' exige --linkedin-url (externalLink de get_post)")


def add(folder: Path, status: str, **extra) -> dict:
    require_confirmation(status, extra.get("buffer_post_id"), extra.get("linkedin_url"))
    mpath = folder / "metadata.json"
    meta = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    if not meta and status not in ("skipped", "draft-test"):
        raise HistoryError(f"falta {mpath}")
    row = {
        "publication_date": meta.get("date", folder.name[:10]), "weekday": meta.get("weekday", ""),
        "type": meta.get("type", ""), "category": meta.get("category", ""), "topic": meta.get("topic", folder.name),
        "topic_key": meta.get("topic_key", ""), "official_url": meta.get("primary_url", ""),
        "deadline": meta.get("deadline") or "", "buffer_channel_id": meta.get("buffer_channel_id", ""),
        "status": status, "verified_date": meta.get("verified_date", ""), "folder": folder.name,
        "format": meta.get("format", "image"), "video_url": (meta.get("video") or {}).get("url", ""),
    }
    row.update({k: v for k, v in extra.items() if v})
    rows = [r for r in read_history() if r.get("folder") != folder.name]  # una fila por carpeta
    rows.append(row)
    write_history(rows)
    return row


def reconcile(buffer_post_id: str, status: str, linkedin_url: str | None = None,
              date: str | None = None, topic: str | None = None) -> dict:
    require_confirmation(status, buffer_post_id, linkedin_url)
    rows = read_history()
    row = next((r for r in rows if r.get("buffer_post_id") == buffer_post_id), None)
    if row is None:
        row = {k: "" for k in FIELDS} | {"buffer_post_id": buffer_post_id, "publication_date": date or "",
                                          "topic": topic or "", "reason": "reconciliado desde Buffer (sin carpeta)"}
        rows.append(row)
    row["status"] = status
    if linkedin_url:
        row["linkedin_url"] = linkedin_url
    write_history(rows)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("url")
    c.add_argument("topic_key", nargs="?")
    a = sub.add_parser("add")
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
    sub.add_parser("pending")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.cmd == "check":
            dups = check(args.url, args.topic_key)
            print(json.dumps(dups, ensure_ascii=False, indent=2) if dups else "SIN DUPLICADOS")
            return 1 if dups else 0
        if args.cmd == "pending":
            for row in read_history():
                if row.get("status") == "scheduled":
                    print(f"{row['publication_date']} {row['buffer_post_id']} {row['folder']}")
            return 0
        if args.cmd == "reconcile":
            row = reconcile(args.buffer_post_id, args.status, args.linkedin_url, args.date, args.topic)
        else:
            row = add(args.folder.resolve(), args.status, buffer_post_id=args.buffer_post_id,
                      linkedin_url=args.linkedin_url, image_url=args.image_url, reason=args.reason)
    except HistoryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
