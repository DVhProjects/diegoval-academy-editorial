"""Genera el carrusel de Instagram (5 imágenes 1080x1350) de DiegoVal Academy a partir de carousel.json.

Uso:
    python3 scripts/render_carousel.py posts/<carpeta>/carousel.json [--out-dir posts/<carpeta>]

Salida: slide-1.png … slide-5.png y carousel_render.json (huellas sha256 de carousel.json y de cada PNG,
que el validador usa para detectar imágenes obsoletas). Sin IA de pago: Pillow, fuentes OFL de assets/fonts
y la misma paleta que la imagen de LinkedIn (render_post.py). Todo el texto es texto real.

Esquema de carousel.json:
{
  "series": "miercoles | viernes | sabado",
  "kicker": "Guía práctica · Doctorado",           # cabecera de la portada, máx. 40 caracteres
  "cover":  {"title": "¿Buscas un doctorado en Europa?", "highlight": "doctorado",
             "subtitle": "Frase corta que explica de qué va (máx. 110 caracteres)"},
  "slides": [                                       # exactamente 4 (la portada es la imagen 1)
    {"type": "points",  "title": "¿Qué es X?",        "items": [{"icon": "search", "text": "..."}, ... 3]},
    {"type": "steps",   "title": "¿Cómo se hace?",    "items": [{"text": "..."}, ... 3-4]},
    {"type": "tip",     "title": "Un consejo importante", "items": [{"icon": "info", "text": "..."}, ... 2]},
    {"type": "summary", "title": "En resumen",        "items": [{"text": "..."}, ... 3], "cta": "Dónde: dominio.org"}
  ],
  "source": "dominio-oficial.org", "verified": "AAAA-MM-DD"
}
Iconos: check, info, search, doc, calendar, globe, euro, star, arrow. Si el texto no cabe con los tamaños mínimos
legibles el script falla (exit 1) en lugar de recortar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_post import (ACCENTS, H, MARGIN, PALETTE, SANS, SERIF, W, LayoutError, check_glyphs, font,  # noqa: E402
                         tracked, wrap)

ICONS = {"check", "info", "search", "doc", "calendar", "globe", "euro", "star", "arrow"}
SLIDE_TYPES = {"points": (3, 3), "steps": (3, 4), "tip": (2, 2), "summary": (3, 3)}
LIMITS = {"kicker": 40, "cover_title": 62, "cover_subtitle": 110, "title": 38, "item": 120, "cta": 60}
PALE = {k: (253, 226, 128) for k in ("miercoles", "viernes", "sabado")}  # subrayador amarillo para la palabra clave
N_SLIDES = 5


def texts_of(spec: dict) -> list[str]:
    """Textos visibles de las imágenes (para lenguaje sencillo y huella de revisión)."""
    out = [spec.get("kicker", ""), spec["cover"]["title"], spec["cover"].get("subtitle", "")]
    for s in spec["slides"]:
        out.append(s["title"])
        out += [i["text"] for i in s["items"]]
        if s.get("cta"):
            out.append(s["cta"])
    return [t for t in out if t]


def check_spec(spec: dict) -> None:
    if spec.get("series") not in ACCENTS:
        raise LayoutError("series debe ser miercoles, viernes o sabado")
    if len(spec.get("slides", [])) != N_SLIDES - 1:
        raise LayoutError(f"se necesitan exactamente {N_SLIDES - 1} diapositivas además de la portada")
    kinds = [s.get("type") for s in spec["slides"]]
    if kinds != ["points", "steps", "tip", "summary"]:
        raise LayoutError(f"orden de diapositivas obligatorio: points, steps, tip, summary (hay {kinds})")
    cov = spec["cover"]
    if len(spec.get("kicker", "")) > LIMITS["kicker"]:
        raise LayoutError(f"kicker de más de {LIMITS['kicker']} caracteres")
    if len(cov["title"]) > LIMITS["cover_title"] or len(cov.get("subtitle", "")) > LIMITS["cover_subtitle"]:
        raise LayoutError("título o subtítulo de portada demasiado largo")
    if cov.get("highlight") and cov["highlight"] not in cov["title"]:
        raise LayoutError("cover.highlight debe ser una parte literal de cover.title")
    for s in spec["slides"]:
        lo, hi = SLIDE_TYPES[s["type"]]
        if not lo <= len(s["items"]) <= hi:
            raise LayoutError(f"'{s['title']}': {s['type']} admite {lo}-{hi} elementos")
        if len(s["title"]) > LIMITS["title"] or len(s.get("cta", "")) > LIMITS["cta"]:
            raise LayoutError(f"'{s['title']}': título o cta demasiado largo")
        for it in s["items"]:
            if len(it["text"]) > LIMITS["item"]:
                raise LayoutError(f"elemento de más de {LIMITS['item']} caracteres: {it['text'][:40]}…")
            if it.get("icon") and it["icon"] not in ICONS:
                raise LayoutError(f"icono desconocido: {it['icon']}")


# ---------- dibujo ----------
def rounded(draw, box, r, fill, outline=None, width=0):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, r: int, fg, bg) -> None:
    """Icono simple dibujado con primitivas dentro de un círculo de radio r."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg)
    k = r / 30.0
    w = max(3, round(4 * k))
    if kind == "check":
        draw.line([(cx - 13 * k, cy + 1 * k), (cx - 4 * k, cy + 10 * k), (cx + 14 * k, cy - 10 * k)], fill=fg, width=w + 1, joint="curve")
    elif kind == "info":
        draw.ellipse([cx - 3.4 * k, cy - 15 * k, cx + 3.4 * k, cy - 8 * k], fill=fg)
        draw.rounded_rectangle([cx - 3.4 * k, cy - 4 * k, cx + 3.4 * k, cy + 15 * k], radius=2, fill=fg)
    elif kind == "search":
        draw.ellipse([cx - 14 * k, cy - 14 * k, cx + 6 * k, cy + 6 * k], outline=fg, width=w)
        draw.line([(cx + 3 * k, cy + 3 * k), (cx + 15 * k, cy + 15 * k)], fill=fg, width=w + 1)
    elif kind == "doc":
        draw.rounded_rectangle([cx - 11 * k, cy - 15 * k, cx + 11 * k, cy + 15 * k], radius=3, outline=fg, width=w)
        for dy in (-6, 1, 8):
            draw.line([(cx - 6 * k, cy + dy * k), (cx + 6 * k, cy + dy * k)], fill=fg, width=max(2, w - 1))
    elif kind == "calendar":
        draw.rounded_rectangle([cx - 14 * k, cy - 11 * k, cx + 14 * k, cy + 14 * k], radius=3, outline=fg, width=w)
        draw.line([(cx - 14 * k, cy - 3 * k), (cx + 14 * k, cy - 3 * k)], fill=fg, width=w)
        for dx in (-7, 7):
            draw.line([(cx + dx * k, cy - 16 * k), (cx + dx * k, cy - 8 * k)], fill=fg, width=w)
    elif kind == "globe":
        draw.ellipse([cx - 15 * k, cy - 15 * k, cx + 15 * k, cy + 15 * k], outline=fg, width=w)
        draw.ellipse([cx - 7 * k, cy - 15 * k, cx + 7 * k, cy + 15 * k], outline=fg, width=max(2, w - 1))
        draw.line([(cx - 15 * k, cy), (cx + 15 * k, cy)], fill=fg, width=max(2, w - 1))
    elif kind == "euro":
        f = font(SANS, round(34 * k), 650)
        draw.text((cx, cy + 1), "€", font=f, fill=fg, anchor="mm")
    elif kind == "star":
        import math
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rad = (16 if i % 2 == 0 else 7) * k
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        draw.polygon(pts, fill=fg)
    elif kind == "arrow":
        draw.line([(cx - 13 * k, cy), (cx + 12 * k, cy)], fill=fg, width=w + 1)
        draw.line([(cx + 3 * k, cy - 10 * k), (cx + 13 * k, cy), (cx + 3 * k, cy + 10 * k)], fill=fg, width=w + 1, joint="curve")


