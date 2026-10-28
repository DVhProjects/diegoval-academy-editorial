"""Radar de becas: seguimiento de convocatorias abiertas, próximas y recurrentes (data/radar_becas.csv).

Uso:
    python scripts/radar.py list [--estado abierta|proxima_confirmada|recurrente_pendiente|por_verificar|cerrada]
    python scripts/radar.py due [--dias 14]
    python scripts/radar.py upsert "<programa>" campo=valor [campo=valor ...]

`due` lista lo que la rutina debe revisar esta semana: entradas sin revisar en `--dias` días,
próximas aperturas en los siguientes 30 días y convocatorias abiertas aún no publicadas.
`upsert` crea o actualiza una fila y pone `ultima_revision` = hoy (Europe/Stockholm).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RADAR = ROOT / "data" / "radar_becas.csv"
FIELDS = ["programa", "organiza", "pais", "nivel", "url_oficial", "estado", "abre", "plazo",
          "ultima_revision", "evidencia_popularidad", "publicado_en", "notas"]
ESTADOS = {"abierta", "proxima_confirmada", "recurrente_pendiente", "por_verificar", "cerrada"}


def today() -> date:
    return datetime.now(ZoneInfo("Europe/Stockholm")).date()


def read() -> list[dict]:
    with RADAR.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(rows: list[dict]) -> None:
    with RADAR.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def due(rows: list[dict], dias: int) -> list[tuple[str, dict]]:
    hoy, out = today(), []
    for r in rows:
        rev = parse_date(r.get("ultima_revision", ""))
        abre = parse_date(r.get("abre", ""))
        if r["estado"] == "cerrada":
            continue
        if rev is None or hoy - rev > timedelta(days=dias):
            out.append(("revisar (sin comprobar recientemente)", r))
        elif r["estado"] == "proxima_confirmada" and abre and hoy <= abre <= hoy + timedelta(days=30):
            out.append(("abre en los próximos 30 días", r))
        elif r["estado"] == "abierta" and not r.get("publicado_en"):
            out.append(("abierta y aún no publicada", r))
    return out


def show(r: dict) -> str:
    return (f"- {r['programa']} [{r['estado']}] abre={r['abre'] or '-'} plazo={r['plazo'] or '-'} "
            f"revisado={r['ultima_revision'] or 'nunca'} publicado={r['publicado_en'] or 'no'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--estado", choices=sorted(ESTADOS))
    du = sub.add_parser("due")
    du.add_argument("--dias", type=int, default=14)
    up = sub.add_parser("upsert")
    up.add_argument("programa")
    up.add_argument("cambios", nargs="*", help="campo=valor")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rows = read()
    if a.cmd == "list":
        for r in rows:
            if not a.estado or r["estado"] == a.estado:
                print(show(r))
        return 0
    if a.cmd == "due":
        for motivo, r in due(rows, a.dias):
            print(f"{show(r)}  ← {motivo}")
        return 0
    cambios = dict(c.split("=", 1) for c in a.cambios)
    bad = set(cambios) - set(FIELDS)
    if bad:
        print(f"ERROR: campos desconocidos {sorted(bad)}", file=sys.stderr)
        return 1
    if "estado" in cambios and cambios["estado"] not in ESTADOS:
        print(f"ERROR: estado debe ser uno de {sorted(ESTADOS)}", file=sys.stderr)
        return 1
    row = next((r for r in rows if r["programa"] == a.programa), None)
    if row is None:
        row = {k: "" for k in FIELDS} | {"programa": a.programa, "estado": "por_verificar"}
        rows.append(row)
    row.update(cambios)
    row["ultima_revision"] = cambios.get("ultima_revision", today().isoformat())
    write(rows)
    print(show(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
