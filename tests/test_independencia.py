"""Independencia de LinkedIn e Instagram, días de publicación y protección de borradores. Sin red."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import history  # noqa: E402
import plan_day  # noqa: E402
import prepare_publish as pp  # noqa: E402
import prepare_publish_instagram as ppi  # noqa: E402
import test_instagram as ti  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
PUB = json.loads((ROOT / "config" / "publishing.json").read_text(encoding="utf-8"))
PUB_ON = json.loads(json.dumps(PUB))
PUB_ON["instagram"]["enabled"] = True
PUB_OFF = json.loads(json.dumps(PUB))
PUB_OFF["instagram"]["enabled"] = False
MIE = datetime(2026, 11, 4, 8, 0, tzinfo=TZ)   # miércoles
LUN = datetime(2026, 11, 2, 8, 0, tzinfo=TZ)   # lunes
MAR = datetime(2026, 11, 3, 8, 0, tzinfo=TZ)   # martes
no_block = lambda folder: False  # noqa: E731


def row(platform: str, status: str, date: str = "2026-11-04", folder: str = "2026-11-04_miercoles_x") -> dict:
    return {"platform": platform, "status": status, "publication_date": date, "folder": folder}


class TestPlanIndependiente(unittest.TestCase):
    def test_sin_historial_ambas_tocan_en_miercoles(self):
        p = plan_day.plan(MIE, PUB_ON, [], no_block)
        self.assertTrue(p["linkedin"]["due"])
        self.assertTrue(p["instagram"]["due"])
        self.assertIsNone(p["instagram"]["reuse_folder"])

    def test_linkedin_ya_publico_instagram_sigue_y_reutiliza(self):
        p = plan_day.plan(MIE, PUB_ON, [row("linkedin", "published")], no_block)
        self.assertFalse(p["linkedin"]["due"])
        self.assertTrue(p["instagram"]["due"])
        self.assertEqual(p["instagram"]["reuse_folder"], "2026-11-04_miercoles_x")

    def test_linkedin_programado_cuenta_como_hecho_pero_instagram_sigue(self):
        p = plan_day.plan(MIE, PUB_ON, [row("linkedin", "scheduled")], no_block)
        self.assertFalse(p["linkedin"]["due"])
        self.assertTrue(p["instagram"]["due"])

    def test_linkedin_fallo_u_omitido_instagram_sigue_con_investigacion_propia(self):
        for status in ("skipped", "draft-test", "deleted"):
            p = plan_day.plan(MIE, PUB_ON, [row("linkedin", status)], no_block)
            self.assertTrue(p["linkedin"]["due"], status)  # LinkedIn puede reintentarse
            self.assertTrue(p["instagram"]["due"], status)
            self.assertIsNone(p["instagram"]["reuse_folder"], status)

    def test_instagram_ya_publico_no_bloquea_linkedin(self):
        p = plan_day.plan(MIE, PUB_ON, [row("instagram", "scheduled")], no_block)
        self.assertTrue(p["linkedin"]["due"])
        self.assertFalse(p["instagram"]["due"])

    def test_fila_antigua_sin_plataforma_es_linkedin(self):
        r = row("", "published")
        del r["platform"]
        p = plan_day.plan(MIE, PUB_ON, [r], no_block)
        self.assertFalse(p["linkedin"]["due"])
        self.assertTrue(p["instagram"]["due"])

    def test_filas_de_otros_dias_no_cuentan(self):
        rows = [row("linkedin", "published", date="2026-10-30"), row("instagram", "published", date="2026-10-30")]
        p = plan_day.plan(MIE, PUB_ON, rows, no_block)
        self.assertTrue(p["linkedin"]["due"] and p["instagram"]["due"])

    def test_lunes_ambas_plataformas(self):
        p = plan_day.plan(LUN, PUB_ON, [], no_block)
        self.assertTrue(p["linkedin"]["due"])
        self.assertTrue(p["instagram"]["due"])

    def test_publicacion_extra_de_hoy_no_bloquea_el_dia_siguiente(self):
        # dos publicaciones extra de Instagram un domingo no cuentan para el lunes ni para ningún otro día
        rows = [row("instagram", "published", date="2026-11-01", folder="2026-11-01_extra_a"),
                row("instagram", "published", date="2026-11-01", folder="2026-11-01_extra_b")]
        p = plan_day.plan(LUN, PUB_ON, rows, no_block)
        self.assertTrue(p["instagram"]["due"])
        self.assertTrue(p["linkedin"]["due"])

    def test_dias_sin_publicacion(self):
        p = plan_day.plan(MAR, PUB_ON, [], no_block)
        self.assertFalse(p["linkedin"]["due"] or p["instagram"]["due"])

    def test_instagram_desactivado_no_toca_aunque_sea_miercoles(self):
        p = plan_day.plan(MIE, PUB_OFF, [], no_block)
        self.assertFalse(p["instagram"]["due"])
        self.assertTrue(p["linkedin"]["due"])

    def test_carpeta_borrador_nunca_se_reutiliza(self):
        p = plan_day.plan(MIE, PUB_ON, [row("linkedin", "published")], lambda f: True)
        self.assertTrue(p["instagram"]["due"])
        self.assertIsNone(p["instagram"]["reuse_folder"])


class TestCalendarioAcordado(unittest.TestCase):
    def test_dias_y_horarios(self):
        cal = PUB["calendar"]
        self.assertEqual(set(cal), {"lunes", "miercoles", "viernes", "sabado"})
        self.assertEqual([cal[d]["publish_time"] for d in ("lunes", "miercoles", "viernes", "sabado")],
                         ["12:30", "12:30", "12:30", "11:00"])
        self.assertEqual(cal["sabado"]["share_now_after"], "10:45")
        self.assertEqual(PUB["calendar_defaults"], {"publish_time": "12:30", "share_now_after": "12:15"})

    def test_instagram_mismos_dias_que_linkedin(self):
        self.assertEqual(PUB["instagram"]["days"], ["lunes", "miercoles", "viernes", "sabado"])
        self.assertEqual(set(PUB["instagram"]["days"]), set(PUB["calendar"]))



class TestCompuertas(ti.Base):
    def approved(self, **meta) -> Path:
        f = ti.make_folder(self.tmp)
        (f / "validation_instagram.md").write_text("Decisión: **APROBADA para publicar**", encoding="utf-8")
        (f / "validation.md").write_text("Decisión: **APROBADA para publicar**", encoding="utf-8")
        m = json.loads((f / "metadata.json").read_text(encoding="utf-8")) if (f / "metadata.json").exists() else {}
        m.update(meta)
        (f / "metadata.json").write_text(json.dumps(m), encoding="utf-8")
        return f

    def run_ig(self, f: Path, *args: str) -> int:
        orig = Path.read_text

        def rt(self_, *a, **k):
            return json.dumps(PUB_ON) if self_.name == "publishing.json" else orig(self_, *a, **k)
        with mock.patch.object(ppi, "fetch_bytes", ti.TestPayload.fake_fetch(f)), mock.patch.object(Path, "read_text", rt):
            return ppi.main([str(f), "--base-url", ti.IMG_BASE, *args])

    def test_instagram_slot_mismos_dias_y_horas_que_linkedin(self):
        f = self.approved()
        self.assertEqual(self.run_ig(f, "--slot", "--now", "2026-11-03T08:00:00+01:00"), 1)   # martes
        self.assertEqual(self.run_ig(f, "--slot", "--now", "2026-11-08T08:00:00+01:00"), 1)   # domingo
        for now, due in (("2026-11-02T08:00:00+01:00", "2026-11-02T12:30:00+01:00"),   # lunes
                         ("2026-11-04T08:00:00+01:00", "2026-11-04T12:30:00+01:00"),   # miércoles
                         ("2026-11-06T08:00:00+01:00", "2026-11-06T12:30:00+01:00"),   # viernes
                         ("2026-11-07T08:00:00+01:00", "2026-11-07T11:00:00+01:00")):  # sábado
            self.assertEqual(self.run_ig(f, "--slot", "--now", now), 0, now)
            p = json.loads((f / ppi.PAYLOAD).read_text(encoding="utf-8"))
            self.assertEqual(p["dueAt"], due)
            (f / ppi.PAYLOAD).unlink()

    def test_instagram_no_depende_de_linkedin_aunque_este_publicado(self):
        f = self.approved()
        history.write_history([{**row("linkedin", "published", folder=f.name), "buffer_post_id": "li1",
                                "linkedin_url": "u"}])
        self.assertEqual(self.run_ig(f, "--slot", "--now", "2026-11-04T08:00:00+01:00"), 0)

    def test_borrador_de_revision_no_se_programa_pero_si_admite_draft(self):
        f = self.approved(do_not_publish=True)
        self.assertEqual(self.run_ig(f, "--slot", "--now", "2026-11-04T08:00:00+01:00"), 1)
        self.assertEqual(self.run_ig(f, "--mode", "shareNow"), 1)
        self.assertEqual(self.run_ig(f, "--draft"), 0)

    def test_linkedin_borrador_de_revision_bloqueado(self):
        f = self.approved(do_not_publish=True)
        (f / "post.png").write_bytes(b"x")
        (f / "caption.md").write_text("Texto", encoding="utf-8")
        with mock.patch.object(pp, "fetch_bytes", return_value=(200, "image/png", b"x", "")):
            rc = pp.main([str(f), "--image-url", "https://x/p.png", "--slot", "--now", "2026-11-04T08:00:00+01:00"])
        self.assertEqual(rc, 1)

    def test_linkedin_slot_rechaza_dias_no_acordados(self):
        f = self.approved()
        (f / "post.png").write_bytes(b"x")
        (f / "caption.md").write_text("Texto", encoding="utf-8")
        with mock.patch.object(pp, "fetch_bytes", return_value=(200, "image/png", b"x", "")):
            rc = pp.main([str(f), "--image-url", "https://x/p.png", "--slot", "--now", "2026-11-03T08:00:00+01:00"])
        self.assertEqual(rc, 1)  # martes

    def test_carpeta_solo_instagram_no_se_publica_en_linkedin(self):
        f = self.approved(platforms=["instagram"])
        (f / "post.png").write_bytes(b"x")
        (f / "caption.md").write_text("Texto", encoding="utf-8")
        with mock.patch.object(pp, "fetch_bytes", return_value=(200, "image/png", b"x", "")):
            rc = pp.main([str(f), "--image-url", "https://x/p.png", "--slot", "--now", "2026-11-04T08:00:00+01:00"])
        self.assertEqual(rc, 1)
        self.assertEqual(self.run_ig(f, "--slot", "--now", "2026-11-04T08:00:00+01:00"), 0)

    def test_historial_rechaza_borrador_de_revision(self):
        f = self.approved(do_not_publish=True)
        for platform in ("linkedin", "instagram"):
            with self.assertRaises(history.HistoryError):
                history.add(f, "scheduled", platform=platform, buffer_post_id="b1")
        history.add(f, "draft-test", platform="instagram")  # los ensayos sí pueden registrarse

    def test_los_dos_borradores_reales_estan_protegidos(self):
        for n in ("eth-esop", "erasmus-mundus-catalogo"):
            meta = json.loads((ROOT / "borradores" / f"2026-11-02_lunes_{n}" / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(meta.get("do_not_publish"), n)
            self.assertTrue(plan_day.folder_blocked(f"2026-11-02_lunes_{n}"), n)


if __name__ == "__main__":
    unittest.main()
