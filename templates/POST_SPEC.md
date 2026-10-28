# Entregable por publicación

Carpeta `posts/AAAA-MM-DD_<miercoles|viernes|lanzamiento>_<slug>/` con:

1. `post.json`: contenido de la imagen (esquema abajo).
2. `post.png`: generado por `scripts/render_post.py` (1080×1350, texto real, fuentes OFL).
3. `caption.md`: texto plano listo para LinkedIn (≤ 3000 caracteres), enlaces oficiales directos y `Verificado el: AAAA-MM-DD`.
4. `sources.md`: URLs específicas, citas literales de los campos verificados, fecha/hora de consulta y alternativas descartadas.
5. `validation.md`: generado por `scripts/validate_post.py` (decisión APROBADA/BLOQUEADA).
6. `metadata.json`: `date`, `weekday`, `type` (`oportunidad`|`research_career`), `category`, `topic`, `topic_key`, `primary_url`, `deadline` (ISO con zona o `null`), `verified_date`, `buffer_channel_id`, `alt_text`, `models_used`, `status` (`draft`|`scheduled`|`published`|`skipped`), `buffer_post_id`.
7. `buffer_payload.json`: generado por `scripts/prepare_publish.py`.

No escribir fechas de cierre si el programa no publica un plazo único. Ninguna URL completa dentro de la imagen: las URLs clicables van en el caption.

## Esquema de `post.json`
```json
{
  "series": "miercoles | viernes",
  "kicker": "Oportunidad verificada · Máster con beca",
  "issue": "N.º 002 · 28 de octubre de 2026",
  "headline": "Titular de 2 líneas idealmente",
  "dek": "Entradilla de 1-2 frases para principiantes.",
  "highlight": {"label": "Plazo", "value": "1 dic 2026 · 23:59 CET", "note": "opcional"},
  "facts": [{"label": "Beca", "value": "…"}, {"label": "Quién", "value": "…"}, {"label": "…", "value": "…"}],
  "action": {"label": "Primer paso", "text": "…"},
  "source": "dominio-oficial.org",
  "verified": "AAAA-MM-DD"
}
```
Viernes: `highlight` puede ser el dato clave de la evidencia (p. ej., `{"label": "Dato clave", "value": "…"}`); `facts` = 3-5 puntos con fuente en el caption.
