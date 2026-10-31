"""Genera la imagen editorial 1080x1350 de DiegoVal Academy a partir de post.json.

Uso:
    python scripts/render_post.py posts/<carpeta>/post.json [--out ruta.png]

Todo el texto se dibuja como texto real con fuentes OFL incluidas en assets/fonts.
Si el contenido no cabe con los tamaños mínimos legibles, el script falla (exit 1)
en lugar de recortar o encoger el texto por debajo del mínimo.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"
SERIF = FONTS / "SourceSerif4.ttf"
SANS = FONTS / "Inter.ttf"

W, H = 1080, 1350
MARGIN = 84

PALETTE = {
    "paper": (246, 242, 235),
    "ink": (27, 36, 51),
    "ink_soft": (70, 78, 94),
    "muted": (112, 117, 128),
    "rule": (214, 206, 192),
    "white": (255, 255, 255),
}
ACCENTS = {
    "miercoles": (171, 66, 40),   # terracota: oportunidades
    "viernes": (36, 92, 108),     # azul petróleo: research & career
    "sabado": (84, 104, 58),      # verde oliva: guías prácticas
}

# Tamaños: (inicial, mínimo legible) en px sobre el lienzo de 1080 px.
SIZES = {
    "headline": (74, 54),
    "dek": (33, 28),
    "highlight_value": (46, 36),
    "fact_value": (31, 27),
    "action_text": (29, 26),
}
# Plantilla v2 (compacta, desde 2026-10-28): se activa cuando post.json trae "tip".
# Menos elementos y letra más grande: titular, entradilla corta, plazo/dato clave,
# 2-3 datos y el bloque "Lo que pocos explican".
SIZES_V2 = {
    "headline": (84, 62),
    "dek": (35, 30),
    "highlight_value": (58, 44),
    "fact_value": (34, 29),
    "action_text": (32, 28),  # texto del bloque "tip"
}
MAX_GAP_EXTRA = 34  # espacio sobrante que se reparte entre secciones (px por hueco)
LABEL_SIZE = 21
MIN_ANY = 21  # ningún texto por debajo de este tamaño


def font(path: Path, size: int, weight: int, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    axes = f.get_variation_axes()
    values = []
    for ax in axes:
        name = ax["name"].decode() if isinstance(ax["name"], bytes) else ax["name"]
        if name.lower().startswith("weight"):
            values.append(weight)
        elif name.lower().startswith("optical"):
            v = opsz if opsz is not None else size
            values.append(max(ax["minimum"], min(ax["maximum"], v)))
        else:
            values.append(ax["default"])
    f.set_variation_by_axes(values)
    return f


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        # Sólo se corta en espacios normales: los espacios duros (U+00A0) mantienen unidas cifras y unidades.
        words = [w for w in para.split(" ") if w]
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if f.getlength(trial) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    for ln in lines:
        if f.getlength(ln) > width:
            raise LayoutError(f"Palabra demasiado larga para el ancho disponible: {ln!r}")
    return lines


class LayoutError(Exception):
    pass


def tracked(draw: ImageDraw.ImageDraw, xy, text: str, f, fill, tracking: float = 1.6) -> int:
    """Dibuja versalitas espaciadas; devuelve el ancho total."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + tracking
    return int(x - xy[0])


def tracked_len(text: str, f, tracking: float = 1.6) -> float:
    return sum(f.getlength(ch) + tracking for ch in text)


@dataclass
class Fonts:
    headline: ImageFont.FreeTypeFont
    dek: ImageFont.FreeTypeFont
    label: ImageFont.FreeTypeFont
    highlight_value: ImageFont.FreeTypeFont
    fact_value: ImageFont.FreeTypeFont
    action_text: ImageFont.FreeTypeFont
    brand: ImageFont.FreeTypeFont
    small: ImageFont.FreeTypeFont
    sizes: dict


def make_fonts(scale: float, sizes: dict = SIZES) -> Fonts:
    s = {k: max(lo, round(hi * scale)) for k, (hi, lo) in sizes.items()}
    return Fonts(
        headline=font(SERIF, s["headline"], 640, opsz=60),
        dek=font(SANS, s["dek"], 400),
        label=font(SANS, LABEL_SIZE, 640),
        highlight_value=font(SERIF, s["highlight_value"], 650, opsz=48),
        fact_value=font(SANS, s["fact_value"], 520),
        action_text=font(SANS, s["action_text"], 420),
        brand=font(SERIF, 27, 600, opsz=28),
        small=font(SANS, 21, 450),
        sizes=s,
    )


