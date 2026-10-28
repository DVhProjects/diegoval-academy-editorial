# Entregable por publicación

Carpeta `posts/AAAA-MM-DD_<miercoles|viernes|lanzamiento>_<slug>/` con:

1. `post.json`: contenido de la imagen (esquema abajo).
2. `post.png`: generado por `scripts/render_post.py` (1080×1350, texto real, fuentes OFL).
3. `caption.md`: texto plano listo para LinkedIn (≤ 1300 caracteres, estilo v2), enlaces oficiales directos y `Verificado el: AAAA-MM-DD`.
4. `sources.md`: URLs específicas, citas literales de los campos verificados, fecha/hora de consulta y alternativas descartadas.
5. `validation.md`: generado por `scripts/validate_post.py` (decisión APROBADA/BLOQUEADA).
6. `metadata.json`: `date`, `weekday`, `type` (`oportunidad`|`research_career`), `category`, `topic`, `topic_key`, `primary_url`, `deadline` (ISO con zona o `null`), `verified_date`, `buffer_channel_id`, `alt_text`, `models_used`, `status` (`draft`|`scheduled`|`published`|`skipped`), `buffer_post_id`.
7. `buffer_payload.json`: generado por `scripts/prepare_publish.py`.

No escribir fechas de cierre si el programa no publica un plazo único. Ninguna URL completa dentro de la imagen: las URLs clicables van en el caption.

## Esquema de `post.json` (v2, compacto)
```json
{
  "series": "miercoles | viernes",
  "kicker": "Oportunidad verificada · Máster con beca",
  "issue": "N.º 004 · 4 de noviembre de 2026",
  "headline": "Máx. 55 caracteres, lenguaje sencillo",
  "dek": "Máx. 110 caracteres: qué es y para quién.",
  "highlight": {"label": "Plazo", "value": "15 dic 2026", "note": "opcional, máx. 60 caracteres"},
  "facts": [{"label": "Cubre", "value": "máx. 48 caracteres"}, {"label": "Pide", "value": "…"}],
  "tip": {"label": "Lo que pocos explican", "text": "Dato práctico verificado, máx. 120 caracteres."},
  "source": "dominio-oficial.org",
  "verified": "AAAA-MM-DD"
}
```
- 2-3 `facts` (no más). Viernes: `highlight` = idea clave (p. ej. `{"label": "La idea clave", "value": "…"}`).
- Caption ≤ 1300 caracteres: gancho · "En corto:" · "Lo que pocos explican:" · "Cómo empezar:" · enlace(s) oficial(es) · `Verificado el:` · 2-3 hashtags.
- `validate_post.py` bloquea si falta `tip` o la línea "Lo que pocos explican" en el caption.

## Formato vídeo (`metadata.format = "video"`)
Carpeta `posts/AAAA-MM-DD_<miercoles|viernes>_<slug>/` con `caption.md`, `sources.md`, `metadata.json`, `validation.md`, `buffer_payload.json`. **Sin `post.json` ni PNG.**

`metadata.json` (además de los campos comunes):
```json
{
  "format": "video",
  "video": {
    "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
    "title": "título tal cual lo publica el canal (oEmbed)",
    "channel": "nombre del canal", "channel_id": "UC...",
    "published": "AAAA-MM-DD", "duration_s": 240,   // null sólo si language = "es" y la nube no pudo leer la página del vídeo
    "subtitles": "es_oficial | es_automatico | traducible | no_verificado",
    "language": "es (opcional; sólo si el audio está en español)",
    "official_evidence_url": "página oficial que enlaza/incrusta el vídeo o su canal (también en sources.md)"
  }
}
```
Se rellena con la salida de `python3 scripts/video.py inspect <url>` (campos `title`, `channel`, `channel_id`, `published`, `duration_s`, `subtitles`).

`caption.md` (≤ 1300 caracteres): gancho · `Qué aprenderás:` · `Por qué es útil:` · `Cómo aprovecharlo:` · línea `Subtítulos:` · `Vídeo: <url>` · `Fuente oficial: <url>` (y plazo/financiación verificados si es una oportunidad) · `Verificado el:` · 2-3 hashtags.

Líneas `Subtítulos:` permitidas (según `video.subtitles`):
- `es_oficial`: "Subtítulos: el vídeo tiene subtítulos en español; actívalos con el icono CC."
- `es_automatico`: "Subtítulos: YouTube ofrece subtítulos automáticos en español (pueden tener errores); actívalos con el icono CC."
- `traducible`: "Subtítulos: el vídeo está en <idioma>; YouTube puede ofrecer traducción automática al español (Ajustes > Subtítulos), pero no está garantizada."
- `no_verificado`: "Subtítulos: no verificados; comprueba con el icono CC si hay subtítulos en español."

Publicación: `python3 scripts/prepare_publish.py posts/<carpeta> --slot` (sin `--image-url`) genera un payload con `metadata.linkedin.linkAttachment` y sin `assets`. Tras `create_post`, `get_post` debe devolver `metadata.linkAttachment` con `title` y `thumbnail`.
