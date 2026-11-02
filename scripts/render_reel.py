"""Genera un Reel original de Instagram (vídeo vertical 1080x1920, MP4) a partir del MISMO carousel.json.

Uso:
    python3 scripts/render_reel.py posts/<carpeta>/carousel.json [--out-dir posts/<carpeta>] [--preview DIR]

Salida: reel.mp4 y reel_render.json (huellas sha256 de carousel.json y del MP4, duración, escenas y tamaños de letra,
que `validate_reel.py` usa para detectar un vídeo obsoleto). Herramientas gratuitas: Pillow dibuja cada fotograma
(fuentes OFL de assets/fonts, paleta del carrusel) y FFmpeg lo codifica en H.264 + AAC (pista de audio en silencio:
sin música ni voz de terceros). Todo el texto es texto real, ya revisado en lenguaje sencillo en carousel.json:
el Reel NO añade textos nuevos (salvo «Guárdala para después», la fuente y la fecha de verificación, que también
están en el carrusel). Sin servicios de pago ni IA generativa.

Diseño: escenas = portada + las 4 diapositivas del carrusel. Los textos aparecen uno a uno (fundido + deslizamiento
suave) con tiempo de lectura de ~3,3 palabras/s para quien lee despacio. Zona segura de Instagram: nada importante
en los primeros 250 px ni en los últimos 440 px, ni a la derecha (botones de «me gusta», comentar…). Si el texto no
cabe con letra legible (≥ 38 px) el script falla (exit 1) en lugar de recortar: entonces se publica solo el carrusel.

FFmpeg: se usa el `ffmpeg` del sistema o, si no hay, el que trae el paquete gratuito `imageio-ffmpeg`
(requirements-video.txt).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_carousel import (PALE, check_spec, fit_text, icon, rounded)  # noqa: E402
from render_post import ACCENTS, PALETTE, SANS, SERIF, LayoutError, font, tracked  # noqa: E402

RW, RH = 1080, 1920
FPS = 30
LEFT = 84
RIGHT_PAD = 100                      # botones de Instagram a la derecha
INNER = RW - LEFT - RIGHT_PAD        # ancho útil del texto
SAFE_TOP, SAFE_BOTTOM = 250, RH - 440
WORDS_PER_S = 3.3                    # velocidad de lectura cómoda para quien lee despacio
FADE_S, SLIDE_PX, XFADE_S = 0.45, 38, 0.4
MIN_PRIMARY_PX = 38                  # letra mínima del contenido principal
OUT_VIDEO, OUT_META = "reel.mp4", "reel_render.json"
MAX_SECONDS = 90                     # límite de Instagram para Reels


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        raise LayoutError("no hay FFmpeg: instala `ffmpeg` o `pip install -r requirements-video.txt`") from e


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def words(t: str) -> int:
    return max(1, len(t.split()))


def read_time(t: str) -> float:
    return 0.6 + words(t) / WORDS_PER_S


class Layer:
    """Elemento que aparece con fundido y deslizamiento en el instante `t0`."""

    def __init__(self, t0: float, img: Image.Image, xy: tuple[int, int]):
        self.t0, self.img, self.xy = t0, img, xy


class Scene:
    def __init__(self, kind: str, base: Image.Image, layers: list[Layer], duration: float, texts: list[str]):
        self.kind, self.base, self.layers, self.duration, self.texts = kind, base, layers, duration, texts
        self.sizes: list[int] = []

    def frame(self, t: float) -> Image.Image:
        img = self.base.copy()
        for ly in self.layers:
            p = ease((t - ly.t0) / FADE_S)
            if p <= 0:
                continue
            layer = ly.img
            if p < 1:
                a = ImageChops.multiply(layer.getchannel("A"), Image.new("L", layer.size, round(255 * p)))
                layer = layer.copy()
                layer.putalpha(a)
            img.paste(layer, (ly.xy[0], ly.xy[1] + round((1 - p) * SLIDE_PX)), layer)
        return img

    def state(self, t: float) -> tuple | None:
        """Firma del estado visual si todos los elementos están quietos (ocultos o ya visibles); None si algo se mueve."""
        sig = []
        for ly in self.layers:
            p = (t - ly.t0) / FADE_S
            if 0 < p < 1:
                return None
            sig.append(p >= 1)
        return tuple(sig)


def canvas(accent, idx: int, total: int, spec: dict, last: bool) -> Image.Image:
    img = Image.new("RGB", (RW, RH), PALETTE["paper"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, RW, 14], fill=accent)
    d.text((LEFT, SAFE_TOP + 44), "DiegoVal", font=font(SERIF, 36, 680, opsz=36), fill=PALETTE["ink"])
    wd = font(SERIF, 36, 680, opsz=36).getlength("DiegoVal ")
    d.text((LEFT + wd, SAFE_TOP + 44), "Academy", font=font(SERIF, 36, 400, opsz=36), fill=PALETTE["ink_soft"])
    pill = font(SANS, 28, 650)
    label = f"{idx}/{total}"
    pw = pill.getlength(label) + 44
    rounded(d, [RW - RIGHT_PAD - pw, SAFE_TOP + 36, RW - RIGHT_PAD, SAFE_TOP + 84], 24, accent)
    d.text((RW - RIGHT_PAD - pw / 2, SAFE_TOP + 60), label, font=pill, fill=PALETTE["white"], anchor="mm")
    small = font(SANS, 25, 480)
    y = SAFE_BOTTOM - 40
    d.rectangle([LEFT, y - 20, RW - RIGHT_PAD, y - 19], fill=PALETTE["rule"])
    d.text((LEFT, y), f"Fuente oficial: {spec['source']}  ·  Verificado el {spec['verified']}", font=small, fill=PALETTE["muted"])
    return img


def text_layer(lines: list[str], f, fill, lh: int, width: int) -> Image.Image:
    img = Image.new("RGBA", (width, lh * len(lines) + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((0, i * lh), ln, font=f, fill=fill)
    return img


def title_layer(title: str, accent) -> tuple[Image.Image, int, int]:
    f, lines = fit_text(title, SERIF, 700, (66, 54), INNER, 2, opsz=True)
    lh = round(f.size * 1.12)
    img = text_layer(lines, f, PALETTE["ink"], lh, INNER)
    img = img.crop((0, 0, INNER, img.height + 24))
    ImageDraw.Draw(img).rectangle([0, img.height - 14, 120, img.height - 8], fill=accent)
    return img, img.height, int(f.size)


def item_card(item: dict, idx: int, kind: str, accent, y_size: list[int]) -> Image.Image:
    pad, badge = 22, 56
    tw = INNER - 2 * pad - badge - 20
    f, lines = fit_text(item["text"], SANS, 440, (44, MIN_PRIMARY_PX), tw, 7)
    y_size.append(int(f.size))
    lh = round(f.size * 1.3)
    h = max(2 * pad + lh * len(lines), 2 * pad + badge)
    card = Image.new("RGBA", (INNER, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, INNER - 1, h - 1], radius=26, fill=(255, 255, 255, 255), outline=PALETTE["rule"], width=2)
    cx, cy = pad + badge // 2, pad + badge // 2
    if kind == "steps":
        d.ellipse([cx - badge // 2, cy - badge // 2, cx + badge // 2, cy + badge // 2], fill=accent)
        d.text((cx, cy - 1), str(idx), font=font(SANS, 34, 700), fill=PALETTE["white"], anchor="mm")
    else:
        icon(d, item.get("icon") or "check", cx, cy, badge // 2, PALETTE["white"], accent)
    ty = (h - lh * len(lines)) // 2
    for i, ln in enumerate(lines):
        d.text((pad + badge + 20, ty + i * lh), ln, font=f, fill=PALETTE["ink"])
    return card


def build_content_scene(spec: dict, s: dict, idx: int, total: int, accent) -> Scene:
    last = s["type"] == "summary"
    base = canvas(accent, idx, total, spec, last)
    sizes: list[int] = []
    title_img, th, tsize = title_layer(s["title"], accent)
    sizes.append(tsize)
    top = SAFE_TOP + 120
    layers = [Layer(0.2, title_img, (LEFT, top))]
    y = top + th + 40
    t = 0.2 + 0.9
    texts = [s["title"]]
    for n, it in enumerate(s["items"], start=1):
        card = item_card(it, n, s["type"], accent, sizes)
        if y + card.height > SAFE_BOTTOM - 80:
            raise LayoutError(f"'{s['title']}': el texto no cabe en la zona segura del Reel (acorta el elemento {n} "
                              "o publica solo el carrusel)")
        layers.append(Layer(t, card, (LEFT, y)))
        y += card.height + 18
        t += read_time(it["text"]) - 0.3
        texts.append(it["text"])
    if s.get("cta"):
        cf = font(SANS, 40, 650)
        label = s["cta"]
        w = int(cf.getlength(label)) + 64
        if w > INNER:
            cf = font(SANS, 34, 650)
            w = int(cf.getlength(label)) + 64
            sizes.append(34)
        else:
            sizes.append(40)
        pill = Image.new("RGBA", (min(w, INNER), 92), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle([0, 0, pill.width - 1, 91], radius=46, fill=accent + (255,))
        pd.text((pill.width / 2, 46), label, font=cf, fill=PALETTE["white"], anchor="mm")
        if y + 92 > SAFE_BOTTOM - 80:
            raise LayoutError(f"'{s['title']}': no cabe la llamada final en la zona segura")
        layers.append(Layer(t, pill, (LEFT, y + 8)))
        t += read_time(label) - 0.3
        texts.append(label)
    # centra un poco el bloque en el espacio libre (zona segura) en vez de pegarlo arriba
    free = (SAFE_BOTTOM - 80) - (y + (100 if s.get("cta") else 0))
    shift = max(0, min(round(free * 0.35), 220))
    layers = [Layer(ly.t0, ly.img, (ly.xy[0], ly.xy[1] + (shift if i else 0))) for i, ly in enumerate(layers)]
    sc = Scene(s["type"], base, layers, t + 1.5, texts)
    sc.sizes = sizes
    return sc


def build_cover(spec: dict, total: int, accent) -> Scene:
    pale = PALE[spec["series"]]
    cov = spec["cover"]
    base = canvas(accent, 1, total, spec, False)
    sizes: list[int] = []
    layers: list[Layer] = []
    top = SAFE_TOP + 170
    kick = Image.new("RGBA", (INNER, 44), (0, 0, 0, 0))
    tracked(ImageDraw.Draw(kick), (0, 0), spec.get("kicker", "").upper(), font(SANS, 28, 650), accent)
    layers.append(Layer(0.15, kick, (LEFT, top)))
    f, lines = fit_text(cov["title"], SERIF, 720, (104, 70), INNER, 5, opsz=True)
    sizes.append(int(f.size))
    lh = round(f.size * 1.12)
    tl = Image.new("RGBA", (INNER, lh * len(lines) + 16), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    phrase = cov.get("highlight")
    for i, ln in enumerate(lines):
        if phrase and phrase in ln:
            j = ln.index(phrase)
            x0 = f.getlength(ln[:j])
            x1 = x0 + f.getlength(phrase)
            td.rounded_rectangle([x0 - 8, i * lh + f.size * 0.14, x1 + 8, i * lh + f.size * 1.02], radius=10, fill=pale + (255,))
        td.text((0, i * lh), ln, font=f, fill=PALETTE["ink"])
    layers.append(Layer(0.45, tl, (LEFT, top + 70)))
    y = top + 70 + tl.height + 20
    sub = cov.get("subtitle", "")
    texts = [spec.get("kicker", ""), cov["title"], sub]
    t = 0.45 + 1.0
    if sub:
        sf, slines = fit_text(sub, SANS, 420, (44, MIN_PRIMARY_PX), INNER, 5)
        sizes.append(int(sf.size))
        slh = round(sf.size * 1.4)
        simg = text_layer(slines, sf, PALETTE["ink_soft"], slh, INNER)
        if y + simg.height > SAFE_BOTTOM - 300:
            raise LayoutError("la portada no cabe en la zona segura del Reel (acorta título o subtítulo)")
        layers.append(Layer(t, simg, (LEFT, y)))
        t += read_time(sub) - 0.3
        y += simg.height + 40
    # llamada a guardar (texto fijo, también presente en la portada del carrusel)
    save = Image.new("RGBA", (INNER, 96), (0, 0, 0, 0))
    sd = ImageDraw.Draw(save)
    sd.rounded_rectangle([0, 0, INNER - 1, 95], radius=48, fill=accent + (255,))
    icon(sd, "arrow", 52, 48, 34, accent, PALETTE["white"])
    sd.text((108, 48), "Guárdala para después", font=font(SANS, 38, 600), fill=PALETTE["white"], anchor="lm")
    sizes.append(38)
    layers.append(Layer(t, save, (LEFT, min(max(y, SAFE_BOTTOM - 330), SAFE_BOTTOM - 250))))
    texts.append("Guárdala para después")
    sc = Scene("cover", base, layers, max(t + 1.6, 5.0), [x for x in texts if x])
    sc.sizes = sizes
    return sc


def build_scenes(spec: dict) -> list[Scene]:
    check_spec(spec)
    accent = ACCENTS[spec["series"]]
    total = 1 + len(spec["slides"])
    scenes = [build_cover(spec, total, accent)]
    for i, s in enumerate(spec["slides"], start=2):
        scenes.append(build_content_scene(spec, s, i, total, accent))
    return scenes


def progress_bar(img: Image.Image, frac: float, accent) -> None:
    d = ImageDraw.Draw(img)
    y = SAFE_TOP - 4
    d.rectangle([LEFT, y, RW - RIGHT_PAD, y + 8], fill=PALETTE["rule"])
    d.rectangle([LEFT, y, LEFT + round((RW - RIGHT_PAD - LEFT) * frac), y + 8], fill=accent)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(spec: dict, out: Path, preview: Path | None = None) -> dict:
    scenes = build_scenes(spec)
    accent = ACCENTS[spec["series"]]
    total_s = sum(sc.duration for sc in scenes)
    if total_s > MAX_SECONDS:
        raise LayoutError(f"el Reel dura {total_s:.0f} s (máx. {MAX_SECONDS}): acorta los textos o publica solo el carrusel")
    n_frames = round(total_s * FPS)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{RW}x{RH}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-t", f"{n_frames / FPS:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-metadata", "title=DiegoVal Academy",
           str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    starts, t0 = [], 0.0
    for sc in scenes:
        starts.append(t0)
        t0 += sc.duration
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
    prev_last: Image.Image | None = None
    cache: tuple[int, tuple, Image.Image] | None = None
    try:
        for n in range(n_frames):
            t = n / FPS
            si = max(i for i, s0 in enumerate(starts) if s0 <= t + 1e-9)
            sc, lt = scenes[si], t - starts[si]
            sig = sc.state(lt) if lt > XFADE_S else None   # solo se reutilizan fotogramas quietos y fuera del fundido
            if sig is not None and cache and cache[0] == si and cache[1] == sig:
                base = cache[2]
            else:
                base = sc.frame(lt)
                if lt <= XFADE_S and prev_last is not None:
                    base = Image.blend(prev_last, base, ease(lt / XFADE_S))
                cache = (si, sig, base) if sig is not None else None
            frame = base.copy()
            progress_bar(frame, (n + 1) / n_frames, accent)
            proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
            if lt + 1 / FPS >= sc.duration or n == n_frames - 1:
                prev_last = base
                if preview:
                    frame.resize((540, 960)).save(preview / f"escena-{si + 1}.png")
        proc.stdin.close()  # type: ignore[union-attr]
        err = proc.stderr.read().decode("utf-8", "replace")  # type: ignore[union-attr]
        proc.stderr.close()  # type: ignore[union-attr]
        if proc.wait() != 0:
            raise LayoutError(f"FFmpeg falló: {err[-400:]}")
    except BrokenPipeError:
        raise LayoutError(f"FFmpeg cerró la entrada: {proc.stderr.read().decode('utf-8', 'replace')[-400:]}")  # type: ignore[union-attr]
    primary = [s for sc in scenes for s in sc.sizes]
    return {
        "fps": FPS, "size": [RW, RH], "duration_s": round(n_frames / FPS, 2), "frames": n_frames,
        "scenes": [{"kind": sc.kind, "start_s": round(starts[i], 2), "duration_s": round(sc.duration, 2)}
                   for i, sc in enumerate(scenes)],
        "min_font_px": min(primary), "safe_area": {"top_px": SAFE_TOP, "bottom_px": RH - SAFE_BOTTOM, "right_px": RIGHT_PAD},
        "audio": "silencio (sin música ni voz)", "text_burned_in": "es",
        "texts": [t for sc in scenes for t in sc.texts],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("carousel", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--preview", type=Path, help="carpeta donde guardar un fotograma por escena (para revisarlo)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    src = a.carousel.resolve()
    out_dir = (a.out_dir or src.parent).resolve()
    spec = json.loads(src.read_text(encoding="utf-8"))
    try:
        out = out_dir / OUT_VIDEO
        info = render(spec, out, a.preview)
    except LayoutError as e:
        print(f"ERROR de Reel: {e}", file=sys.stderr)
        return 1
    info.update({"carousel_sha256": sha256_file(src), "mp4_sha256": sha256_file(out), "mp4_bytes": out.stat().st_size})
    (out_dir / OUT_META).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {out} ({info['duration_s']} s, {info['mp4_bytes'] / 1e6:.1f} MB, letra mínima {info['min_font_px']} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