def number_badge(draw, n: int, cx: int, cy: int, r: int, accent) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    draw.text((cx, cy - 1), str(n), font=font(SANS, round(r * 1.05), 700), fill=PALETTE["white"], anchor="mm")


def header(draw, idx: int, accent) -> None:
    draw.text((MARGIN, 64), "DiegoVal", font=font(SERIF, 34, 680, opsz=36), fill=PALETTE["ink"])
    wd = font(SERIF, 34, 680, opsz=36).getlength("DiegoVal ")
    draw.text((MARGIN + wd, 64), "Academy", font=font(SERIF, 34, 400, opsz=36), fill=PALETTE["ink_soft"])
    pill = font(SANS, 26, 650)
    label = f"{idx}/{N_SLIDES}"
    pw = pill.getlength(label) + 44
    rounded(draw, [W - MARGIN - pw, 58, W - MARGIN, 104], 23, accent)
    draw.text((W - MARGIN - pw / 2, 81), label, font=pill, fill=PALETTE["white"], anchor="mm")
    draw.rectangle([MARGIN, 124, W - MARGIN, 126], fill=PALETTE["ink"])


def footer(draw, spec: dict, accent) -> None:
    y = H - 92
    draw.rectangle([MARGIN, y - 18, W - MARGIN, y - 17], fill=PALETTE["rule"])
    small = font(SANS, 23, 480)
    draw.text((MARGIN, y), f"Fuente oficial: {spec['source']}", font=small, fill=PALETTE["muted"])
    ver = f"Verificado el {spec['verified']}"
    draw.text((W - MARGIN - small.getlength(ver), y), ver, font=small, fill=PALETTE["muted"])


