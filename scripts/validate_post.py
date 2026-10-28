"""Valida una carpeta de publicación antes de enviarla a Buffer.

Uso:
    python scripts/validate_post.py posts/<carpeta> [--now 2026-10-27T16:40:00+01:00] [--skip-network]

Escribe posts/<carpeta>/validation.md y termina con código 0 sólo si TODAS las
comprobaciones bloqueantes pasan. Los avisos (WARN) deben resolverse a mano y
documentarse en sources.md antes de publicar.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from history import canonical_url, read_history  # noqa: E402

REQUIRED_FILES = ["post.json", "post.png", "caption.md", "sources.md", "metadata.json"]
REQUIRED_META = ["date", "type", "topic", "topic_key", "primary_url", "verified_date",
                 "buffer_channel_id", "alt_text", "status"]
URL_RE = re.compile(r"https?://[^\s)>\]]+")
PLACEHOLDERS = re.compile(r"TODO|TBD|XXX|lorem ipsum|\{\{|\}\}", re.IGNORECASE)
UA = "Mozilla/5.0 (compatible; DiegoValAcademy-LinkCheck/1.0)"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def http_status(url: str) -> tuple[int | None, str]:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return e.code, url
        except Exception as e:  # DNS, timeout, TLS
            if method == "HEAD":
                continue
            return None, f"{type(e).__name__}: {e}"
    return None, "sin respuesta"


def validate(folder: Path, now: datetime, skip_network: bool) -> tuple[list, bool]:
    pub = load_json(ROOT / "config" / "publishing.json")
    chan = load_json(ROOT / "config" / "buffer_channel.json")
    tz = ZoneInfo(pub["timezone"])
    results: list[tuple[str, str, str]] = []  # (estado, comprobación, detalle)

    def ok(name, detail=""):
        results.append(("PASS", name, detail))

    def fail(name, detail):
        results.append(("FAIL", name, detail))

    def warn(name, detail):
        results.append(("WARN", name, detail))

    # 1. Archivos
    missing = [f for f in REQUIRED_FILES if not (folder / f).exists()]
    if missing:
        fail("Archivos obligatorios", f"faltan: {missing}")
        return results, False
    ok("Archivos obligatorios", ", ".join(REQUIRED_FILES))

    meta = load_json(folder / "metadata.json")
    caption = (folder / "caption.md").read_text(encoding="utf-8")
    sources = (folder / "sources.md").read_text(encoding="utf-8")
    spec = load_json(folder / "post.json")

    # 2. Metadatos
    miss_meta = [k for k in REQUIRED_META if not meta.get(k)]
    if miss_meta:
        fail("Metadatos", f"faltan campos: {miss_meta}")
    else:
        ok("Metadatos", "campos obligatorios presentes")

    # 3. Imagen: exactamente una, 1080x1350 PNG
    pngs = list(folder.glob("*.png"))
    with Image.open(folder / "post.png") as im:
        size, fmt = im.size, im.format
    exp = tuple(pub["rules"]["image_size"])
    if size == exp and fmt == "PNG" and len(pngs) == 1:
        ok("Imagen", f"{size[0]}x{size[1]} {fmt}, 1 archivo")
    else:
        fail("Imagen", f"tamaño={size} formato={fmt} pngs={len(pngs)} (se espera 1 PNG {exp})")

    # 4. Canal autorizado
    if meta.get("buffer_channel_id") == chan["channel_id"]:
        ok("Canal Buffer", f"{chan['display_name']} ({chan['channel_id']})")
    else:
        fail("Canal Buffer", f"{meta.get('buffer_channel_id')} != canal autorizado {chan['channel_id']}")

    # 5. Fecha de verificación = hoy (zona del proyecto)
    today = now.astimezone(tz).date().isoformat()
    if meta.get("verified_date") == today and spec.get("verified") == today:
        ok("Verificación del día", today)
    else:
        fail("Verificación del día", f"metadata={meta.get('verified_date')} imagen={spec.get('verified')} hoy={today}")

    # 6. Caption
    maxc = pub["rules"]["caption_max_chars"]
    if len(caption) <= maxc:
        ok("Longitud del texto", f"{len(caption)}/{maxc} caracteres")
    else:
        fail("Longitud del texto", f"{len(caption)} > {maxc}")
    if f"Verificado el: {today}" in caption:
        ok("Fecha visible en el texto", f"Verificado el: {today}")
    else:
        fail("Fecha visible en el texto", f"falta 'Verificado el: {today}'")
    blob = caption + json.dumps(spec, ensure_ascii=False)
    m = PLACEHOLDERS.search(blob)
    if m:
        fail("Marcadores pendientes", m.group(0))
    else:
        ok("Marcadores pendientes", "ninguno")
    if "No verificable" in caption:
        warn("Campos no verificables", "el texto contiene 'No verificable': confirmar que no es un dato crítico")

    urls = sorted(set(u.rstrip(".,;") for u in URL_RE.findall(caption)))
    if not urls:
        fail("Enlaces oficiales", "el texto no contiene enlaces")
    unsourced = [u for u in urls if u not in sources]
    if unsourced:
        fail("Enlaces documentados en sources.md", f"sin fuente: {unsourced}")
    elif urls:
        ok("Enlaces documentados en sources.md", f"{len(urls)} enlaces")
    if canonical_url(meta.get("primary_url", "")) not in {canonical_url(u) for u in urls}:
        fail("Enlace principal en el texto", meta.get("primary_url", ""))
    else:
        ok("Enlace principal en el texto", meta["primary_url"])
    if "tip" in spec and "Lo que pocos explican" in caption:
        ok("Estilo compacto (v2)", "imagen con bloque 'Lo que pocos explican' y dato práctico en el texto")
    else:
        fail("Estilo compacto (v2)", "falta 'tip' en post.json o la línea 'Lo que pocos explican' en caption.md")
    if URL_RE.search(json.dumps(spec, ensure_ascii=False)):
        fail("Sin URLs en la imagen", "post.json contiene una URL completa")
    else:
        ok("Sin URLs en la imagen", "sólo dominio de la fuente")

    # 7. Política de selección (oportunidades publicadas desde 2026-10-29)
    status = meta.get("call_status", "abierta")
    if meta.get("type") == "oportunidad" and meta.get("date", "") >= "2026-10-29":
        if status not in ("abierta", "proxima_confirmada", "recurrente_pendiente"):
            fail("Estado de la convocatoria", f"call_status inválido: {status!r}")
        ev = meta.get("popularity_evidence") or []
        if not ev or any(not e.get("url") or e["url"] not in sources for e in ev):
            fail("Evidencia de popularidad", "falta popularity_evidence con URL documentada en sources.md")
        else:
            ok("Evidencia de popularidad", f"{len(ev)} señales documentadas")
        if not meta.get("audience_fit"):
            fail("Relevancia para la audiencia", "falta audience_fit")
        if "Por qué es conocida" not in caption:
            fail("Por qué es conocida", "el caption debe explicar por qué es conocida")
        if status == "proxima_confirmada":
            opens = meta.get("opens_on")
            if not opens or datetime.fromisoformat(opens).date() <= now.date():
                fail("Próxima apertura", "opens_on ausente o no futura")
            if not re.search(r"aún no está abierta|abre el", caption, re.IGNORECASE):
                fail("Convocatoria futura visible", "el caption debe decir que aún no está abierta")
        if status == "recurrente_pendiente":
            if meta.get("deadline"):
                fail("Convocatoria recurrente", "no se puede afirmar plazo si está pendiente de confirmación")
            if "pendiente de confirmación" not in caption.lower():
                fail("Convocatoria recurrente", "el caption debe decir 'pendiente de confirmación'")

    # 8. Plazo vigente con margen (sólo convocatorias abiertas)
    if meta.get("type") == "oportunidad" and status == "abierta":
        dl = meta.get("deadline")
        if not dl:
            fail("Plazo", "oportunidad sin deadline verificado")
        else:
            d = datetime.fromisoformat(dl)
            margin = timedelta(days=pub["rules"]["min_days_before_deadline"])
            if d - now >= margin:
                ok("Plazo", f"{dl} (quedan {(d - now).days} días)")
            else:
                fail("Plazo", f"{dl}: menos de {margin.days} días o vencido")

    # 9. Duplicados
    hist = read_history()
    cu, tk = canonical_url(meta.get("primary_url", "")), meta.get("topic_key")
    dups = [r for r in hist if r.get("status") in ("published", "scheduled")
            and r.get("folder") != folder.name
            and (canonical_url(r.get("official_url", "")) == cu or r.get("topic_key") == tk)]
    if dups:
        fail("Duplicados", f"ya publicado: {[(r['publication_date'], r['topic']) for r in dups]}")
    else:
        ok("Duplicados", f"sin coincidencias en {len(hist)} filas (URL canónica y topic_key)")

    # 10. Enlaces accesibles
    if skip_network:
        warn("Enlaces accesibles", "omitido (--skip-network)")
    else:
        for u in urls:
            code, info = http_status(u)
            if code is not None and code < 400:
                ok("Enlace accesible", f"{code} {u}")
            elif code in (401, 403, 429):
                warn("Enlace accesible", f"{code} {u}: bloqueo anti-bots; confirmar con WebFetch y anotar en sources.md")
            elif code is None:
                # Sin respuesta HTTP (proxy, DNS o red del entorno): no prueba que el enlace esté roto.
                warn("Enlace accesible", f"sin respuesta desde este entorno ({info}) {u}: confirmar con WebFetch y anotar en sources.md")
            else:
                fail("Enlace accesible", f"{code} {u} {info}")

    passed = not any(r[0] == "FAIL" for r in results)
    return results, passed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--now", help="ISO 8601 con zona; por defecto, ahora")
    ap.add_argument("--skip-network", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(ZoneInfo("Europe/Stockholm"))
    results, passed = validate(folder, now, a.skip_network)
    decision = "APROBADA para publicar" if passed else "BLOQUEADA: no publicar"
    lines = [f"# Validación — {folder.name}", "",
             f"Ejecutado: {now.isoformat(timespec='seconds')}", f"Decisión: **{decision}**", "",
             "| Estado | Comprobación | Detalle |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {d.replace('|', '/')} |" for s, n, d in results]
    (folder / "validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s, n, d in results:
        print(f"[{s}] {n}: {d}")
    print(f"\nDECISIÓN: {decision}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
