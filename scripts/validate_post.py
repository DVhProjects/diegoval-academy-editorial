"""Valida una carpeta de publicación antes de enviarla a Buffer.

Uso:
    python scripts/validate_post.py posts/<carpeta> [--now 2026-10-27T16:40:00+01:00] [--skip-network]

Escribe posts/<carpeta>/validation.md y termina con código 0 sólo si TODAS las
comprobaciones bloqueantes pasan. Los avisos (WARN) deben resolverse a mano y
documentarse en sources.md antes de publicar.
"""
from __future__ import annotations

import argparse
import hashlib
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
import video as videomod  # noqa: E402

REQUIRED_FILES = ["post.json", "post.png", "caption.md", "sources.md", "metadata.json"]
REQUIRED_FILES_VIDEO = ["caption.md", "sources.md", "metadata.json"]
VIDEO_KEYS = ["url", "title", "channel", "channel_id", "published", "subtitles", "official_evidence_url"]
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


SUBTITLE_PHRASES = {
    "es_oficial": ["subtítulos en español"],
    "es_automatico": ["automáticos en español"],
    "traducible": ["traducción automática", "no está garantizada"],
    "no_verificado": ["no verificados"],
}
FORBIDDEN_PROMISES = ["tiene subtítulos en español", "con subtítulos en español", "subtitulado al español",
                      "subtitulado en español"]


def _validate_video(meta, caption, sources, now, skip_network, ok, fail, warn):
    v = meta.get("video") or {}
    miss = [k for k in VIDEO_KEYS if v.get(k) in (None, "")]
    if miss:
        fail("Datos del vídeo", f"faltan en metadata.video: {miss}")
        return
    vid = videomod.video_id(v["url"])
    if not vid:
        fail("Vídeo", f"URL no reconocida como vídeo de YouTube: {v['url']}")
        return
    ok("Vídeo", f"{v['channel']} · {v['title']} ({vid})")
    low = caption.lower()
    if vid in caption:
        ok("Enlace del vídeo en el texto", "respaldo si la tarjeta no se muestra")
    else:
        fail("Enlace del vídeo en el texto", "el caption debe incluir el enlace del vídeo")
    if v["official_evidence_url"] in sources:
        ok("Procedencia oficial documentada", v["official_evidence_url"])
    else:
        fail("Procedencia oficial documentada",
             "official_evidence_url debe figurar en sources.md (página oficial que enlaza o incrusta el vídeo o su canal)")
    info = {"duration_s": v.get("duration_s"), "published": v["published"], "title": v["title"], "channel_id": v["channel_id"]}
    unknown_ok = v.get("duration_s") is None and v.get("language") == "es"
    why = videomod.quality(info, now.date(), allow_unknown_duration=unknown_ok)
    if why:
        fail("Calidad del vídeo", "; ".join(why))
    elif v.get("duration_s") is None:
        warn("Calidad del vídeo", f"duración no verificada (modo limitado de la nube; sólo se admite en vídeos en español); publicado {v['published']}")
    else:
        ok("Calidad del vídeo", f"{v['duration_s']} s, publicado {v['published']}")
    state = v["subtitles"]
    if state not in videomod.SUBTITLE_STATES:
        fail("Subtítulos", f"estado inválido: {state!r}")
    elif state == "no_verificado" and v.get("language") != "es":
        fail("Utilidad para la audiencia",
             "vídeo sin subtítulos verificables y sin declarar language 'es': para hispanohablantes aporta más la imagen v2")
    else:
        missing = [p for p in SUBTITLE_PHRASES[state] if p not in low]
        promised = [p for p in FORBIDDEN_PROMISES if p in low] if state in ("traducible", "no_verificado") else []
        if "subtítulos:" not in low:
            fail("Subtítulos en el texto", "falta la línea 'Subtítulos:'")
        elif missing or promised:
            fail("Subtítulos en el texto",
                 f"el texto no coincide con el estado {state}: faltan {missing}, promesas indebidas {promised}")
        else:
            ok("Subtítulos en el texto", f"coherente con el estado {state}")
    for section in ("qué aprenderás", "por qué es útil", "cómo aprovecharlo"):
        if section not in low:
            fail("Estructura del texto (vídeo)", f"falta la sección '{section}'")
            break
    else:
        ok("Estructura del texto (vídeo)", "qué aprenderás · por qué es útil · cómo aprovecharlo")
    if skip_network:
        warn("Vídeo en vivo", "omitido (--skip-network)")
        return
    live = videomod.inspect(v["url"], now.date())
    if live["errors"] or not live.get("title"):
        if state != "no_verificado":
            fail("Vídeo en vivo", f"no se pudo comprobar ({live['errors']}); no se promete ningún subtítulo sin comprobarlo")
        else:
            warn("Vídeo en vivo", f"no se pudo comprobar: {live['errors']}")
        return
    problems = []
    if live.get("channel_id") and live["channel_id"] != v["channel_id"]:
        problems.append(f"canal {live['channel_id']} distinto de {v['channel_id']}")
    if (live.get("title") or "").strip() != v["title"].strip():
        problems.append("el título publicado ha cambiado")
    if live.get("published") and live["published"] != v["published"]:
        problems.append(f"fecha publicada {live['published']} distinta de {v['published']}")
    if live.get("source") == "feed":
        # Modo limitado: no se puede comprobar duración ni subtítulos; no se admite prometer nada.
        if state != "no_verificado":
            problems.append(f"subtítulos '{state}' no comprobables desde este entorno (sólo RSS/oEmbed)")
        if v.get("duration_s") is not None:
            problems.append("duración declarada pero no comprobable desde este entorno")
        if v.get("language") != "es":
            problems.append("sin acceso a la página del vídeo sólo se admiten vídeos en español")
    else:
        if live.get("subtitles") != state:
            problems.append(f"subtítulos en vivo '{live.get('subtitles')}' distintos de los declarados '{state}'")
        if live.get("quality_problems"):
            problems.append("; ".join(live["quality_problems"]))
    if problems:
        fail("Vídeo en vivo", " | ".join(problems))
    else:
        ok("Vídeo en vivo", f"coincide con lo declarado ({live['subtitles']})")


