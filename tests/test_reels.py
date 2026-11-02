"""Reels originales (render_reel / validate_reel / prepare_publish_reel) y arreglo del validador de imágenes. Sin red.

Los tests de Reels necesitan FFmpeg (del sistema o `pip install -r requirements-video.txt`); si no hay, se omiten.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import history  # noqa: E402
import prepare_publish_reel as ppr  # noqa: E402
import render_reel  # noqa: E402
import test_instagram as ti  # noqa: E402
import test_sistema as ts  # noqa: E402
import validate_post  # noqa: E402
import validate_reel  # noqa: E402
from render_post import LayoutError, PALETTE  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
NOW = ti.NOW


def have_ffmpeg() -> bool:
    try:
        render_reel.ffmpeg_exe()
        return True
    except LayoutError:
        return False


class TestArregloValidadorImagen(ts.Sandbox):
    """El carrusel deja slide-N.png junto a post.png: no debe contar como 'más de una imagen' de LinkedIn."""

    def img_status(self, f: Path):
        res, _ = validate_post.validate(f, ts.NOW_OK, True)
        return next((s, d) for s, n, d in res if n == "Imagen")

    def test_diapositivas_del_carrusel_no_cuentan(self):
        f = self.copy(ts.BASE_RC)
        for i in range(1, 6):
            shutil.copy(f / "post.png", f / f"slide-{i}.png")
        status, detail = self.img_status(f)
        self.assertEqual(status, "PASS", detail)
        self.assertIn("5 diapositivas", detail)

    def test_otra_png_suelta_sigue_bloqueando(self):
        f = self.copy(ts.BASE_RC)
        shutil.copy(f / "post.png", f / "otra.png")
        self.assertEqual(self.img_status(f)[0], "FAIL")

    def test_falta_post_png_no_revienta(self):
        f = self.copy(ts.BASE_RC)
        (f / "post.png").unlink()
        res, passed = validate_post.validate(f, ts.NOW_OK, True)  # se detiene antes, sin excepción
        self.assertFalse(passed)
        self.assertIn("Archivos obligatorios", [n for s, n, _ in res if s == "FAIL"])

    def test_formato_video_admite_diapositivas_pero_no_post_png(self):
        f = self.tmp / "x"
        f.mkdir()
        (f / "slide-1.png").write_bytes(b"x")
        (f / "post.png").write_bytes(b"x")
        self.assertEqual([p.name for p in validate_post.own_pngs(f)], ["post.png"])
        self.assertEqual([p.name for p in validate_post.slide_pngs(f)], ["slide-1.png"])


class TestZonaSegura(unittest.TestCase):
    def test_lienzo_limpio_no_tiene_violaciones(self):
        from PIL import Image
        img = Image.new("RGB", (render_reel.RW, render_reel.RH), PALETTE["paper"])
        self.assertEqual(validate_reel.ui_zone_violations(img), [])

    def test_texto_en_zona_de_la_interfaz_se_detecta(self):
        from PIL import Image, ImageDraw
        for box, zona in (((100, 100, 500, 200), "arriba"), ((100, 1600, 600, 1700), "abajo"), ((1000, 800, 1070, 1000), "derecha")):
            img = Image.new("RGB", (render_reel.RW, render_reel.RH), PALETTE["paper"])
            ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))
            bad = validate_reel.ui_zone_violations(img)
            self.assertTrue(any(zona in b for b in bad), (zona, bad))


@unittest.skipUnless(have_ffmpeg(), "sin FFmpeg")
class TestReel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._hist = history.HISTORY
        history.HISTORY = cls.tmp / "history.csv"
        history.write_history([])
        cls.folder = ti.make_folder(cls.tmp)
        assert render_reel.main([str(cls.folder / "carousel.json")]) == 0
        cls.base = {p.name: p.read_bytes() for p in cls.folder.iterdir() if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        history.HISTORY = cls._hist
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):  # cada prueba parte de la carpeta recién renderizada
        for p in self.folder.iterdir():
            if p.is_file() and p.name not in self.base:
                p.unlink()
        for name, data in self.base.items():
            (self.folder / name).write_bytes(data)
        self.set_meta(format="reel", format_reason="Pasos cortos que se entienden mejor viendo cómo aparecen uno a uno.")

    def set_meta(self, **ig):
        m = json.loads((self.folder / "metadata.json").read_text(encoding="utf-8"))
        m.setdefault("instagram", {}).update(ig)
        (self.folder / "metadata.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    def fails(self) -> list[str]:
        res, _ = validate_reel.validate(self.folder, NOW, check_linkedin=False)
        return [n for s, n, _ in res if s == "FAIL"]

    # --- render ---
    def test_formato_real_del_mp4(self):
        p = validate_reel.probe(self.folder / "reel.mp4")
        self.assertEqual((p["codec"], p["pix_fmt"], p["width"], p["height"]), ("h264", "yuv420p", 1080, 1920))
        self.assertAlmostEqual(p["fps"], 30, delta=0.5)
        self.assertEqual(p["audio"], "aac")
        self.assertTrue(15 <= p["duration_s"] <= 90)

    def test_los_textos_del_reel_salen_del_carrusel(self):
        meta = json.loads((self.folder / "reel_render.json").read_text(encoding="utf-8"))
        spec = json.loads((self.folder / "carousel.json").read_text(encoding="utf-8"))
        from render_carousel import texts_of
        self.assertLessEqual(set(meta["texts"]) - set(texts_of(spec)), validate_reel.FIXED_TEXTS)
        self.assertGreaterEqual(meta["min_font_px"], 38)

    # --- validación ---
    def test_reel_valido_se_aprueba(self):
        self.assertEqual(self.fails(), [])

    def test_carousel_modificado_deja_el_video_obsoleto(self):
        spec = json.loads((self.folder / "carousel.json").read_text(encoding="utf-8"))
        spec["slides"][0]["title"] = "Otro título"
        (self.folder / "carousel.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        self.assertIn("Vídeo actualizado", self.fails())

    def test_mp4_alterado_bloquea(self):
        with (self.folder / "reel.mp4").open("ab") as f:
            f.write(b"\0" * 16)
        self.assertIn("Vídeo íntegro", self.fails())

    def test_caption_que_promete_subtitulos_bloquea(self):
        cap = self.folder / "caption_instagram.md"
        cap.write_text(cap.read_text(encoding="utf-8").replace("Guarda esta guía.", "Activa los subtítulos. Guarda esta guía."),
                       encoding="utf-8")
        self.assertIn("El caption no promete lo que el vídeo no tiene", self.fails())

    def test_sin_decision_de_formato_bloquea(self):
        self.set_meta(format="carrusel", format_reason="")
        self.assertIn("Decisión de formato", self.fails())

    def test_falta_el_video(self):
        (self.folder / "reel.mp4").unlink()
        self.assertIn("Archivos obligatorios", self.fails())

    def test_texto_ajeno_en_el_render_bloquea(self):
        p = self.folder / "reel_render.json"
        m = json.loads(p.read_text(encoding="utf-8"))
        m["texts"].append("Texto que no está en el carrusel")
        p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        self.assertIn("Textos del vídeo", self.fails())

    def test_texto_demasiado_largo_no_se_recorta_falla(self):
        spec = json.loads((self.folder / "carousel.json").read_text(encoding="utf-8"))
        spec = copy.deepcopy(spec)
        spec["slides"][1]["items"] = [{"text": "Palabra " * 15} for _ in range(4)]
        src = self.tmp / "largo.json"
        src.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        out = self.tmp / "out"
        out.mkdir(exist_ok=True)
        self.assertEqual(render_reel.main([str(src), "--out-dir", str(out)]), 1)
        self.assertFalse((out / "reel.mp4").exists())

    # --- publicación ---
    def approved(self):
        res, passed = validate_reel.validate(self.folder, NOW, check_linkedin=False)
        self.assertTrue(passed, res)
        (self.folder / "validation_reel.md").write_text("Decisión: **APROBADA para publicar**\n", encoding="utf-8")

    def fake_fetch(self, *a, **k):
        return 200, "video/mp4", (self.folder / "reel.mp4").read_bytes(), ""

    def run_ppr(self, *args):
        with mock.patch.object(ppr, "fetch_bytes", self.fake_fetch):
            return ppr.main([str(self.folder), "--video-url", "https://raw.example/sha/p/reel.mp4", *args])

    def test_borrador_funciona_y_el_payload_es_un_reel(self):
        self.approved()
        self.assertEqual(self.run_ppr("--draft"), 0)
        pay = json.loads((self.folder / "buffer_payload_reel.json").read_text(encoding="utf-8"))
        self.assertEqual(pay["metadata"]["instagram"], {"type": "reel", "shouldShareToFeed": True})
        self.assertEqual(pay["assets"][0]["video"]["url"], "https://raw.example/sha/p/reel.mp4")
        self.assertGreater(pay["assets"][0]["video"]["metadata"]["thumbnailOffset"], 1000)
        self.assertTrue(pay["saveToDraft"])
        self.assertEqual(pay["schedulingType"], "automatic")
        self.assertNotIn("mode", pay)
        self.assertEqual(pay["channelId"], json.loads((ROOT / "config" / "instagram_channel.json").read_text(encoding="utf-8"))["channel_id"])

    def test_publicacion_automatica_de_reels_esta_apagada(self):
        pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
        self.assertFalse(pub["instagram"]["reels"]["enabled"], "los Reels no se publican solos hasta que el propietario lo active")
        self.approved()
        for args in (("--slot",), ("--mode", "shareNow")):
            self.assertEqual(self.run_ppr(*args), 1, args)
        self.assertFalse((self.folder / "buffer_payload_reel.json").exists())

    def test_con_el_interruptor_encendido_se_puede_programar(self):
        self.approved()
        pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
        pub["instagram"]["reels"]["enabled"] = True
        real = Path.read_text

        def fake_read(self_, *a, **k):
            if self_.name == "publishing.json":
                return json.dumps(pub)
            return real(self_, *a, **k)

        with mock.patch.object(Path, "read_text", fake_read):
            self.assertEqual(self.run_ppr("--mode", "shareNow"), 0)
        pay = json.loads((self.folder / "buffer_payload_reel.json").read_text(encoding="utf-8"))
        self.assertEqual(pay["mode"], "shareNow")
        self.assertNotIn("saveToDraft", pay)

    def test_sin_validacion_aprobada_bloquea(self):
        self.assertEqual(self.run_ppr("--draft"), 1)

    def test_video_publico_distinto_bloquea(self):
        self.approved()
        with mock.patch.object(ppr, "fetch_bytes", lambda *a, **k: (200, "video/mp4", b"otro", "")):
            self.assertEqual(ppr.main([str(self.folder), "--video-url", "https://raw.example/x.mp4", "--draft"]), 1)

    def test_url_que_no_es_video_bloquea(self):
        self.approved()
        with mock.patch.object(ppr, "fetch_bytes", lambda *a, **k: (200, "text/html", b"<html>", "")):
            self.assertEqual(ppr.main([str(self.folder), "--video-url", "https://raw.example/x.mp4", "--draft"]), 1)


if __name__ == "__main__":
    unittest.main()