def check_glyphs(spec: dict) -> None:
    """Falla si algún carácter no existe en las fuentes (evita cuadros vacíos)."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:  # fontTools es opcional; se avisa pero no se bloquea
        print("AVISO: fontTools no disponible; no se comprobó la cobertura de glifos.")
        return
    text = json.dumps(spec, ensure_ascii=False)
    for path in (SERIF, SANS):
        cmap = TTFont(str(path)).getBestCmap()
        missing = sorted({ch for ch in text if ch.isprintable() and ord(ch) not in cmap})
        if missing:
            raise LayoutError(f"Caracteres sin glifo en {path.name}: {missing}")


def layout(spec: dict, F: Fonts, accent, draw: ImageDraw.ImageDraw | None):
    """Calcula (y dibuja si draw no es None) el diseño. Devuelve la y final del contenido."""
    inner = W - 2 * MARGIN
    ink, soft, muted, rule = PALETTE["ink"], PALETTE["ink_soft"], PALETTE["muted"], PALETTE["rule"]

    # Cabecera: categoría + marca + filete
    y = 70
    if draw:
        tracked(draw, (MARGIN, y + 4), spec["kicker"].upper(), F.label, accent)
        brand = "DiegoVal Academy"
        draw.text((W - MARGIN - F.brand.getlength(brand), y - 2), brand, font=F.brand, fill=ink)
    y += 50
    if draw:
        draw.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=ink)
    if spec.get("issue"):
        y += 16
        if draw:
            tracked(draw, (MARGIN, y), spec["issue"].upper(), F.small, muted, tracking=1.0)
    y += 44

    # Titular
    hl = F.headline
    lh = round(hl.size * 1.1)
    lines = wrap(spec["headline"], hl, inner)
    if len(lines) > 4:
        raise LayoutError("Titular de más de 4 líneas")
    for ln in lines:
        if draw:
            draw.text((MARGIN, y), ln, font=hl, fill=ink)
        y += lh
    y += 34

    # Entradilla
    dk = F.dek
    lh = round(dk.size * 1.38)
    lines = wrap(spec["dek"], dk, inner)
    if len(lines) > 4:
        raise LayoutError("Entradilla de más de 4 líneas")
    for ln in lines:
        if draw:
            draw.text((MARGIN, y), ln, font=dk, fill=soft)
        y += lh
    y += 30

    # Bloque destacado (plazo o dato clave)
    hlg = spec.get("highlight")
    if hlg:
        pad = 28
        hv = F.highlight_value
        vlines = wrap(hlg["value"], hv, inner - 2 * pad)
        if len(vlines) > 2:
            raise LayoutError("Valor destacado de más de 2 líneas")
        vlh = round(hv.size * 1.15)
        box_h = pad + 30 + len(vlines) * vlh + (44 if hlg.get("note") else 0) + pad - 6
        if draw:
            draw.rectangle([MARGIN, y, W - MARGIN, y + box_h], fill=accent)
            tracked(draw, (MARGIN + pad, y + pad - 2), hlg["label"].upper(), F.label, PALETTE["white"])
            yy = y + pad + 32
            for ln in vlines:
                draw.text((MARGIN + pad, yy), ln, font=hv, fill=PALETTE["white"])
                yy += vlh
            if hlg.get("note"):
                draw.text((MARGIN + pad, yy + 10), hlg["note"], font=F.small, fill=PALETTE["white"])
        y += box_h + 26

    # Datos clave
    facts = spec.get("facts", [])
    if not 3 <= len(facts) <= 5:
        raise LayoutError("Se requieren entre 3 y 5 datos clave")
    label_w = 236
    val_w = inner - label_w
    fv = F.fact_value
    vlh = round(fv.size * 1.3)
    for i, fact in enumerate(facts):
        vlines = wrap(fact["value"], fv, val_w)
        if len(vlines) > 3:
            raise LayoutError(f"Dato clave demasiado largo: {fact['label']}")
        if tracked_len(fact["label"].upper(), F.label) > label_w - 16:
            raise LayoutError(f"Etiqueta demasiado larga: {fact['label']}")
        row_h = max(len(vlines) * vlh, 34) + 22
        if draw:
            if i == 0:
                draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=rule)
            tracked(draw, (MARGIN, y + 18), fact["label"].upper(), F.label, muted)
            yy = y + 12
            for ln in vlines:
                draw.text((MARGIN + label_w, yy), ln, font=fv, fill=ink)
                yy += vlh
            draw.rectangle([MARGIN, y + row_h, W - MARGIN, y + row_h + 1], fill=rule)
        y += row_h
    y += 30

    # Acción concreta
    act = spec.get("action")
    if act:
        at = F.action_text
        alh = round(at.size * 1.36)
        alines = wrap(act["text"], at, inner - 30)
        if len(alines) > 4:
            raise LayoutError("Texto de acción de más de 4 líneas")
        block_h = 32 + len(alines) * alh
        if draw:
            draw.rectangle([MARGIN, y, MARGIN + 5, y + block_h], fill=accent)
            tracked(draw, (MARGIN + 26, y), act["label"].upper(), F.label, accent)
            yy = y + 34
            for ln in alines:
                draw.text((MARGIN + 26, yy), ln, font=at, fill=ink)
                yy += alh
        y += block_h
    return y


def tint(color, amount: float):
    """Mezcla el color de acento con el papel (amount = proporción de acento)."""
    return tuple(round(p + (c - p) * amount) for c, p in zip(color, PALETTE["paper"]))


def layout_v2(spec: dict, F: Fonts, accent, draw: ImageDraw.ImageDraw | None, gap_extra: int = 0):
    """Plantilla compacta. Devuelve (y final del contenido, número de huecos ampliables)."""
    inner = W - 2 * MARGIN
    ink, soft, muted, rule = PALETTE["ink"], PALETTE["ink_soft"], PALETTE["muted"], PALETTE["rule"]
    gaps = 0

    # Cabecera: categoría + marca + filete + número/fecha
    y = 70
    if draw:
        tracked(draw, (MARGIN, y + 4), spec["kicker"].upper(), F.label, accent)
        brand = "DiegoVal Academy"
        draw.text((W - MARGIN - F.brand.getlength(brand), y - 2), brand, font=F.brand, fill=ink)
    if tracked_len(spec["kicker"].upper(), F.label) > inner - F.brand.getlength("DiegoVal Academy") - 30:
        raise LayoutError("Antetítulo demasiado largo")
    y += 50
    if draw:
        draw.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=ink)
    if spec.get("issue"):
        y += 16
        if draw:
            tracked(draw, (MARGIN, y), spec["issue"].upper(), F.small, muted, tracking=1.0)
    y += 56

    # Titular (ideal 2 líneas)
    hl = F.headline
    lh = round(hl.size * 1.08)
    lines = wrap(spec["headline"], hl, inner)
    if len(lines) > 3:
        raise LayoutError("Titular de más de 3 líneas")
    for ln in lines:
        if draw:
            draw.text((MARGIN, y), ln, font=hl, fill=ink)
        y += lh
    y += 30 + gap_extra
    gaps += 1

    # Entradilla (máx. 2 líneas)
    dk = F.dek
    lh = round(dk.size * 1.36)
    lines = wrap(spec["dek"], dk, inner)
    if len(lines) > 2:
        raise LayoutError("Entradilla de más de 2 líneas")
    for ln in lines:
        if draw:
            draw.text((MARGIN, y), ln, font=dk, fill=soft)
        y += lh
    y += 34 + gap_extra
    gaps += 1

    # Bloque destacado (plazo o idea clave)
    hlg = spec["highlight"]
    pad = 30
    hv = F.highlight_value
    vlines = wrap(hlg["value"], hv, inner - 2 * pad)
    if len(vlines) > 2:
        raise LayoutError("Valor destacado de más de 2 líneas")
    vlh = round(hv.size * 1.12)
    note_h = 40 if hlg.get("note") else 0
    box_h = pad + 34 + len(vlines) * vlh + note_h + pad - 4
    if hlg.get("note") and F.small.getlength(hlg["note"]) > inner - 2 * pad:
        raise LayoutError("Nota del bloque destacado demasiado larga")
    if draw:
        draw.rectangle([MARGIN, y, W - MARGIN, y + box_h], fill=accent)
        tracked(draw, (MARGIN + pad, y + pad - 2), hlg["label"].upper(), F.label, PALETTE["white"])
        yy = y + pad + 36
        for ln in vlines:
            draw.text((MARGIN + pad, yy), ln, font=hv, fill=PALETTE["white"])
            yy += vlh
        if hlg.get("note"):
            draw.text((MARGIN + pad, yy + 8), hlg["note"], font=F.small, fill=PALETTE["white"])
    y += box_h + 30 + gap_extra
    gaps += 1

    # 2-3 datos esenciales
    facts = spec.get("facts", [])
    if not 2 <= len(facts) <= 3:
        raise LayoutError("La plantilla compacta admite 2 o 3 datos")
    label_w = 210
    val_w = inner - label_w
    fv = F.fact_value
    vlh = round(fv.size * 1.28)
    for i, fact in enumerate(facts):
        vlines = wrap(fact["value"], fv, val_w)
        if len(vlines) > 2:
            raise LayoutError(f"Dato demasiado largo (máx. 2 líneas): {fact['label']}")
        if tracked_len(fact["label"].upper(), F.label) > label_w - 16:
            raise LayoutError(f"Etiqueta demasiado larga: {fact['label']}")
        row_h = len(vlines) * vlh + 34
        if draw:
            if i == 0:
                draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=rule)
            tracked(draw, (MARGIN, y + 23), fact["label"].upper(), F.label, muted)
            yy = y + 16
            for ln in vlines:
                draw.text((MARGIN + label_w, yy), ln, font=fv, fill=ink)
                yy += vlh
            draw.rectangle([MARGIN, y + row_h, W - MARGIN, y + row_h + 1], fill=rule)
        y += row_h
    y += 34 + gap_extra
    gaps += 1

    # Lo que pocos explican: el dato práctico diferencial
    tip = spec["tip"]
    tt = F.action_text
    tlh = round(tt.size * 1.34)
    pad = 28
    tlines = wrap(tip["text"], tt, inner - 2 * pad - 8)
    if len(tlines) > 3:
        raise LayoutError("Texto de 'Lo que pocos explican' de más de 3 líneas")
    block_h = pad + 34 + len(tlines) * tlh + pad - 8
    if draw:
        draw.rectangle([MARGIN, y, W - MARGIN, y + block_h], fill=tint(accent, 0.10))
        draw.rectangle([MARGIN, y, MARGIN + 6, y + block_h], fill=accent)
        tracked(draw, (MARGIN + pad + 8, y + pad - 4), tip["label"].upper(), F.label, accent)
        yy = y + pad + 32
        for ln in tlines:
            draw.text((MARGIN + pad + 8, yy), ln, font=tt, fill=ink)
            yy += tlh
    y += block_h
    return y, gaps


FOOTER_TOP = H - 112


def draw_footer(draw, spec, F):
    y = FOOTER_TOP
    draw.rectangle([MARGIN, y, W - MARGIN, y + 1], fill=PALETTE["ink"])
    left = f"Fuente oficial: {spec['source']}"
    right = f"Verificado el {spec['verified']}"
    draw.text((MARGIN, y + 20), left, font=F.small, fill=PALETTE["ink"])
    draw.text((W - MARGIN - F.small.getlength(right), y + 20), right, font=F.small, fill=PALETTE["ink"])
    note = spec.get("footer_note", "Enlaces oficiales y detalles completos en el texto de la publicación.")
    draw.text((MARGIN, y + 54), note, font=F.small, fill=PALETTE["muted"])
    for t in (left, right, note):
        if F.small.getlength(t) > W - 2 * MARGIN:
            raise LayoutError(f"Texto de pie demasiado largo: {t!r}")


def render(spec: dict, out: Path) -> dict:
    accent = ACCENTS[spec["series"]]
    check_glyphs(spec)
    v2 = "tip" in spec
    sizes = SIZES_V2 if v2 else SIZES

    def measure(F, extra=0, draw=None):
        if v2:
            return layout_v2(spec, F, accent, draw, extra)
        return layout(spec, F, accent, draw), 0

    scale, last_err = 1.0, None
    while scale >= 0.6:
        F = make_fonts(scale, sizes)
        try:
            end_y, gaps = measure(F)
        except LayoutError as e:
            last_err = e
            scale -= 0.04
            continue
        if end_y <= FOOTER_TOP - 28:
            break
        last_err = LayoutError(f"Contenido demasiado largo: termina en y={end_y}, límite {FOOTER_TOP - 28}")
        if all(F.sizes[k] == lo for k, (_, lo) in sizes.items()):
            break
        scale -= 0.04
    else:
        raise last_err or LayoutError("No se pudo maquetar")
    if end_y > FOOTER_TOP - 28:
        raise last_err or LayoutError("No se pudo maquetar")

    # v2: el espacio sobrante se reparte entre secciones en lugar de quedar vacío abajo
    extra = min(MAX_GAP_EXTRA, (FOOTER_TOP - 28 - end_y) // gaps) if gaps else 0
    img = Image.new("RGB", (W, H), PALETTE["paper"])
    d = ImageDraw.Draw(img)
    end_y, _ = measure(F, extra, d)
    draw_footer(d, spec, F)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return {
        "output": str(out),
        "size": img.size,
        "font_sizes_px": F.sizes,
        "content_bottom_y": end_y,
        "free_space_px": FOOTER_TOP - 28 - end_y,
        "min_font_px": min(min(F.sizes.values()), LABEL_SIZE, 21),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    out = args.out or args.spec.with_name("post.png")
    try:
        report = render(spec, out)
    except (LayoutError, KeyError) as e:
        print(f"ERROR de maquetación: {e}", file=sys.stderr)
        return 1
    if report["min_font_px"] < MIN_ANY:
        print("ERROR: texto por debajo del tamaño mínimo", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