# Lenguaje sencillo (obligatorio desde 2026-10-31): el lector nunca ha pedido una beca ni un doctorado.
PLAIN_QUESTION = ("¿Una persona que nunca ha solicitado una beca ni un doctorado entendería este texto "
                  "sin buscar explicaciones adicionales?")
# Siglas o códigos: 2+ mayúsculas seguidas (MSCA, UE), mayúscula + cifra (R1) o PhD.
ACRONYM_RE = re.compile(r"(?<![\w#@/.-])(?:[A-ZÁÉÍÓÚÑ]{2,}[0-9]*|[A-Z][0-9]+|PhD)(?![\w-])")
# Siglas que cualquier lector hispanohablante entiende sin explicación.
# CC: botón de subtítulos de YouTube, ya explicado en la línea obligatoria "Subtítulos:".
ACRONYMS_OK = {"CV", "PDF", "DNI", "TV", "CC"}
# Lenguaje burocrático o calcos del inglés que confunden a un principiante (sustituir por la sugerencia).
JARGON = {
    "elegibilidad": "explica quién puede pedirla ('pueden pedirla…')",
    "elegible": "di 'puedes pedirla si…'",
    "estancia de movilidad": "di 'tiempo viviendo en otro país'",
    "regla de movilidad": "explica la regla con palabras simples",
    "investigador en etapa inicial": "di 'persona que empieza a investigar (antes del doctorado)'",
    "aplicar a": "di 'solicitar' o 'pedir' (calco de 'apply')",
    "aplicar para": "di 'solicitar'",
    "aplica a": "di 'solicita' o 'pide'",
    "postulante": "di 'quien la solicita'",
    "a tal efecto": "frase burocrática",
    "en virtud de": "frase burocrática",
    "dicha convocatoria": "frase burocrática",
    "con carácter": "frase burocrática",
    "acreditar": "di 'demostrar' o 'presentar un documento'",
    "partenariado": "di 'grupo de universidades'",
    "consorcio": "explica 'grupo de universidades o centros'",
    "full-time": "di 'a tiempo completo'",
    "deadline": "di 'plazo' o 'fecha límite'",
    "networking": "explica qué hay que hacer",
    "track record": "explica qué se pide",
    "puestos de acogida": "explica con palabras simples",
}


