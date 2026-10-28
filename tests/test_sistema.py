"""Pruebas del sistema editorial (sin red salvo las marcadas, sin tocar data/ real).

Ejecutar desde la raíz del repositorio:
    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import history  # noqa: E402
import prepare_publish  # noqa: E402
import render_post  # noqa: E402
import validate_post  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
BASE_RC = ROOT / "posts" / "2026-10-28_research-career_suelos-tesis"
BASE_OP = ROOT / "posts" / "2026-10-28_oportunidad_euroculture"
NOW_OK = datetime(2026, 10, 28, 9, 0, tzinfo=TZ)


class Sandbox(unittest.TestCase):
    """Copia una carpeta de post y un historial vacío a un directorio temporal."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._hist = history.HISTORY
        history.HISTORY = self.tmp / "history.csv"
        history.write_history([])

    def tearDown(self):
        history.HISTORY = self._hist
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, base: Path, name: str | None = None) -> Path:
        dst = self.tmp / (name or base.name)
        shutil.copytree(base, dst)
        return dst

    def failures(self, folder: Path, now: datetime = NOW_OK) -> list[str]:
        results, _ = validate_post.validate(folder, now, skip_network=True)
        return [n for s, n, _ in results if s == "FAIL"]


class TestValidacion(Sandbox):
    def test_post_valido_aprueba(self):
        self.assertEqual(self.failures(self.copy(BASE_RC)), [])

    def test_convocatoria_caducada_bloquea(self):
        f = self.copy(BASE_OP)
        fails = self.failures(f, datetime(2027, 1, 12, 9, 0, tzinfo=TZ))
        self.assertIn("Plazo", fails)

    def test_verificacion_de_otro_dia_bloquea(self):
        fails = self.failures(self.copy(BASE_RC), datetime(2026, 10, 30, 9, 0, tzinfo=TZ))
        self.assertIn("Verificación del día", fails)

    def test_duplicado_bloquea(self):
        f = self.copy(BASE_RC)
        meta = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
        history.write_history([{"folder": "otra", "status": "published", "topic_key": meta["topic_key"],
                                "official_url": "https://example.org/x", "publication_date": "2026-10-01", "topic": "x"}])
        self.assertIn("Duplicados", self.failures(f))

    def test_sin_tip_bloquea(self):
        f = self.copy(BASE_RC)
        spec = json.loads((f / "post.json").read_text(encoding="utf-8"))
        spec.pop("tip")
        (f / "post.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        self.assertIn("Estilo compacto (v2)", self.failures(f))

    def test_caption_largo_bloquea(self):
        f = self.copy(BASE_RC)
        (f / "caption.md").write_text((f / "caption.md").read_text(encoding="utf-8") + "x" * 400, encoding="utf-8")
        self.assertIn("Longitud del texto", self.failures(f))

    def test_canal_incorrecto_bloquea(self):
        f = self.copy(BASE_RC)
        meta = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
        meta["buffer_channel_id"] = "000000000000000000000000"
        (f / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertIn("Canal Buffer", self.failures(f))

    def test_oportunidad_nueva_exige_politica_de_seleccion(self):
        f = self.copy(BASE_OP)
        meta = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
        meta["date"] = "2026-11-04"
        (f / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        fails = self.failures(f)
        self.assertIn("Evidencia de popularidad", fails)
        self.assertIn("Por qué es conocida", fails)


class TestHistorial(Sandbox):
    def test_publicado_exige_confirmacion_de_buffer(self):
        f = self.copy(BASE_RC)
        with self.assertRaises(history.HistoryError):
            history.add(f, "published", buffer_post_id="abc")  # sin linkedin_url
        with self.assertRaises(history.HistoryError):
            history.add(f, "scheduled")  # sin buffer_post_id

    def test_skipped_sin_metadata(self):
        f = self.tmp / "2026-10-30_viernes_fallo"
        f.mkdir()
        row = history.add(f, "skipped", reason="ninguna candidata verificable")
        self.assertEqual(row["status"], "skipped")
        self.assertEqual(row["publication_date"], "2026-10-30")

    def test_reconciliacion_desde_buffer(self):
        history.reconcile("idbuffer1", "scheduled", date="2026-10-30", topic="Tema")
        history.reconcile("idbuffer1", "published", linkedin_url="https://www.linkedin.com/feed/update/x")
        rows = history.read_history()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "published")


class TestHora(unittest.TestCase):
    PUB = {"timezone": "Europe/Stockholm", "publish_time": "12:30", "share_now_after": "12:15"}

    def test_invierno_cet(self):
        p = prepare_publish.slot_payload(datetime(2026, 10, 30, 7, 5, tzinfo=TZ), self.PUB)
        self.assertEqual(p, {"mode": "customScheduled", "dueAt": "2026-10-30T12:30:00+01:00"})

    def test_verano_cest(self):
        p = prepare_publish.slot_payload(datetime(2027, 4, 2, 8, 5, tzinfo=TZ), self.PUB)
        self.assertEqual(p["dueAt"], "2027-04-02T12:30:00+02:00")

    def test_dia_del_cambio_de_hora(self):
        p = prepare_publish.slot_payload(datetime(2027, 3, 28, 8, 5, tzinfo=TZ), self.PUB)
        self.assertEqual(p["dueAt"], "2027-03-28T12:30:00+02:00")

    def test_tarde_usa_sharenow(self):
        p = prepare_publish.slot_payload(datetime(2026, 10, 30, 12, 20, tzinfo=TZ), self.PUB)
        self.assertEqual(p, {"mode": "shareNow"})


class TestPublicacion(Sandbox):
    def test_carpeta_ya_publicada_no_se_repite(self):
        f = self.copy(BASE_RC)
        history.write_history([{"folder": f.name, "status": "published", "buffer_post_id": "x", "linkedin_url": "y"}])
        rc = prepare_publish.main([str(f), "--image-url", "https://example.invalid/a.png", "--slot", "--retries", "1"])
        self.assertEqual(rc, 1)

    def test_imagen_inaccesible_bloquea(self):  # usa red: URL inexistente en GitHub
        f = self.copy(BASE_RC)
        url = "https://raw.githubusercontent.com/DVhProjects/diegoval-academy-editorial/0000000000000000000000000000000000000000/no.png"
        rc = prepare_publish.main([str(f), "--image-url", url, "--slot", "--retries", "1"])
        self.assertEqual(rc, 1)
        self.assertFalse((f / "buffer_payload.json").exists() and
                         "no.png" in (f / "buffer_payload.json").read_text(encoding="utf-8"))


class TestImagen(Sandbox):
    def test_render_1080x1350(self):
        f = self.copy(BASE_RC)
        rep = render_post.render(json.loads((f / "post.json").read_text(encoding="utf-8")), f / "t.png")
        self.assertEqual(tuple(rep["size"]), (1080, 1350))
        self.assertGreaterEqual(rep["min_font_px"], render_post.MIN_ANY)

    def test_texto_imposible_falla(self):
        spec = json.loads((BASE_RC / "post.json").read_text(encoding="utf-8"))
        spec["tip"]["text"] = "palabra " * 120
        with self.assertRaises(render_post.LayoutError):
            render_post.render(spec, self.tmp / "t.png")


if __name__ == "__main__":
    unittest.main()