def fit_text(text: str, path: Path, weight: int, sizes: tuple[int, int], width: int, max_lines: int,
             opsz: bool = False):
    """Mayor tamaño (≤ sizes[0], ≥ sizes[1]) con el que el texto cabe en max_lines líneas."""
    for size in range(sizes[0], sizes[1] - 1, -2):
        f = font(path, size, weight, opsz=min(size, 60) if opsz else None)
        try:
            lines = wrap(text, f, width)
        except LayoutError:
            continue
        if len(lines) <= max_lines:
            return f, lines
    raise LayoutError(f"el texto no cabe con tamaño legible (mín. {sizes[1]} px): {text[:50]}…")


def title_block(draw, title: str, y: int, accent) -> int:
    f, lines = fit_text(title, SERIF, 700, (74, 54), W - 2 * MARGIN, 2, opsz=True)
    lh = round(f.size * 1.12)
    for ln in lines:
        draw.text((MARGIN, y), ln, font=f, fill=PALETTE["ink"])
        y += lh
    draw.rectangle([MARGIN, y + 8, MARGIN + 120, y + 14], fill=accent)
    return y + 14


def draw_highlighted(draw, lines, f, y, lh, phrase, accent, pale) -> None:
    """Dibuja líneas de titular con una franja de color tras la frase destacada."""
    for ln in lines:
        x = MARGIN
        if phrase and phrase in ln:
            i = ln.index(phrase)
            x0 = x + f.getlength(ln[:i])
            x1 = x0 + f.getlength(phrase)
            draw.rounded_rectangle([x0 - 8, y + f.size * 0.14, x1 + 8, y + f.size * 1.02], radius=10, fill=pale)
        draw.text((x, y), ln, font=f, fill=PALETTE["ink"])
        y += lh


def cover(spec: dict, accent, pale) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["paper"])
    d = ImageDraw.Draw(img)
    header(d, 1, accent)
    tracked(d, (MARGIN, 168), spec.get("kicker", "").upper(), font(SANS, 24, 650), accent)
    cov = spec["cover"]
    inner = W - 2 * MARGIN
    f, lines = fit_text(cov["title"], SERIF, 720, (112, 70), inner, 4, opsz=True)
    lh = round(f.size * 1.12)
    y = 232
    draw_highlighted(d, lines, f, y, lh, cov.get("highlight"), accent, pale)
    y += lh * len(lines) + 26
    d.rectangle([MARGIN, y, MARGIN + 120, y + 6], fill=accent)
    y += 40
    sf, slines = fit_text(cov.get("subtitle", ""), SANS, 420, (40, 32), inner - 40, 4)
    for ln in slines:
        d.text((MARGIN, y), ln, font=sf, fill=PALETTE["ink_soft"])
        y += round(sf.size * 1.4)
    # Bloque inferior: motivo geométrico + invitación a deslizar
    top = max(y + 60, 800)
    d.rectangle([0, top, W, H], fill=accent)
    for i, (rx, ry, rr) in enumerate([(880, top + 130, 190), (1010, top + 330, 130)]):
        d.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], outline=(255, 255, 255), width=3)
    d.ellipse([880 - 60, top + 130 - 60, 880 + 60, top + 130 + 60], fill=pale)
    tracked(d, (MARGIN, top + 70), "GUÍA EN 5 IMÁGENES", font(SANS, 24, 650), PALETTE["white"])
    d.text((MARGIN, top + 112), "Desliza para verla", font=font(SERIF, 56, 640, opsz=56), fill=PALETTE["white"])
    icon(d, "arrow", MARGIN + 36, top + 232, 36, accent, PALETTE["white"])
    d.text((MARGIN + 94, top + 232), "Guárdala para después", font=font(SANS, 30, 520), fill=PALETTE["white"], anchor="lm")
    d.text((MARGIN, H - 92), f"Fuente oficial: {spec['source']}  ·  Verificado el {spec['verified']}",
           font=font(SANS, 23, 480), fill=(255, 255, 255))
    return img