def _strip_noise(text: str) -> str:
    """Quita URLs, hashtags y la línea 'Verificado el' antes de analizar el lenguaje."""
    text = URL_RE.sub(" ", text)
    text = re.sub(r"#\w+", " ", text)
    return re.sub(r"Verificado el:.*", " ", text)


def unexplained_acronyms(text: str) -> list[str]:
    """Siglas sin explicar. Cuenta como explicada si alguna aparición lleva la explicación entre paréntesis
    ('MSCA (becas Marie Curie)') o va entre paréntesis tras ella ('becas Marie Curie (MSCA)')."""
    clean = _strip_noise(text)
    bad = []
    for acr in dict.fromkeys(ACRONYM_RE.findall(clean)):
        if acr in ACRONYMS_OK:
            continue
        a = re.escape(acr)
        explained = (re.search(rf"(?<!\w){a}\s*\(\s*[^)]*[a-záéíóúñ]{{3}}[^)]*\)", clean)
                     or re.search(rf"[a-záéíóúñ]{{3}}[^()\n]*\(\s*{a}\s*\)", clean))
        if not explained:
            bad.append(acr)
    return bad


def jargon_found(text: str) -> list[str]:
    low = _strip_noise(text).lower()
    return [f"'{k}' → {v}" for k, v in JARGON.items() if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", low)]


def long_sentences(text: str, limit: int = 32) -> list[str]:
    out = []
    for s in re.split(r"(?<=[.!?:])\s+|\n+", _strip_noise(text)):
        n = len(re.findall(r"\w+", s))
        if n > limit:
            out.append(f"{n} palabras: «{s.strip()[:60]}…»")
    return out


def _spec_texts(spec) -> list[str]:
    """Textos visibles de la imagen (sin 'source', 'verified', 'series' ni 'issue')."""
    out = []

    def walk(v, key=""):
        if key in ("source", "verified", "series", "issue"):
            return
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str):
            out.append(v)
    walk(spec)
    return out


def _plain_digest(caption: str, spec) -> str:
    return hashlib.sha256((caption + "\n" + "\n".join(_spec_texts(spec))).encode("utf-8")).hexdigest()


def plain_hash(folder: Path) -> str:
    spec = load_json(folder / "post.json") if (folder / "post.json").exists() else {}
    return _plain_digest((folder / "caption.md").read_text(encoding="utf-8"), spec)


