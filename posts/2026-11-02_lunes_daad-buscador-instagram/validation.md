# Validación — 2026-11-02_lunes_daad-buscador-instagram

Ejecutado: 2026-11-02T07:16:35+01:00
Decisión: **BLOQUEADA: no publicar**

| Estado | Comprobación | Detalle |
|---|---|---|
| PASS | Archivos obligatorios | imagen: post.json, post.png, caption.md, sources.md, metadata.json |
| PASS | Metadatos | campos obligatorios presentes |
| FAIL | Imagen | tamaño=(1080, 1350) formato=PNG pngs=6 (se espera 1 PNG (1080, 1350)) |
| PASS | Canal Buffer | DiegoVal Academy (6ae0bdf22f1f5ed648eb92f9) |
| PASS | Verificación del día | 2026-11-02 |
| PASS | Longitud del texto | 1174/1300 caracteres |
| PASS | Fecha visible en el texto | Verificado el: 2026-11-02 |
| PASS | Marcadores pendientes | ninguno |
| PASS | Enlaces documentados en sources.md | 1 enlaces |
| PASS | Enlace principal en el texto | https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/ |
| PASS | Lo que pocos explican | presente en imagen y texto |
| PASS | Sin URLs en la imagen | sólo dominio de la fuente |
| PASS | Lenguaje sencillo: siglas (texto) | todas explicadas o ninguna |
| PASS | Lenguaje sencillo: palabras difíciles (texto) | sin burocracia ni calcos detectados |
| PASS | Lenguaje sencillo: siglas (imagen) | todas explicadas o ninguna |
| PASS | Lenguaje sencillo: palabras difíciles (imagen) | sin burocracia ni calcos detectados |
| PASS | Lenguaje sencillo: frases largas | todas ≤ 32 palabras |
| FAIL | Lenguaje sencillo: revisión del verificador | falta metadata.plain_language_check con la pregunta exacta, answer 'sí', reviewer y checked_text_sha256 (python3 scripts/validate_post.py <carpeta> --plain-hash) |
| FAIL | Duplicados | ya publicado: [('2026-10-31', 'Cómo usar el buscador de becas del DAAD para estudiar en Alemania')] |
| PASS | Enlace accesible | 200 https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/ |
