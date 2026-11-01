"""Pruebas del canal de Instagram (carrusel de 5 imágenes) y de la deduplicación por plataforma. Sin red."""
from __future__ import annotations

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

import history  # noqa: E402
import prepare_publish_instagram as ppi  # noqa: E402
import render_carousel  # noqa: E402
import validate_carousel  # noqa: E402
import validate_post  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 10, 30, 9, 0, tzinfo=TZ)
FIX = ROOT / "tests" / "fixtures" / "carousel_example.json"
CAPTION = ("¿Buscas un doctorado en Europa? Hay un portal oficial de la Unión Europea para eso.\n\n"
           "• EURAXESS (portal oficial de la Unión Europea) reúne ofertas para investigar.\n"
           "• Usa el filtro del perfil R1 (quien empieza a investigar).\n"
           "• Lee los requisitos de cada oferta.\n\n"
           "Guarda esta guía. Búscalo en euraxess.ec.europa.eu\n\nVerificado el: 2026-10-30\n\n"
           "#Doctorado #Europa #EURAXESS")
IMG_BASE = "https://raw.example/sha/p"


def make_folder(tmp: Path, name: str = "2026-10-30_viernes_x", caption: str = CAPTION) -> Path:
    f = tmp / name
    f.mkdir()
    shutil.copy(FIX, f / "carousel.json")
    (f / "caption_instagram.md").write_text(caption, encoding="utf-8")
    assert render_carousel.main([str(f / "carousel.json")]) == 0
    meta = {"date": "2026-10-30", "topic": "Tema", "topic_key": "tema-x",
            "primary_url": "https://euraxess.ec.europa.eu/jobs/search", "verified_date": "2026-10-30",
            "type": "research_career", "weekday": "viernes", "category": "programa_red"}
    (f / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    stamp(f)
    return f


def stamp(f: Path) -> None:
    m = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
    m["instagram"] = {"plain_language_check": {"question": validate_post.PLAIN_QUESTION, "answer": "sí",
                                               "reviewer": "prueba",
                                               "checked_text_sha256": validate_carousel.plain_hash(f)}}
    (f / "metadata.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._hist = history.HISTORY
        history.HISTORY = self.tmp / "history.csv"
        history.write_history([])

    def tearDown(self):
        history.HISTORY = self._hist
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fails(self, f: Path) -> list[str]:
        res, _ = validate_carousel.validate(f, NOW, check_linkedin=False)
        return [n for s, n, _ in res if s == "FAIL"]


class TestDedupPorPlataforma(Base):
    def test_fila_antigua_sin_plataforma_es_linkedin(self):
        history.write_history([{"folder": "a", "status": "published", "topic_key": "t",
                                "official_url": "https://x.org/a"}])
        self.assertEqual(len(history.check("https://x.org/a", "t")), 1)
        self.assertEqual(history.check("https://x.org/a", "t", "instagram"), [])

    def test_instagram_no_bloquea_linkedin_ni_al_reves(self):
        f = make_folder(self.tmp)
        history.add(f, "scheduled", platform="instagram", buffer_post_id="ig1")
        self.assertEqual(history.check("https://euraxess.ec.europa.eu/jobs/search", "tema-x"), [])
        self.assertEqual(len(history.check("https://euraxess.ec.europa.eu/jobs/search", "tema-x", "instagram")), 1)
        history.add(f, "scheduled", platform="linkedin", buffer_post_id="li1")  # misma carpeta, otra plataforma
        rows = history.read_history()
        self.assertEqual(sorted(history.row_platform(r) for r in rows), ["instagram", "linkedin"])

    def test_una_fila_por_carpeta_y_plataforma(self):
        f = make_folder(self.tmp)
        history.add(f, "scheduled", platform="instagram", buffer_post_id="ig1")
        history.add(f, "skipped", platform="instagram", reason="x")
        self.assertEqual(len(history.rows_for("instagram")), 1)

    def test_confirmacion_obligatoria(self):
        f = make_folder(self.tmp)
        with self.assertRaises(history.HistoryError):
            history.add(f, "scheduled", platform="instagram")
        with self.assertRaises(history.HistoryError):
            history.add(f, "published", platform="instagram", buffer_post_id="ig1")  # sin external_url
        row = history.add(f, "published", platform="instagram", buffer_post_id="ig1",
                          external_url="https://instagram.com/p/x")
        self.assertEqual(row["platform"], "instagram")

    def test_linkedin_ignora_filas_de_instagram_al_publicar(self):
        f = make_folder(self.tmp)
        history.add(f, "scheduled", platform="instagram", buffer_post_id="ig1")
        self.assertEqual([r for r in history.rows_for("linkedin") if r.get("folder") == f.name], [])

    def test_linkedin_sin_argumentos_nuevos_funciona_como_antes(self):
        f = make_folder(self.tmp)
        with self.assertRaises(history.HistoryError):
            history.add(f, "published", buffer_post_id="x")  # sin linkedin_url
        row = history.add(f, "published", buffer_post_id="x", linkedin_url="https://linkedin.com/p")
        self.assertEqual(history.row_platform(row), "linkedin")


class TestCarrusel(Base):
    def test_cinco_imagenes_1080x1350(self):
        from PIL import Image
        f = make_folder(self.tmp)
        for i in range(1, 6):
            with Image.open(f / f"slide-{i}.png") as im:
                self.assertEqual(im.size, (1080, 1350))
                self.assertEqual(im.format, "PNG")

    def test_render_determinista(self):
        f = make_folder(self.tmp)
        a = json.loads((f / "carousel_render.json").read_text(encoding="utf-8"))
        render_carousel.main([str(f / "carousel.json")])
        b = json.loads((f / "carousel_render.json").read_text(encoding="utf-8"))
        self.assertEqual(a, b)

    def test_esquema_rechaza_menos_diapositivas_y_texto_largo(self):
        spec = json.loads(FIX.read_text(encoding="utf-8"))
        with self.assertRaises(render_carousel.LayoutError):
            render_carousel.render(dict(spec, slides=spec["slides"][:3]))
        long = json.loads(FIX.read_text(encoding="utf-8"))
        long["slides"][0]["items"][0]["text"] = "palabra " * 40
        with self.assertRaises(render_carousel.LayoutError):
            render_carousel.render(long)

    def test_validacion_aprobada(self):
        self.assertEqual(self.fails(make_folder(self.tmp)), [])

    def test_texto_cambiado_tras_revision_bloquea(self):
        f = make_folder(self.tmp)
        (f / "caption_instagram.md").write_text(CAPTION + " Extra.", encoding="utf-8")
        self.assertIn("Lenguaje sencillo: revisión del verificador", self.fails(f))

    def test_imagen_obsoleta_bloquea(self):
        f = make_folder(self.tmp)
        spec = json.loads((f / "carousel.json").read_text(encoding="utf-8"))
        spec["slides"][3]["title"] = "En resumen final"
        (f / "carousel.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        self.assertIn("Imágenes actualizadas", self.fails(f))

    def test_caption_largo_y_sin_verificado_bloquean(self):
        fails = self.fails(make_folder(self.tmp, caption="Hola " * 300 + "\n#a #b #c"))
        self.assertIn("Caption breve", fails)
        self.assertIn("Verificado el", fails)

    def test_siglas_sin_explicar_en_caption_bloquean(self):
        f = make_folder(self.tmp, caption=CAPTION.replace("R1 (quien empieza a investigar)", "MSCA"))
        self.assertIn("Lenguaje sencillo: siglas (texto)", self.fails(f))

    def test_duplicado_solo_en_instagram(self):
        f = make_folder(self.tmp)
        other = self.tmp / "otra"
        other.mkdir()
        (other / "metadata.json").write_text(json.dumps({"topic_key": "tema-x", "topic": "T", "date": "2026-10-28"}),
                                             encoding="utf-8")
        history.add(other, "scheduled", platform="linkedin", buffer_post_id="li9")  # LinkedIn no cuenta
        self.assertNotIn("Duplicados (Instagram)", self.fails(f))
        history.add(other, "scheduled", platform="instagram", buffer_post_id="ig9")
        self.assertIn("Duplicados (Instagram)", self.fails(f))


class TestPayload(Base):
    def approved(self) -> Path:
        f = make_folder(self.tmp)
        (f / "validation_instagram.md").write_text("Decisión: **APROBADA para publicar**", encoding="utf-8")
        return f

    @staticmethod
    def fake_fetch(f: Path):
        def fetch(url, intentos=3, espera=10.0):
            return 200, "image/png", (f / url.rsplit("/", 1)[1]).read_bytes(), ""
        return fetch

    def test_borrador_5_imagenes_automatico_instagram_post(self):
        f = self.approved()
        with mock.patch.object(ppi, "fetch_bytes", self.fake_fetch(f)):
            self.assertEqual(ppi.main([str(f), "--base-url", IMG_BASE, "--draft"]), 0)
        p = json.loads((f / ppi.PAYLOAD).read_text(encoding="utf-8"))
        self.assertEqual(len(p["assets"]), 5)
        self.assertTrue(all(a["image"]["metadata"]["altText"] for a in p["assets"]))
        self.assertEqual(p["schedulingType"], "automatic")
        self.assertEqual(p["metadata"]["instagram"], {"type": "post", "shouldShareToFeed": True})
        self.assertEqual(p["channelId"], "6ae71fe8e29c69a17126342a")
        self.assertTrue(p["saveToDraft"])
        self.assertNotIn("mode", p)

    def test_produccion_bloqueada_mientras_enabled_false(self):
        f = self.approved()
        pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
        with mock.patch.object(ppi, "fetch_bytes", self.fake_fetch(f)):
            rc = ppi.main([str(f), "--base-url", IMG_BASE, "--slot", "--now", "2026-10-30T09:00:00+01:00"])
        self.assertEqual(rc, 0 if pub["instagram"]["enabled"] else 1)

    def test_slot_mismas_horas_que_linkedin(self):
        f = self.approved()
        pub = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
        pub["instagram"]["enabled"] = True
        orig = Path.read_text

        def rt(self_, *a, **k):
            return json.dumps(pub) if self_.name == "publishing.json" else orig(self_, *a, **k)
        with mock.patch.object(ppi, "fetch_bytes", self.fake_fetch(f)), mock.patch.object(Path, "read_text", rt):
            for now, expected in (("2026-10-30T09:00:00+01:00", "2026-10-30T12:30:00+01:00"),   # viernes
                                  ("2026-10-31T08:00:00+01:00", "2026-10-31T11:00:00+01:00")):  # sábado
                self.assertEqual(ppi.main([str(f), "--base-url", IMG_BASE, "--slot", "--now", now]), 0)
                p = json.loads(orig(f / ppi.PAYLOAD, encoding="utf-8"))
                self.assertEqual((p["mode"], p["dueAt"]), ("customScheduled", expected))
                (f / ppi.PAYLOAD).unlink()

    def test_imagen_publica_distinta_bloquea(self):
        f = self.approved()
        good = self.fake_fetch(f)

        def bad(url, intentos=3, espera=10.0):
            if url.endswith("slide-3.png"):
                return 200, "image/png", b"otra cosa", ""
            return good(url)
        with mock.patch.object(ppi, "fetch_bytes", bad):
            self.assertEqual(ppi.main([str(f), "--base-url", IMG_BASE, "--draft"]), 1)

    def test_sin_validacion_aprobada_bloquea(self):
        self.assertEqual(ppi.main([str(make_folder(self.tmp)), "--base-url", IMG_BASE, "--draft"]), 1)


if __name__ == "__main__":
    unittest.main()
