"""Valida el Reel original de Instagram de una publicación (reel.mp4 generado por render_reel.py).

Uso:
    python3 scripts/validate_reel.py posts/<carpeta> [--now ISO8601]

Un Reel SIEMPRE acompaña a un carrusel de la misma carpeta (misma investigación, mismos textos): el carrusel es la
alternativa segura. Por eso este validador exige primero que `validate_carousel.py` apruebe la carpeta (texto en
lenguaje sencillo, fuentes, duplicados con la política de repetición, verificación del día) y después comprueba el vídeo:

- el MP4 corresponde al carousel.json actual (huella sha256) y no fue modificado;
- formato real (leído con FFmpeg): H.264, yuv420p, 1080x1920 (9:16), ~30 fps, audio AAC, 15-90 s, ≤ 100 MB;
- legibilidad: letra mínima ≥ 38 px (registrada al renderizar) y zonas de la interfaz de Instagram vacías, comprobado
  sobre FOTOGRAMAS DECODIFICADOS del propio MP4 (arriba 240 px, abajo 440 px y columna derecha);
- subtítulos: el texto en español va incrustado en la imagen; no hay voz ni música; ningún texto fuera de carousel.json;
- el caption no promete subtítulos ni narración que el vídeo no tiene.
Escribe validation_reel.md. `prepare_publish_reel.py` se niega sin una validación APROBADA.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_carousel  # noqa: E402
from render_carousel import texts_of  # noqa: E402
from render_post import PALETTE  # noqa: E402
from render_reel import MIN_PRIMARY_PX, OUT_META, OUT_VIDEO, RH, RW, ffmpeg_exe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = "validation_reel.md"
MIN_S, MAX_S, WARN_S, MAX_BYTES = 15, 90, 75, 100 * 1024 * 1024
FIXED_TEXTS = {"Guárdala para después"}
CAPTION_PROMISES = ["subtítulos", "subtitulado", "narración", "con voz", "audio", "música"]


def probe(mp4: Path) -> dict:
    """Lee el formato real del MP4 con FFmpeg (sin ffprobe)."""
    err = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(mp4)], capture_output=True, text=True).stderr
    info: dict = {"raw": err}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    info["duration_s"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    v = re.search(r"Video: (\w+)[^\n]*?, (yuv\w+)[^\n]*?, (\d+)x(\d+)[^\n]*?, ([\d.]+) fps", err)
    if v:
        info.update(codec=v.group(1), pix_fmt=v.group(2), width=int(v.group(3)), height=int(v.group(4)), fps=float(v.group(5)))
    a = re.search(r"Audio: (\w+)", err)
    info["audio"] = a.group(1) if a else None
    return info


def frame_at(mp4: Path, t: float) -> Image.Image:
    out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(mp4),
                          "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(out)).convert("RGB")


def ui_zone_violations(img: Image.Image) -> list[str]:
    """Píxeles que NO son papel (salvo un margen de compresión) en las zonas que tapa la interfaz de Instagram."""
    paper = PALETTE["paper"]
    bad = []

    def dirty(box) -> int:
        reg = img.crop(box)
        # Pillow ≥ 13 retira getdata(); get_flattened_data() existe desde Pillow 12.1
        px = reg.get_flattened_data() if hasattr(reg, "get_flattened_data") else reg.getdata()
        return sum(1 for p in px if max(abs(p[i] - paper[i]) for i in range(3)) > 24)

    top = dirty((0, 24, RW, 240))          # por debajo de la franja de color de 14 px
    bottom = dirty((0, RH - 430, RW, RH))
    right = dirty((RW - 90, 256, RW, RH - 440))
    for name, n in (("arriba (240 px)", top), ("abajo (430 px)", bottom), ("derecha (90 px)", right)):
        if n > 40:
            bad.append(f"{name}: {n} píxeles con contenido")
    return bad


def validate(folder: Path, now: datetime, check_linkedin: bool = True) -> tuple[list[tuple[str, str, str]], bool]:
    results: list[tuple[str, str, str]] = []

    def ok(n, d=""):
        results.append(("PASS", n, d))

    def fail(n, d):
        results.append(("FAIL", n, d))

    def warn(n, d):
        results.append(("WARN", n, d))

    mp4, meta_p, spec_p = folder / OUT_VIDEO, folder / OUT_META, folder / "carousel.json"
    missing = [p.name for p in (mp4, meta_p, spec_p, folder / "metadata.json") if not p.exists()]
    if missing:
        fail("Archivos obligatorios", f"faltan: {missing}")
        return results, False
    ok("Archivos obligatorios", f"{OUT_VIDEO}, {OUT_META}, carousel.json")

    # 1. El carrusel de la misma carpeta (alternativa segura) debe estar aprobado: texto, fuentes, duplicados, hoy.
    res, passed = validate_carousel.validate(folder, now, check_linkedin)
    if passed:
        ok("Base: carrusel aprobado", "validate_carousel.py: APROBADA (texto en lenguaje sencillo, fuentes, duplicados)")
    else:
        fail("Base: carrusel aprobado", "validate_carousel.py bloquea: " + "; ".join(n for s, n, _ in res if s == "FAIL"))

    # 2. Huellas: el vídeo corresponde al carousel.json actual y no se ha tocado
    render = json.loads(meta_p.read_text(encoding="utf-8"))
    if render.get("carousel_sha256") != hashlib.sha256(spec_p.read_bytes()).hexdigest():
        fail("Vídeo actualizado", "carousel.json cambió después de renderizar: ejecuta render_reel.py otra vez")
    elif render.get("mp4_sha256") != hashlib.sha256(mp4.read_bytes()).hexdigest():
        fail("Vídeo íntegro", "reel.mp4 no coincide con la huella registrada")
    else:
        ok("Vídeo actualizado e íntegro", "huellas sha256 de carousel.json y reel.mp4 coinciden")

    # 3. Formato real
    p = probe(mp4)
    problems = []
    if p.get("codec") != "h264":
        problems.append(f"códec {p.get('codec')} (se espera h264)")
    if p.get("pix_fmt") != "yuv420p":
        problems.append(f"pix_fmt {p.get('pix_fmt')} (se espera yuv420p)")
    if (p.get("width"), p.get("height")) != (RW, RH):
        problems.append(f"tamaño {p.get('width')}x{p.get('height')} (se espera {RW}x{RH}, 9:16)")
    if not p.get("fps") or abs(p["fps"] - 30) > 0.5:
        problems.append(f"fps {p.get('fps')} (se espera 30)")
    if p.get("audio") != "aac":
        problems.append(f"audio {p.get('audio')} (se espera una pista AAC, aunque sea silenciosa)")
    (fail if problems else ok)("Formato del vídeo", "; ".join(problems) if problems
                               else f"h264 yuv420p {RW}x{RH} {p['fps']:g} fps + audio aac")
    d = p.get("duration_s")
    if d is None or not MIN_S <= d <= MAX_S:
        fail("Duración", f"{d} s (se esperan {MIN_S}-{MAX_S} s)")
    elif d > WARN_S:
        warn("Duración", f"{d:.0f} s: larga para un Reel; considera acortar los textos")
    else:
        ok("Duración", f"{d:.0f} s")
    size = mp4.stat().st_size
    (ok if size <= MAX_BYTES else fail)("Tamaño del archivo", f"{size / 1e6:.1f} MB (máx. {MAX_BYTES // 1024 // 1024} MB)")

    # 4. Legibilidad: letra mínima registrada + zonas de la interfaz vacías en fotogramas reales del MP4
    mf = render.get("min_font_px", 0)
    (ok if mf >= MIN_PRIMARY_PX else fail)("Legibilidad: tamaño de letra", f"mínimo {mf} px (≥ {MIN_PRIMARY_PX} px)")
    if d:
        bad_all = []
        for sc in render.get("scenes", []):
            t = min(sc["start_s"] + sc["duration_s"] - 0.3, d - 0.2)
            bad = ui_zone_violations(frame_at(mp4, t))
            if bad:
                bad_all.append(f"escena '{sc['kind']}' ({t:.1f} s): " + "; ".join(bad))
        (fail if bad_all else ok)("Zona segura de Instagram (fotogramas reales)",
                                  " | ".join(bad_all) if bad_all else f"{len(render.get('scenes', []))} fotogramas sin contenido en las zonas que tapa la interfaz")

    # 5. Subtítulos y textos: todo el texto es español incrustado y procede de carousel.json (ya revisado)
    spec = json.loads(spec_p.read_text(encoding="utf-8"))
    allowed = set(texts_of(spec)) | FIXED_TEXTS
    extra = [t for t in render.get("texts", []) if t not in allowed]
    (fail if extra else ok)("Textos del vídeo", f"textos que no están en carousel.json: {extra}" if extra
                            else "todo el texto del vídeo procede de carousel.json (revisado en lenguaje sencillo)")
    if render.get("text_burned_in") == "es" and render.get("audio", "").startswith("silencio"):
        ok("Subtítulos", "texto en español incrustado en la imagen; sin voz ni música: no se promete ningún subtítulo aparte")
    else:
        fail("Subtítulos", "reel_render.json no declara texto en español incrustado y audio en silencio")
    cap = (folder / validate_carousel.CAPTION_FILE).read_text(encoding="utf-8").lower()
    promised = [w for w in CAPTION_PROMISES if w in cap]
    (fail if promised else ok)("El caption no promete lo que el vídeo no tiene",
                               f"menciona {promised}: el Reel no tiene voz, música ni subtítulos activables" if promised else "sin promesas de audio ni subtítulos")

    # 6. Decisión de formato registrada (autonomía con trazabilidad)
    ig = json.loads((folder / "metadata.json").read_text(encoding="utf-8")).get("instagram") or {}
    reason = str(ig.get("format_reason", "")).strip()
    if ig.get("format") == "reel" and len(reason) >= 20:
        ok("Decisión de formato", f"reel: {reason[:90]}")
    else:
        fail("Decisión de formato", "metadata.instagram.format debe ser 'reel' y metadata.instagram.format_reason (≥ 20 caracteres) "
                                    "explicar por qué el Reel aporta más que el carrusel")
    return results, not any(s == "FAIL" for s, _, _ in results)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--now", help="ISO 8601 con zona; por defecto, ahora")
    ap.add_argument("--skip-linkedin-check", action="store_true", help="sólo pruebas (carpetas de borrador sin validación de LinkedIn)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    folder = a.folder.resolve()
    pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(ZoneInfo(pub["timezone"]))
    results, passed = validate(folder, now, not a.skip_linkedin_check)
    decision = "APROBADA para publicar" if passed else "BLOQUEADA: no publicar"
    lines = [f"# Validación del Reel — {folder.name}", "", f"Ejecutado: {now.isoformat(timespec='seconds')}",
             f"Decisión: **{decision}**", "", "| Estado | Comprobación | Detalle |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {d.replace('|', '/')} |" for s, n, d in results]
    (folder / VALIDATION).write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s, n, d in results:
        print(f"[{s}] {n}: {d}")
    print(f"\nDECISIÓN: {decision}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