def content_slide(spec: dict, idx: int, s: dict, accent, pale) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["paper"])
    d = ImageDraw.Draw(img)
    header(d, idx, accent)
    y = title_block(d, s["title"], 168, accent) + 56
    area_bottom = H - 150
    n = len(s["items"])
    kind = s["type"]
    pad_x, icon_r = 32, 38
    text_w = W - 2 * MARGIN - 2 * pad_x - 2 * icon_r - 28
    # Tamaño común para todos los elementos: el mayor con el que todos caben en ≤ 4 líneas.
    cta = s.get("cta") if kind == "summary" else None
    reserve = 150 if cta else 0
    avail = area_bottom - y - reserve
    gap = 26
    for size in range(46, 29, -2):
        f = font(SANS, size, 480)
        try:
            all_lines = [wrap(it["text"], f, text_w) for it in s["items"]]
        except LayoutError:
            continue
        lh = round(size * 1.34)
        heights = [max(2 * icon_r + 44, len(ln) * lh + 52) for ln in all_lines]
        if max(len(ln) for ln in all_lines) <= 4 and sum(heights) + gap * (n - 1) <= avail:
            break
    else:
        raise LayoutError(f"diapositiva '{s['title']}': el texto no cabe con tamaño legible (mín. 30 px)")
    extra = max(0, avail - (sum(heights) + gap * (n - 1)))
    gap += min(extra // max(1, n), 30)  # reparte el espacio sobrante entre tarjetas
    extra = max(0, avail - (sum(heights) + gap * (n - 1)))
    y += min(extra // 2, 90)
    for i, (it, lines, hgt) in enumerate(zip(s["items"], all_lines, heights)):
        rounded(d, [MARGIN, y, W - MARGIN, y + hgt], 26, PALETTE["white"], outline=PALETTE["rule"], width=2)
        d.rounded_rectangle([MARGIN, y, MARGIN + 12, y + hgt], radius=6, fill=accent)
        cx, cy = MARGIN + pad_x + icon_r + 8, y + hgt // 2
        if kind == "steps":
            number_badge(d, i + 1, cx, cy, icon_r, accent)
        elif kind == "summary":
            icon(d, "check", cx, cy, icon_r, PALETTE["white"], (63, 138, 84))
        else:
            default = "info" if kind == "tip" else "star"
            icon(d, it.get("icon") or default, cx, cy, icon_r, PALETTE["white"], accent)
        tx = MARGIN + pad_x + 2 * icon_r + 28 + 8
        ty = y + (hgt - len(lines) * lh) // 2
        for ln in lines:
            d.text((tx, ty), ln, font=f, fill=PALETTE["ink"])
            ty += lh
        y += hgt + gap
    if cta:
        cf, cl = fit_text(cta, SANS, 650, (34, 28), W - 2 * MARGIN - 130, 2)
        box_h = 40 + len(cl) * round(cf.size * 1.3)
        by = area_bottom - box_h - 4
        rounded(d, [MARGIN, by, W - MARGIN, by + box_h], 24, accent)
        icon(d, "globe", MARGIN + 62, by + box_h // 2, 30, accent, PALETTE["white"])
        ty = by + 20
        for ln in cl:
            d.text((MARGIN + 116, ty), ln, font=cf, fill=PALETTE["white"])
            ty += round(cf.size * 1.3)
    footer(d, spec, accent)
    return img


def render(spec: dict) -> list[Image.Image]:
    check_spec(spec)
    check_glyphs({"t": texts_of(spec), "s": spec["source"], "v": spec["verified"]})
    accent, pale = ACCENTS[spec["series"]], PALE[spec["series"]]
    imgs = [cover(spec, accent, pale)]
    for i, s in enumerate(spec["slides"], start=2):
        imgs.append(content_slide(spec, i, s, accent, pale))
    return imgs


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out-dir", type=Path)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    out = (a.out_dir or a.spec.parent).resolve()
    try:
        imgs = render(spec)
    except (LayoutError, KeyError) as e:
        print(f"ERROR de diseño: {e}", file=sys.stderr)
        return 1
    files = {}
    for i, im in enumerate(imgs, start=1):
        p = out / f"slide-{i}.png"
        im.save(p, "PNG", optimize=True)
        files[p.name] = sha256_file(p)
    (out / "carousel_render.json").write_text(json.dumps(
        {"carousel_json_sha256": sha256_file(a.spec.resolve()), "size": [W, H], "slides": files},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(imgs)} imágenes {W}x{H} en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