def _validate_plain_language(meta, caption, spec, ok, fail):
    image_text = "\n".join(_spec_texts(spec))
    for where, text in (("texto", caption), ("imagen", image_text)):
        if not text.strip():
            continue
        acr = unexplained_acronyms(text)
        if acr:
            fail(f"Lenguaje sencillo: siglas ({where})",
                 f"sin explicar: {acr}. Explícalas la primera vez, p. ej. 'MSCA (becas Marie Curie de la UE)', o quítalas")
        else:
            ok(f"Lenguaje sencillo: siglas ({where})", "todas explicadas o ninguna")
        jar = jargon_found(text)
        if jar:
            fail(f"Lenguaje sencillo: palabras difíciles ({where})", "; ".join(jar))
        else:
            ok(f"Lenguaje sencillo: palabras difíciles ({where})", "sin burocracia ni calcos detectados")
    longs = long_sentences(caption)
    if longs:
        fail("Lenguaje sencillo: frases largas", "parte estas frases (máx. 32 palabras): " + " | ".join(longs[:3]))
    else:
        ok("Lenguaje sencillo: frases largas", "todas ≤ 32 palabras")
    chk = meta.get("plain_language_check") or {}
    if not (chk.get("question") == PLAIN_QUESTION and str(chk.get("answer", "")).strip().lower() in ("sí", "si")
            and chk.get("reviewer") and chk.get("checked_text_sha256")):
        fail("Lenguaje sencillo: revisión del verificador",
             "falta metadata.plain_language_check con la pregunta exacta, answer 'sí', reviewer y "
             "checked_text_sha256 (python3 scripts/validate_post.py <carpeta> --plain-hash)")
    elif chk["checked_text_sha256"] != _plain_digest(caption, spec):
        fail("Lenguaje sencillo: revisión del verificador",
             "el texto cambió después de la revisión: el verificador debe revisarlo otra vez")
    else:
        ok("Lenguaje sencillo: revisión del verificador", f"respuesta 'sí' de {chk['reviewer']}")


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

    # 1. Archivos (el formato lo decide metadata.json: "image" por defecto o "video")
    if not (folder / "metadata.json").exists():
        fail("Archivos obligatorios", "falta metadata.json")
        return results, False
    meta = load_json(folder / "metadata.json")
    is_video = meta.get("format") == "video"
    required = REQUIRED_FILES_VIDEO if is_video else REQUIRED_FILES
    missing = [f for f in required if not (folder / f).exists()]
    if missing:
        fail("Archivos obligatorios", f"faltan: {missing}")
        return results, False
    ok("Archivos obligatorios", f"{'vídeo' if is_video else 'imagen'}: " + ", ".join(required))

    caption = (folder / "caption.md").read_text(encoding="utf-8")
    sources = (folder / "sources.md").read_text(encoding="utf-8")
    spec = {} if is_video else load_json(folder / "post.json")

    # 2. Metadatos
    miss_meta = [k for k in REQUIRED_META if not meta.get(k)]
    if miss_meta:
        fail("Metadatos", f"faltan campos: {miss_meta}")
    else:
        ok("Metadatos", "campos obligatorios presentes")

    # 3. Imagen: exactamente una, 1080x1350 PNG (el formato vídeo no lleva imagen propia)
    if is_video:
        if list(folder.glob("*.png")):
            fail("Sin imagen propia", "el formato vídeo no debe incluir PNG (la miniatura la pone el enlace)")
        else:
            ok("Sin imagen propia", "formato vídeo: la vista previa la genera el enlace")
    else:
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
    if meta.get("verified_date") == today and (is_video or spec.get("verified") == today):
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
    if is_video:
        _validate_video(meta, caption, sources, now, skip_network, ok, fail, warn)
    else:
        # "Lo que pocos explican" es opcional (sólo si hay un consejo realmente útil), pero coherente.
        if ("tip" in spec) == ("Lo que pocos explican" in caption):
            ok("Lo que pocos explican", "presente en imagen y texto" if "tip" in spec else "omitido (sin consejo útil)")
        else:
            fail("Lo que pocos explican", "debe estar en post.json ('tip') y en caption.md a la vez, o en ninguno")
        if URL_RE.search(json.dumps(spec, ensure_ascii=False)):
            fail("Sin URLs en la imagen", "post.json contiene una URL completa")
        else:
            ok("Sin URLs en la imagen", "sólo dominio de la fuente")

    # 6b. Lenguaje sencillo (todos los formatos y días)
    _validate_plain_language(meta, caption, spec, ok, fail)

    # 6c. Tipo coherente con el calendario
    # "variado" (lunes) no es un tipo: el post usa uno de los tipos de los demás días.
    types = {c["type"] for c in pub.get("calendar", {}).values() if c["type"] != "variado"}
    if meta.get("type") not in types:
        fail("Tipo de publicación", f"type {meta.get('type')!r} no está en el calendario {sorted(types)}")
    elif meta.get("type") == "educativo" and meta.get("category") not in pub["rules"].get("saturday_categories", []):
        fail("Categoría del sábado", f"category {meta.get('category')!r} no está en {pub['rules'].get('saturday_categories')}")

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
    vid = videomod.video_id((meta.get("video") or {}).get("url", "")) if is_video else None
    dups = [r for r in hist if r.get("status") in ("published", "scheduled")
            and r.get("folder") != folder.name
            and (canonical_url(r.get("official_url", "")) == cu or r.get("topic_key") == tk
                 or (vid and videomod.video_id(r.get("video_url", "")) == vid))]
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
    ap.add_argument("--plain-hash", action="store_true",
                    help="imprime el hash del texto revisado (caption + imagen) para metadata.plain_language_check")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()
    if a.plain_hash:
        print(plain_hash(folder))
        return 0
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
