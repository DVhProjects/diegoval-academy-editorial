"""Plan del día por plataforma (LinkedIn e Instagram son INDEPENDIENTES).

Uso:
    python3 scripts/plan_day.py [--now ISO8601]

Imprime un JSON con, para cada plataforma, `due` (¿toca publicar hoy?), `reason` y, en Instagram, `reuse_folder`
(carpeta de LinkedIn de hoy cuya investigación puede reutilizarse; None => investigación propia).

Reglas:
- Días: LinkedIn = claves de `calendar`; Instagram = `instagram.days` (miércoles, viernes y sábado).
- Instagram sólo si `instagram.enabled` es true.
- La deduplicación es POR CANAL: sólo cuentan las filas (scheduled/published) de la propia plataforma con fecha de hoy.
  Que LinkedIn ya haya publicado, haya fallado (skipped) o no tenga contenido NO cambia `due` de Instagram, ni al revés.
- Las carpetas marcadas `do_not_publish` (borradores de revisión) nunca se proponen para reutilizar.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from history import read_history, row_platform  # noqa: E402

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DONE = ("scheduled", "published")


def folder_blocked(folder: str) -> bool:
    meta = ROOT / "posts" / folder / "metadata.json"
    if not meta.exists():
        return False
    try:
        return bool(json.loads(meta.read_text(encoding="utf-8")).get("do_not_publish"))
    except ValueError:
        return True


def plan(now: datetime, pub: dict, rows: list[dict], blocked: Callable[[str], bool] = folder_blocked) -> dict:
    tz = ZoneInfo(pub["timezone"])
    now = now.astimezone(tz)
    today, dia = now.date().isoformat(), DIAS[now.weekday()]

    def done_today(platform: str) -> list[dict]:
        return [r for r in rows if row_platform(r) == platform and r.get("status") in DONE
                and r.get("publication_date") == today]

    out: dict = {"date": today, "weekday": dia}

    # LinkedIn
    if dia not in pub.get("calendar", {}):
        out["linkedin"] = {"due": False, "reason": "hoy no es día de publicación de LinkedIn"}
    elif done_today("linkedin"):
        out["linkedin"] = {"due": False, "reason": "LinkedIn ya tiene una publicación de hoy (programada o publicada)"}
    else:
        out["linkedin"] = {"due": True, "reason": "toca LinkedIn"}

    # Instagram (no mira el estado de LinkedIn para decidir `due`)
    ig = pub.get("instagram", {})
    if not ig.get("enabled"):
        out["instagram"] = {"due": False, "reason": "instagram.enabled=false", "reuse_folder": None}
    elif dia not in ig.get("days", ["miercoles", "viernes", "sabado"]):
        out["instagram"] = {"due": False, "reason": "hoy no es día de publicación de Instagram", "reuse_folder": None}
    elif done_today("instagram"):
        out["instagram"] = {"due": False, "reason": "Instagram ya tiene una publicación de hoy", "reuse_folder": None}
    else:
        reuse = next((r["folder"] for r in done_today("linkedin") if r.get("folder") and not blocked(r["folder"])), None)
        out["instagram"] = {"due": True, "reuse_folder": reuse,
                            "reason": ("toca Instagram; reutiliza la investigación de " + reuse) if reuse
                            else "toca Instagram; investigación propia (LinkedIn no aportó contenido hoy)"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="ISO 8601 con zona; por defecto, ahora")
    a = ap.parse_args(argv)
    pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(ZoneInfo(pub["timezone"]))
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(plan(now, pub, read_history()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
