"""Política de repetición de temas (2026-11-02): mismo día en dos redes = permitido; días anteriores = repetición.

Reproduce el caso real del 2 de noviembre de 2026: LinkedIn preparó Eiffel, pero Instagram ya lo había publicado
el 1 de noviembre; después Instagram intentó DAAD, que ya estaba en LinkedIn desde el 31 de octubre. Sin red.
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
sys.path.insert(0, str(ROOT / "tests"))

import history  # noqa: E402
import plan_day  # noqa: E402
import test_sistema as ts  # noqa: E402
import validate_post  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
PUB = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
PUB["instagram"]["enabled"] = True
LUN = datetime(2026, 11, 2, 13, 0, tzinfo=TZ)
EIFFEL = ("https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence", "eiffel-excellence-2027")
DAAD = ("https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/", "daad-buscador-becas")
no_block = lambda folder: False  # noqa: E731


def r(platform: str, date: str, key: tuple[str, str], status: str = "published", folder: str | None = None) -> dict:
    return {"platform": platform, "publication_date": date, "official_url": key[0], "topic_key": key[1],
            "status": status, "topic": key[1], "folder": folder or f"{date}_{platform}_{key[1]}"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._hist = history.HISTORY
        history.HISTORY = self.tmp / "history.csv"
        history.write_history([])

    def tearDown(self):
        history.HISTORY = self._hist
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reps(self, key, platform, date, **kw):
        return history.find_repeats(key[0], key[1], platform, date, **kw)


class TestFindRepeats(Base):
    def test_mismo_dia_en_la_otra_red_esta_permitido(self):
        history.write_history([r("linkedin", "2026-11-04", DAAD)])
        self.assertEqual(self.reps(DAAD, "instagram", "2026-11-04"), [])
        history.write_history([r("instagram", "2026-11-04", DAAD)])
        self.assertEqual(self.reps(DAAD, "linkedin", "2026-11-04"), [])

    def test_dia_anterior_en_la_otra_red_es_repeticion(self):
        history.write_history([r("linkedin", "2026-10-31", DAAD)])
        self.assertEqual(len(self.reps(DAAD, "instagram", "2026-11-02")), 1)
        history.write_history([r("instagram", "2026-11-01", EIFFEL)])
        self.assertEqual(len(self.reps(EIFFEL, "linkedin", "2026-11-02")), 1)  # el caso real de LinkedIn

    def test_misma_plataforma_siempre_es_repeticion(self):
        history.write_history([r("linkedin", "2026-11-02", EIFFEL, folder="a")])
        self.assertEqual(len(self.reps(EIFFEL, "linkedin", "2026-11-02", folder="b")), 1)  # mismo día
        self.assertEqual(len(self.reps(EIFFEL, "linkedin", "2026-11-09")), 1)

    def test_filas_no_publicadas_no_cuentan(self):
        history.write_history([r("instagram", "2026-11-01", EIFFEL, status=s)
                               for s in ("skipped", "draft-test", "deleted")])
        self.assertEqual(self.reps(EIFFEL, "linkedin", "2026-11-02"), [])

    def test_coincide_por_url_o_por_topic_key(self):
        history.write_history([r("instagram", "2026-11-01", EIFFEL)])
        self.assertEqual(len(history.find_repeats(EIFFEL[0] + "/", None, "linkedin", "2026-11-02")), 1)  # barra final
        self.assertEqual(len(history.find_repeats("https://otra.org/x", EIFFEL[1], "linkedin", "2026-11-02")), 1)
        self.assertEqual(history.find_repeats("https://otra.org/x", "otro", "linkedin", "2026-11-02"), [])

    def test_fila_sin_fecha_o_sin_plataforma(self):
        old = {"status": "published", "official_url": EIFFEL[0], "topic_key": EIFFEL[1], "folder": "a"}  # LinkedIn antiguo
        history.write_history([old])
        self.assertEqual(len(self.reps(EIFFEL, "linkedin", "2026-11-02")), 1)
        self.assertEqual(len(self.reps(EIFFEL, "instagram", "2026-11-02")), 1)  # sin fecha: se considera anterior

    def test_la_propia_carpeta_no_cuenta(self):
        history.write_history([r("linkedin", "2026-11-02", EIFFEL, folder="mia")])
        self.assertEqual(self.reps(EIFFEL, "linkedin", "2026-11-02", folder="mia"), [])

    def test_justificacion_permite_dias_anteriores_pero_no_el_mismo_dia_en_la_misma_red(self):
        history.write_history([r("instagram", "2026-11-01", EIFFEL), r("linkedin", "2026-10-20", EIFFEL)])
        self.assertEqual(self.reps(EIFFEL, "linkedin", "2026-11-02", justified=True), [])
        history.write_history([r("linkedin", "2026-11-02", EIFFEL, folder="a")])
        self.assertEqual(len(self.reps(EIFFEL, "linkedin", "2026-11-02", folder="b", justified=True)), 1)

    def test_repeat_justified_exige_texto_suficiente(self):
        self.assertFalse(history.repeat_justified({}))
        self.assertFalse(history.repeat_justified({"repeat_justification": "hay novedades"}))
        self.assertTrue(history.repeat_justified(
            {"repeat_justification": "El plazo cambió el 2026-11-05 por una nueva fase."}))

    def test_recent_lista_todas_las_plataformas(self):
        history.write_history([r("instagram", history.today_stockholm(), EIFFEL), r("linkedin", "2020-01-01", DAAD)])
        self.assertEqual([x["topic_key"] for x in history.recent(30)], [EIFFEL[1]])


class TestPlanDayReutilizacion(Base):
    def test_caso_real_2_nov_eiffel_no_se_reutiliza(self):
        rows = [r("instagram", "2026-11-01", EIFFEL, folder="2026-11-01_extra_eiffel"),
                r("linkedin", "2026-11-02", EIFFEL, folder="2026-11-02_lunes_eiffel")]
        ig = plan_day.plan(LUN, PUB, rows, no_block)["instagram"]
        self.assertTrue(ig["due"])
        self.assertIsNone(ig["reuse_folder"])
        self.assertEqual(len(ig["reuse_rejected"]), 1)
        self.assertIn("investigación nueva", ig["reason"])

    def test_tema_nuevo_de_linkedin_hoy_se_reutiliza_en_instagram(self):
        rows = [r("linkedin", "2026-11-02", DAAD, folder="2026-11-02_lunes_nuevo"),
                r("instagram", "2026-11-01", EIFFEL, folder="2026-11-01_extra_eiffel")]
        ig = plan_day.plan(LUN, PUB, rows, no_block)["instagram"]
        self.assertEqual(ig["reuse_folder"], "2026-11-02_lunes_nuevo")
        self.assertEqual(ig["reuse_rejected"], [])

    def test_linkedin_de_hoy_repetido_pero_otro_programado_si_se_reutiliza(self):
        rows = [r("linkedin", "2026-11-02", EIFFEL, folder="a"), r("linkedin", "2026-11-02", DAAD, folder="b"),
                r("instagram", "2026-11-01", EIFFEL, folder="x")]
        ig = plan_day.plan(LUN, PUB, rows, no_block)["instagram"]
        self.assertEqual(ig["reuse_folder"], "b")


class TestValidarPost(ts.Sandbox):
    """Integra `validate_post.validate` con el historial usando un post real copiado a una carpeta temporal."""

    def post(self, date: str, key: tuple[str, str], **extra) -> Path:
        f = self.copy(ts.BASE_RC, f"{date}_lunes_prueba")
        m = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
        m.update({"date": date, "primary_url": key[0], "topic_key": key[1], **extra})
        (f / "metadata.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        return f

    def dup(self, f: Path, platform: str):
        res, _ = validate_post.validate(f, ts.NOW_OK, True, platform)
        return next(s for s, n, _ in res if n == "Duplicados")

    def test_daad_en_instagram_el_2_nov_se_bloquea_y_el_mismo_dia_no(self):
        f = self.post("2026-11-02", DAAD)
        history.write_history([r("linkedin", "2026-10-31", DAAD)])
        self.assertEqual(self.dup(f, "instagram"), "FAIL")
        history.write_history([r("linkedin", "2026-11-02", DAAD)])
        self.assertEqual(self.dup(f, "instagram"), "PASS")

    def test_eiffel_en_linkedin_el_2_nov_se_bloquea_por_instagram_del_1_nov(self):
        f = self.post("2026-11-02", EIFFEL)
        history.write_history([r("instagram", "2026-11-01", EIFFEL)])
        self.assertEqual(self.dup(f, "linkedin"), "FAIL")

    def test_justificacion_documentada_avisa_en_vez_de_bloquear(self):
        f = self.post("2026-11-02", EIFFEL, repeat_justification="Cambió el plazo oficial el 2026-11-02: nueva fecha límite.")
        history.write_history([r("instagram", "2026-11-01", EIFFEL)])
        self.assertEqual(self.dup(f, "linkedin"), "WARN")


if __name__ == "__main__":
    unittest.main()
