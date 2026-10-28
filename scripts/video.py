"""Formato vídeo: inspección y descubrimiento de vídeos (sólo enlaces; nunca se descarga ni se republica nada).

Uso:
    python3 scripts/video.py inspect <url_youtube>
    python3 scripts/video.py feed <@canal|UCxxxxxxxxxxxxxxxxxxxxxx> [--limit 15]

`inspect` lee el oEmbed público y los metadatos de la página pública del vídeo y devuelve JSON con
título, canal, miniatura, duración, fecha de publicación, estado de subtítulos y si cumple los
criterios de calidad. `feed` lista los últimos vídeos de un canal con su RSS público.

Desde la nube de Claude, YouTube bloquea la página del vídeo (HTTP 429) pero sirven el oEmbed y el RSS del
canal. En ese caso `inspect` devuelve source="feed": título, canal, miniatura, fecha y descripción verificados,
pero duración desconocida y subtítulos "no_verificado" (nunca se inventan).

Estados de subtítulos (nunca se promete más de lo que se detecta):
  es_oficial      pista de subtítulos en español subida por el canal
  es_automatico   subtítulos automáticos en español (ASR)
  traducible      hay subtítulos en otro idioma y YouTube ofrece traducción automática (no garantizada)
  no_verificado   no se detecta nada o no se pudo comprobar
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; DiegoValAcademy-VideoCheck/1.0)", "Accept-Language": "en"}
MIN_SECONDS, MAX_SECONDS, MAX_AGE_DAYS = 90, 1200, 730
SUBTITLE_STATES = ("es_oficial", "es_automatico", "traducible", "no_verificado")
ATOM = {"a": "http://www.w3.org/2005/Atom", "y": "http://www.youtube.com/xml/schemas/2015",
        "m": "http://search.yahoo.com/mrss/"}


def http_get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def video_id(url: str) -> str | None:
    p = urllib.parse.urlsplit((url or "").strip())
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        vid = p.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        if p.path == "/watch":
            vid = urllib.parse.parse_qs(p.query).get("v", [""])[0]
        else:
            m = re.match(r"^/(?:shorts|embed|live|v)/([\w-]{11})", p.path)
            vid = m.group(1) if m else ""
    else:
        return None
    return vid if re.fullmatch(r"[\w-]{11}", vid or "") else None


def canonical_video_url(url: str) -> str | None:
    vid = video_id(url)
    return f"https://www.youtube.com/watch?v={vid}" if vid else None


def parse_watch_page(html: str) -> dict:
    """Extrae del HTML público: pistas de subtítulos, traducibilidad, duración, canal y fecha."""
    tracks: list[dict] = []
    m = re.search(r'"captionTracks":(\[.*?\]),"audioTracks"', html, re.S)
    if m:
        try:
            tracks = [{"languageCode": t.get("languageCode", ""), "kind": t.get("kind", "")} for t in json.loads(m.group(1))]
        except (ValueError, TypeError):
            tracks = [{"languageCode": lc, "kind": ""} for lc in re.findall(r'"languageCode":"([\w-]+)"', m.group(1))]
    length = re.search(r'"lengthSeconds":"(\d+)"', html)
    chan = re.search(r'"channelId":"(UC[\w-]{22})"', html)
    author = re.search(r'"author":"((?:[^"\\]|\\.)*)"', html)
    pub = re.search(r'"publishDate":"(\d{4}-\d{2}-\d{2})', html) or re.search(r'"uploadDate":"(\d{4}-\d{2}-\d{2})', html)
    return {
        "tracks": tracks,
        "translatable": '"isTranslatable":true' in html,
        "duration_s": int(length.group(1)) if length else None,
        "channel_id": chan.group(1) if chan else None,
        "author": json.loads(f'"{author.group(1)}"') if author else None,
        "published": pub.group(1) if pub else None,
    }


def classify_subtitles(tracks: list[dict], translatable: bool) -> tuple[str, str]:
    es = [t for t in tracks if t["languageCode"].lower().startswith("es")]
    if any(t.get("kind") != "asr" for t in es):
        return "es_oficial", "pista de subtítulos en español (no automática)"
    if es:
        return "es_automatico", "subtítulos automáticos en español"
    if tracks and translatable:
        langs = sorted({t["languageCode"] for t in tracks})
        return "traducible", f"subtítulos en {', '.join(langs)} y traducción automática ofrecida por YouTube"
    return "no_verificado", "no se detectan subtítulos en español ni traducción"


def quality(info: dict, today: date, allow_unknown_duration: bool = False) -> list[str]:
    """Motivos por los que el vídeo NO cumple los criterios de calidad (lista vacía = cumple)."""
    why = []
    d = info.get("duration_s")
    if d is None:
        if not allow_unknown_duration:
            why.append("duración desconocida")
    elif not MIN_SECONDS <= d <= MAX_SECONDS:
        why.append(f"duración {d}s fuera de {MIN_SECONDS}-{MAX_SECONDS}s")
    pub = info.get("published")
    if not pub:
        why.append("fecha de publicación desconocida")
    else:
        age = (today - date.fromisoformat(pub)).days
        if age > MAX_AGE_DAYS:
            why.append(f"antigüedad {age} días > {MAX_AGE_DAYS}")
        if age < 0:
            why.append("fecha de publicación futura")
    if not info.get("title"):
        why.append("sin título")
    elif re.search(r"#shorts?\b", info["title"], re.I):
        why.append("es un Short")
    if not info.get("channel_id"):
        why.append("canal no identificado")
    return why


def inspect(url: str, today: date | None = None, fetch=http_get) -> dict:
    today = today or date.today()
    canon = canonical_video_url(url)
    out: dict = {"url": canon or url, "ok": False, "errors": []}
    if not canon:
        out["errors"].append("URL no reconocida como vídeo de YouTube")
        return out
    try:
        oe = json.loads(fetch("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(canon, safe="")))
        out.update(title=oe.get("title"), channel=oe.get("author_name"), thumbnail=oe.get("thumbnail_url"))
    except Exception as e:  # vídeo privado/eliminado/no incrustable, red
        out["errors"].append(f"oEmbed: {type(e).__name__}: {e}")
        return out
    out["source"] = "page"
    try:
        page = parse_watch_page(fetch(canon))
        if page["duration_s"] is None:
            # A veces YouTube responde 200 con una página de consentimiento o sin datos del reproductor.
            raise ValueError("la página no trae datos del reproductor (consentimiento o bloqueo)")
        status, why = classify_subtitles(page["tracks"], page["translatable"])
        out.update(duration_s=page["duration_s"], channel_id=page["channel_id"], published=page["published"],
                   subtitles=status, subtitles_detail=why, caption_languages=sorted({t["languageCode"] for t in page["tracks"]}))
    except Exception as e:
        # Página no disponible (típico en la nube: 429). Alternativa: RSS del canal (fecha y descripción reales).
        out["notes"] = [f"página: {type(e).__name__}: {e}"]
        out.update(source="feed", duration_s=None, subtitles="no_verificado",
                   subtitles_detail="página del vídeo no disponible desde este entorno: duración y subtítulos sin comprobar")
        try:
            handle = (oe.get("author_url") or "").rstrip("/").rsplit("/", 1)[-1]
            cid = channel_id_of(handle, fetch)
            rows = feed(cid, 50, fetch)
            if rows and out.get("channel") and rows[0]["channel"].strip() != out["channel"].strip():
                raise ValueError(f"el RSS es del canal '{rows[0]['channel']}', no de '{out['channel']}'")
            entry = next((r for r in rows if r["id"] == canon.rsplit("=", 1)[-1]), None)
            if entry:
                out.update(channel_id=cid, published=entry["published"], description=entry.get("description", ""))
            else:
                out["errors"].append("el vídeo no figura en el RSS reciente del canal: no se puede comprobar su fecha")
        except Exception as e2:
            out["errors"].append(f"RSS: {type(e2).__name__}: {e2}")
    out["quality_problems"] = quality(out, today, allow_unknown_duration=out["source"] == "feed")
    out["ok"] = not out["errors"] and not out["quality_problems"]
    return out


def channel_id_of(channel: str, fetch=http_get) -> str:
    if re.fullmatch(r"UC[\w-]{22}", channel):
        return channel
    handle = channel if channel.startswith("@") else "@" + channel
    html = fetch(f"https://www.youtube.com/{handle}")
    # Orden de fiabilidad: enlace canónico y RSS del propio canal; el primer "channelId" de la página puede ser de otro
    # canal (barras laterales, vídeos recomendados) y sólo se usa como último recurso.
    for pattern in (r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                    r"channel_id=(UC[\w-]{22})", r'"externalId":"(UC[\w-]{22})"', r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    raise ValueError(f"no se pudo resolver el canal {channel}")


def feed(channel: str, limit: int = 15, fetch=http_get) -> list[dict]:
    root = ET.fromstring(fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id_of(channel, fetch)))
    chan = root.find("a:title", ATOM).text
    rows = []
    for e in root.findall("a:entry", ATOM)[:limit]:
        vid = e.find("y:videoId", ATOM).text
        desc = e.find("m:group/m:description", ATOM)
        rows.append({"channel": chan, "published": e.find("a:published", ATOM).text[:10], "id": vid,
                     "title": e.find("a:title", ATOM).text, "url": f"https://www.youtube.com/watch?v={vid}",
                     "description": (desc.text or "")[:400] if desc is not None else ""})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("url")
    f = sub.add_parser("feed")
    f.add_argument("channel")
    f.add_argument("--limit", type=int, default=15)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if a.cmd == "inspect":
            info = inspect(a.url, datetime.now().date())
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0 if info["ok"] else 1
        for r in feed(a.channel, a.limit):
            print(f"{r['published']} {r['url']} {r['title']}")
        return 0
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
