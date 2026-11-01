"""Valida el carrusel de Instagram de una publicación (independiente de la validación de LinkedIn).

Uso:
    python3 scripts/validate_carousel.py posts/<carpeta> [--plain-hash] [--skip-linkedin-check]

Entregables en la carpeta: carousel.json, slide-1..5.png, carousel_render.json, caption_instagram.md y
metadata.json con el bloque `instagram` (plain_language_check). Escribe validation_instagram.md.
Decisión APROBADA/BLOQUEADA. `prepare_publish_instagram.py` se niega sin una validación APROBADA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from history import canonical_url, rows_for  # noqa: E402
from render_carousel import N_SLIDES, texts_of  # noqa: E402
from validate_post import (PLAIN_QUESTION, URL_RE, jargon_found, long_sentences, unexplained_acronyms)  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPTION_FILE = "caption_instagram.md"
SIZE = (1080, 1350)


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def digest(caption: str, spec: dict) -> str:
    return hashlib.sha256((caption + "\n" + "\n".join(texts_of(spec))).encode("utf-8")).hexdigest()


def plain_hash(folder: Path) -> str:
    return digest((folder / CAPTION_FILE).read_text(encoding="utf-8"), load_json(folder / "carousel.json"))


def validate(folder: Path, now: datetime, check_linkedin: bool = True) -> tuple[list, bool]:
    pub = load_json(ROOT / "config" / "publishing.json")
    cfg = pub["instagram"]
    results: list[tuple[str, str, str]] = []

    def ok(n, d=""):
        results.append(("PASS", n, d))

    def fail(n, d):
        results.append(("FAIL", n, d))

    def warn(n, d):
        results.append(("WARN", n, d))

    required = ["carousel.json", CAPTION_FILE, "carousel_render.json", "metadata.json"] + \
               [f"slide-{i}.png" for i in range(1, N_SLIDES + 1)]
    missing = [f for f in required if not (folder / f).exists()]
    if missing:
        fail("Archivos obligatorios", f"faltan: {missing}")
        return results, False
    ok("Archivos obligatorios", f"{N_SLIDES} imágenes + caption + carousel.json")

    meta, spec = load_json(folder / "metadata.json"), load_json(folder / "carousel.json")
    caption = (folder / CAPTION_FILE).read_text(encoding="utf-8")

    # LinkedIn: el contenido (datos verificados) sale de la publicación validada de LinkedIn.
    if check_linkedin:
        val = folder / "validation.md"
        if val.exists() and "APROBADA para publicar" in val.read_text(encoding="utf-8"):
            ok("Base verificada (LinkedIn)", "validation.md APROBADA: mismos datos y fuentes oficiales")
        else:
            fail("Base verificada (LinkedIn)", "falta validation.md APROBADA: el carrusel reutiliza esa investigación")

    # Imágenes: tamaño, formato y huellas (no obsoletas)
    render = load_json(folder / "carousel_render.json")
    bad = []
    for i in range(1, N_SLIDES + 1):
        p = folder / f"slide-{i}.png"
        with Image.open(p) as im:
            if im.size != SIZE or im.format != "PNG":
                bad.append(f"slide-{i}: {im.format} {im.size}")
        if render["slides"].get(p.name) != hashlib.sha256(p.read_bytes()).hexdigest():
            bad.append(f"slide-{i}: no coincide con carousel_render.json")
    if bad:
        fail("Imágenes 1080×1350 PNG", "; ".join(bad))
    else:
        ok("Imágenes 1080×1350 PNG", f"{N_SLIDES} imágenes correctas")
    if render.get("carousel_json_sha256") != hashlib.sha256((folder / "carousel.json").read_bytes()).hexdigest():
        fail("Imágenes actualizadas", "carousel.json cambió después de renderizar: ejecuta render_carousel.py")
    else:
        ok("Imágenes actualizadas", "generadas desde el carousel.json actual")

    # Contenido de las imágenes
    img_text = "\n".join(texts_of(spec))
    if URL_RE.search(img_text) or re.search(r"\bwww\.", img_text):
        fail("Imágenes sin URL completa", "usa sólo el dominio (la URL va en el caption)")
    else:
        ok("Imágenes sin URL completa", "sólo dominios")
    if meta.get("verified_date") and spec.get("verified") != meta["verified_date"]:
        fail("Fecha de verificación", f"carousel.json {spec.get('verified')} ≠ metadata {meta['verified_date']}")
    else:
        ok("Fecha de verificación", spec.get("verified", ""))

    # Caption
    n = len(caption.strip())
    if n > cfg["caption_max_chars"]:
        fail("Caption breve", f"{n} caracteres (máx. {cfg['caption_max_chars']})")
    else:
        ok("Caption breve", f"{n} caracteres (máx. {cfg['caption_max_chars']})")
    tags = re.findall(r"#\w+", caption)
    lo, hi = cfg["hashtags"]
    (ok if lo <= len(tags) <= hi else fail)("Hashtags", f"{len(tags)} (rango {lo}-{hi})")
    m = re.search(r"Verificado el:\s*(\d{4}-\d{2}-\d{2})", caption)
    if not m:
        fail("Verificado el", "falta la línea 'Verificado el: AAAA-MM-DD' (la usa la reconciliación con Buffer)")
    elif m.group(1) != meta.get("verified_date"):
        fail("Verificado el", f"{m.group(1)} ≠ metadata.verified_date {meta.get('verified_date')}")
    else:
        ok("Verificado el", m.group(1))
    if URL_RE.search(caption):
        warn("Enlaces en el caption", "en Instagram los enlaces no son clicables: mejor sólo el dominio oficial")
    if re.search(r"TODO|TBD|XXX|lorem ipsum", caption + img_text, re.IGNORECASE):
        fail("Marcadores de posición", "quedan TODO/TBD/XXX")
    if not any(d in caption for d in (spec["source"],)):
        warn("Fuente en el caption", f"el caption no menciona {spec['source']}")

    # Lenguaje sencillo (imagen y texto por separado, como en LinkedIn)
    for where, text in (("texto", caption), ("imagen", img_text)):
        acr = unexplained_acronyms(text)
        (fail if acr else ok)(f"Lenguaje sencillo: siglas ({where})",
                              f"sin explicar: {acr}" if acr else "todas explicadas o ninguna")
        jar = jargon_found(text)
        (fail if jar else ok)(f"Lenguaje sencillo: palabras difíciles ({where})",
                              "; ".join(jar) if jar else "sin burocracia ni calcos detectados")
    longs = long_sentences(caption) + long_sentences(img_text)
    (fail if longs else ok)("Lenguaje sencillo: frases largas", " | ".join(longs[:3]) if longs else "todas ≤ 32 palabras")
    chk = (meta.get("instagram") or {}).get("plain_language_check") or {}
    if not (chk.get("question") == PLAIN_QUESTION and str(chk.get("answer", "")).strip().lower() in ("sí", "si")
            and chk.get("reviewer") and chk.get("checked_text_sha256")):
        fail("Lenguaje sencillo: revisión del verificador",
             "falta metadata.instagram.plain_language_check (pregunta exacta, answer 'sí', reviewer, "
             "checked_text_sha256 = python3 scripts/validate_carousel.py <carpeta> --plain-hash)")
    elif chk["checked_text_sha256"] != digest(caption, spec):
        fail("Lenguaje sencillo: revisión del verificador", "el texto cambió después de la revisión: revisar otra vez")
    else:
        ok("Lenguaje sencillo: revisión del verificador", f"respuesta 'sí' de {chk['reviewer']}")

    # Duplicados: SÓLO en el historial de Instagram (el mismo tema ya está en LinkedIn por diseño)
    cu, tk = canonical_url(meta.get("primary_url", "")), meta.get("topic_key")
    dups = [r for r in rows_for("instagram") if r.get("status") in ("published", "scheduled")
            and r.get("folder") != folder.name
            and (canonical_url(r.get("official_url", "")) == cu or r.get("topic_key") == tk)]
    mine = [r for r in rows_for("instagram") if r.get("folder") == folder.name and r.get("status") in ("published", "scheduled")]
    if dups:
        fail("Duplicados (Instagram)", f"ya publicado en Instagram: {[(r['publication_date'], r['topic']) for r in dups]}")
    elif mine:
        fail("Duplicados (Instagram)", f"esta carpeta ya figura como {mine[0]['status']} en Instagram")
    else:
        ok("Duplicados (Instagram)", f"sin coincidencias en {len(rows_for('instagram'))} filas de Instagram")

    # Verificación de hoy
    tz = ZoneInfo(pub["timezone"])
    vd = meta.get("verified_date")
    if vd == now.astimezone(tz).date().isoformat():
        ok("Verificación de hoy", vd)
    else:
        fail("Verificación de hoy", f"verified_date {vd} ≠ hoy {now.astimezone(tz).date().isoformat()}")

    return results, not any(s == "FAIL" for s, _, _ in results)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--now", help="ISO 8601 con zona; por defecto, ahora")
    ap.add_argument("--plain-hash", action="store_true")
    ap.add_argument("--skip-linkedin-check", action="store_true", help="sólo pruebas")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()
    if a.plain_hash:
        print(plain_hash(folder))
        return 0
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(ZoneInfo("Europe/Stockholm"))
    results, passed = validate(folder, now, not a.skip_linkedin_check)
    decision = "APROBADA para publicar" if passed else "BLOQUEADA: no publicar"
    lines = [f"# Validación Instagram — {folder.name}", "", f"Ejecutado: {now.isoformat(timespec='seconds')}",
             f"Decisión: **{decision}**", "", "| Estado | Comprobación | Detalle |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {d.replace('|', '/')} |" for s, n, d in results]
    (folder / "validation_instagram.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s, n, d in results:
        print(f"[{s}] {n}: {d}")
    print(f"\nDECISIÓN: {decision}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
