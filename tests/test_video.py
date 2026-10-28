"""Pruebas del formato vídeo (sin red).

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import history  # noqa: E402
import validate_post  # noqa: E402
import video  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 10, 30, 9, 0, tzinfo=TZ)
VID = "U0cNhCMpANA"
URL = f"https://www.youtube.com/watch?v={VID}"
OFFICIAL = "https://www.daad.de/en/study-and-research-in-germany/"

SUBTITLE_LINES = {
    "es_oficial": "Subtítulos: el vídeo tiene subtítulos en español; actívalos con el icono CC.",
    "es_automatico": "Subtítulos: YouTube ofrece subtítulos automáticos en español (pueden tener errores).",
    "traducible": ("Subtítulos: el vídeo está en inglés; YouTube puede ofrecer traducción automática al español "
                   "(Ajustes > Subtítulos), pero no está garantizada."),
    "no_verificado": "Subtítulos: no verificados; comprueba con el icono CC si hay subtítulos en español.",
}


def caption(state: str, extra: str = "") -> str:
    return (f"Una estudiante explica cómo quedarse en Alemania tras graduarse.\n\nQué aprenderás: los pasos básicos.\n"
            f"Por qué es útil: evita errores de plazo.\nCómo aprovecharlo: toma nota y revisa la web oficial.\n\n"
            f"{SUBTITLE_LINES[state]}\n\nVídeo: {URL}\nWeb oficial: {OFFICIAL}\n\nVerificado el: 2026-10-30.\n{extra}")


def meta(state: str = "traducible", **over) -> dict:
    m = {"date": "2026-10-30", "weekday": "viernes", "type": "research_career", "category": "programa_red",
         "topic": "Quedarse en Alemania tras graduarse", "topic_key": "alemania-tras-graduarse", "primary_url": OFFICIAL,
         "verified_date": "2026-10-30", "buffer_channel_id": "6ae0bdf22f1f5ed648eb92f9", "alt_text": "n/a",
         "status": "draft", "format": "video",
         "video": {"url": URL, "title": "Temiloluwa: How To Stay In Germany After Graduation", "channel": "Study in Germany",
                   "channel_id": "UCJ_7CUHExD_m1KDsxHE4G3w", "published": "2026-10-19", "duration_s": 240,
                   "subtitles": state, "official_evidence_url": OFFICIAL}}
    if state == "no_verificado":
        m["video"]["language"] = "es"  # sin subtítulos verificables sólo vale si el audio está en español
    m.update(over)
    return m


class TestUtilidades(unittest.TestCase):
    def test_video_id_variantes(self):
        for u in (URL, f"https://youtu.be/{VID}", f"https://m.youtube.com/watch?v={VID}&t=5s", f"https://www.youtube.com/shorts/{VID}",
                  f"https://www.youtube.com/embed/{VID}"):
            self.assertEqual(video.video_id(u), VID, u)
        for u in ("https://example.com/watch?v=" + VID, "https://www.youtube.com/@canal", "", "https://youtu.be/corto"):
            self.assertIsNone(video.video_id(u), u)

    def test_subtitulos(self):
        c = video.classify_subtitles
        self.assertEqual(c([{"languageCode": "es", "kind": ""}], True)[0], "es_oficial")
        self.assertEqual(c([{"languageCode": "es-419", "kind": "asr"}], True)[0], "es_automatico")
        self.assertEqual(c([{"languageCode": "en", "kind": "asr"}], True)[0], "traducible")
        self.assertEqual(c([{"languageCode": "en", "kind": "asr"}], False)[0], "no_verificado")
        self.assertEqual(c([], True)[0], "no_verificado")
        # un español automático y otro oficial: manda el oficial
        self.assertEqual(c([{"languageCode": "es", "kind": "asr"}, {"languageCode": "es", "kind": ""}], False)[0], "es_oficial")

    def test_parse_pagina(self):
        html = ('..."captionTracks":[{"baseUrl":"https:\\/\\/x?a=1\\u0026b=2","languageCode":"en","kind":"asr"}],"audioTracks":[]...'
                '"isTranslatable":true "lengthSeconds":"240" "channelId":"UCJ_7CUHExD_m1KDsxHE4G3w" "author":"Study in Germany" '
                '"publishDate":"2026-10-19T09:00:00-07:00"')
        p = video.parse_watch_page(html)
        self.assertEqual(p["tracks"], [{"languageCode": "en", "kind": "asr"}])
        self.assertTrue(p["translatable"])
        self.assertEqual((p["duration_s"], p["published"], p["author"]), (240, "2026-10-19", "Study in Germany"))

    def test_calidad(self):
        base = {"duration_s": 240, "published": "2026-10-19", "title": "t", "channel_id": "UC" + "a" * 22}
        self.assertEqual(video.quality(base, date(2026, 10, 30)), [])
        self.assertTrue(video.quality({**base, "duration_s": 43}, date(2026, 10, 30)))
        self.assertTrue(video.quality({**base, "duration_s": 5000}, date(2026, 10, 30)))
        self.assertTrue(video.quality({**base, "published": "2020-01-01"}, date(2026, 10, 30)))
        self.assertTrue(video.quality({**base, "published": None}, date(2026, 10, 30)))

    def test_inspect_sin_red(self):
        def sin_red(_url):
            raise OSError("sin red")
        r = video.inspect(URL, date(2026, 10, 30), fetch=sin_red)
        self.assertFalse(r["ok"])
        self.assertTrue(r["errors"])
        self.assertFalse(video.inspect("https://example.com/x", date(2026, 10, 30))["ok"])


class TestValidadorVideo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._hist = history.HISTORY
        history.HISTORY = self.tmp / "h.csv"
        history.write_history([])

    def tearDown(self):
        history.HISTORY = self._hist
        shutil.rmtree(self.tmp, ignore_errors=True)

    def folder(self, state="traducible", cap=None, m=None, sources=None) -> Path:
        f = self.tmp / "2026-10-30_viernes_prueba"
        shutil.rmtree(f, ignore_errors=True)
        f.mkdir()
        (f / "caption.md").write_text(cap if cap is not None else caption(state), encoding="utf-8")
        (f / "metadata.json").write_text(json.dumps(m or meta(state)), encoding="utf-8")
        (f / "sources.md").write_text(sources if sources is not None else f"{URL}\n{OFFICIAL}\n", encoding="utf-8")
        return f

    def fails(self, f: Path) -> list[str]:
        res, _ = validate_post.validate(f, NOW, skip_network=True)
        return [n for s, n, _ in res if s == "FAIL"]

    def test_cuatro_estados_validos(self):
        for state in SUBTITLE_LINES:
            self.assertEqual(self.fails(self.folder(state)), [], state)

    def test_promesa_indebida_de_subtitulos(self):
        cap = caption("no_verificado").replace("comprueba con el icono CC si hay subtítulos en español.",
                                               "el vídeo tiene subtítulos en español.")
        self.assertIn("Subtítulos en el texto", self.fails(self.folder("no_verificado", cap=cap)))

    def test_sin_subtitulos_y_sin_espanol_no_vale(self):
        m = meta("no_verificado"); m["video"].pop("language")
        self.assertIn("Utilidad para la audiencia", self.fails(self.folder("no_verificado", m=m)))

    def test_traducible_sin_aviso_de_no_garantizada(self):
        cap = caption("traducible").replace(", pero no está garantizada", "")
        self.assertIn("Subtítulos en el texto", self.fails(self.folder("traducible", cap=cap)))

    def test_falta_linea_subtitulos(self):
        cap = caption("es_oficial").replace(SUBTITLE_LINES["es_oficial"], "")
        self.assertIn("Subtítulos en el texto", self.fails(self.folder("es_oficial", cap=cap)))

    def test_sin_enlace_del_video(self):
        self.assertIn("Enlace del vídeo en el texto", self.fails(self.folder(cap=caption("traducible").replace(URL, ""))))

    def test_video_antiguo_o_corto(self):
        m = meta(); m["video"]["published"] = "2020-05-01"
        self.assertIn("Calidad del vídeo", self.fails(self.folder(m=m)))
        m = meta(); m["video"]["duration_s"] = 43
        self.assertIn("Calidad del vídeo", self.fails(self.folder(m=m)))

    def test_procedencia_no_documentada(self):
        self.assertIn("Procedencia oficial documentada", self.fails(self.folder(sources=f"{URL}\n")))

    def test_png_sobrante_bloquea(self):
        f = self.folder()
        (f / "post.png").write_bytes(b"x")
        self.assertIn("Sin imagen propia", self.fails(f))

    def test_video_duplicado(self):
        history.write_history([{"folder": "otra", "status": "published", "video_url": f"https://youtu.be/{VID}",
                                "publication_date": "2026-10-01", "topic": "x", "topic_key": "otro", "official_url": "https://e.org/x"}])
        self.assertIn("Duplicados", self.fails(self.folder()))

    def test_secciones_obligatorias(self):
        self.assertIn("Estructura del texto (vídeo)", self.fails(self.folder(cap=caption("traducible").replace("Por qué es útil", "Por qué"))))

    def test_historial_guarda_video_url(self):
        f = self.folder()
        row = history.add(f, "skipped", reason="prueba")
        self.assertEqual(row["video_url"], URL)
        self.assertEqual(row["format"], "video")
        self.assertFalse(history.check(f"https://youtu.be/{VID}", None))  # 'skipped' no cuenta como publicado
        history.add(f, "scheduled", buffer_post_id="abc")
        self.assertTrue(history.check(f"https://youtu.be/{VID}", None))


if __name__ == "__main__":
    unittest.main()
