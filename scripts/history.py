"""Historial de publicaciones y deduplicación (data/publication_history.csv).

Uso:
    python scripts/history.py check <url> [<topic_key>]
    python scripts/history.py add posts/<carpeta> --status published|scheduled|skipped|draft-test \
        [--buffer-post-id ID] [--linkedin-url URL] [--image-url URL] [--reason TEXTO]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "publication_history.csv"
FIELDS = ["publication_date", "weekday", "type", "category", "topic", "topic_key", "official_url",
          "deadline", "buffer_channel_id", "buffer_post_id", "linkedin_url", "image_url",
          "status", "verified_date", "folder", "reason"]


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
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def check(url: str, topic_key: str | None) -> list[dict]:
    cu = canonical_url(url)
    return [r for r in read_history() if r.get("status") in ("published", "scheduled")
            and (canonical_url(r.get("official_url", "")) == cu or (topic_key and r.get("topic_key") == topic_key))]


def add(folder: Path, status: str, **extra) -> dict:
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    row = {
        "publication_date": meta["date"], "weekday": meta.get("weekday", ""), "type": meta["type"],
        "category": meta.get("category", ""), "topic": meta["topic"], "topic_key": meta["topic_key"],
        "official_url": meta["primary_url"], "deadline": meta.get("deadline") or "",
        "buffer_channel_id": meta["buffer_channel_id"], "status": status,
        "verified_date": meta["verified_date"], "folder": folder.name,
    }
    row.update({k: v for k, v in extra.items() if v})
    rows = [r for r in read_history() if r.get("folder") != folder.name]  # una fila por carpeta
    rows.append(row)
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
    a.add_argument("--status", required=True, choices=["published", "scheduled", "skipped", "draft-test"])
    a.add_argument("--buffer-post-id", dest="buffer_post_id")
    a.add_argument("--linkedin-url", dest="linkedin_url")
    a.add_argument("--image-url", dest="image_url")
    a.add_argument("--reason")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "check":
        dups = check(args.url, args.topic_key)
        print(json.dumps(dups, ensure_ascii=False, indent=2) if dups else "SIN DUPLICADOS")
        return 1 if dups else 0
    row = add(args.folder.resolve(), args.status, buffer_post_id=args.buffer_post_id,
              linkedin_url=args.linkedin_url, image_url=args.image_url, reason=args.reason)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
