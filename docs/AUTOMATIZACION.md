# Automatización: estado, requisitos y bloqueos

Última revisión: 2026-10-28.

## Arquitectura
```
Rutina en la nube (Claude Code, claude.ai/code/routines)  ── lun, mié, vie y sáb, cron 0 6 * * 1,3,5,6 (UTC)
  │                                                          = 07:00 CET (invierno) / 08:00 CEST (verano)
  ├─ clona github.com/DVhProjects/diegoval-academy-editorial (público)
  ├─ sigue prompts/RUTINA_SEMANAL.md (modelo claude-sonnet-5-5)
  ├─ investiga → post.json → render_post.py → validate_post.py → verificador-convocatorias
  ├─ commit + push del PNG → raw.githubusercontent.com/DVhProjects/diegoval-academy-editorial/<sha>/…/post.png
  ├─ prepare_publish.py (comprueba la URL pública byte a byte) → buffer_payload.json
  └─ conector Buffer de claude.ai → create_post customScheduled 12:30 Europe/Stockholm
```

## Estado de cada pieza

| Pieza | Estado | Evidencia |
|---|---|---|
| Buffer MCP local | OK | OAuth; borrador de prueba creado y borrado (2026-10-27) |
| Repositorio GitHub | OK | `DVhProjects/diegoval-academy-editorial`, público, rama `main`; autoría noreply de DVhProjects; sin datos personales (escaneo de contenido de todos los commits y de metadatos) |
| Imagen pública para Buffer | OK | URL raw por SHA aceptada por Buffer y LinkedIn (1080×1350) |
| Primera publicación | OK | 2026-10-28 10:08 CET, https://www.linkedin.com/feed/update/urn:li:share:7521135820360146947 |
| Conector Buffer en claude.ai | OK | `connector_uuid e6f83204-f84f-4e43-86a3-ec272a29e783` (adjuntado por el servidor al crear la rutina) |
| Rutina semanal | **ACTIVA** desde 2026-10-28 10:28 CET | `trig_01Np3DtdUEyuYobQKkbePAox` · cron `0 6 * * 1,3,5,6` UTC (sábado y lunes añadidos 2026-10-31) · Sonnet · sólo conector Buffer · primera ejecución 2026-10-30 07:05 CET · https://claude.ai/code/routines/trig_01Np3DtdUEyuYobQKkbePAox |
| Prueba en la nube (borrador) | **Parcial** (2026-10-28 10:14 CET) | Python 3.11 OK · render 1080×1350 OK (tras reinstalar Pillow) · Buffer get_channel OK · **git push 403: falta la app Claude de GitHub en DVhProjects** · borrador Buffer no ejecutado. `trig_0126GEUFSjqZUAHgDYq9YZCT` |
| App Claude en GitHub (DVhProjects) | OK | Instalada 2026-10-28; push desde la nube verificado |
| Prueba en la nube, 2.ª ejecución | **OK** (2026-10-28 10:25 CET) | Python 3.11 + Pillow OK · render 1080×1350 · push a `claude/prueba-nube` · URL raw 200 image/png · Buffer: borrador con imagen creado, verificado y borrado. Única incidencia: la nube no puede borrar ramas remotas (se borró desde local) |

## Modo autónomo
**ACTIVO** desde 2026-10-28: rutina persistente confirmada (`enabled=true`, `next_run_at` 2026-10-30T06:05Z) y prueba en la nube superada.
Si una ejecución falla una comprobación, omite la publicación y lo registra en `data/publication_history.csv` (status `skipped`).
Revisión: https://claude.ai/code/routines/trig_01Np3DtdUEyuYobQKkbePAox (historial de ejecuciones). Para pausar: desactivar la rutina allí.
Nota: si la nube no puede hacer push a `main`, usa `claude/publicaciones`; la sesión local debe fusionar esa rama antes de trabajar.

## Por qué no se usa otra cosa
- Cowork / tareas programadas de escritorio: dependen de que el ordenador esté encendido.
- Google Drive: el conector sólo comparte con personas concretas; no da enlaces públicos permanentes.
- Alojadores de imágenes anónimos: sin garantías de permanencia ni de términos de uso.
- El repositorio de la web (`diegoval-academy`, Vercel) no se usa para no provocar despliegues.

## Auditoría 2026-10-28 (prueba integral en la nube, modo borrador)
Rutina de prueba `trig_0165UxSq6qprhzmMMsJxiPd3`, sesión `cse_01HRCw35yLdCamTwzBhhGYwq`, rama `claude/prueba-e2e` (no toca `main`).
- OK en la nube: Python 3.11.17 + dependencias; 19/19 pruebas (`tests/test_sistema.py`); subagentes del repositorio disponibles; Buffer (`get_channel`, `list_posts`, reconciliación, borrador creado/confirmado/borrado); render 1080×1350; push a rama `claude/*`; URL raw 200; `--slot`; imagen inaccesible bloquea; verificación caducada bloquea; `published` sin ids da error; idempotencia habría detenido la publicación del día.
- **BLOQUEO**: la red del entorno `Default` no resuelve dominios oficiales (`marie-sklodowska-curie-actions.ec.europa.eu`, `rea.ec.europa.eu`, `euraxess.ec.europa.eu`: ENOTFOUND). Sin acceso a fuentes primarias la rutina termina en `skipped` (comportamiento correcto, pero no publica). Requiere que el propietario amplíe el acceso de red del entorno en claude.ai/code.
- El servidor `buffer` de `.mcp.json` falla en la nube (403 del proxy); se usa el conector `Buffer` de claude.ai.
- No verificado aún: push a `main` desde la nube (hay alternativa `claude/publicaciones`).

## Diagnóstico de red en la nube (2026-10-28 12:25 UTC, rutina `trig_01BX4twh16osgvWibzw8Uajk`, sesión `cse_01HRCw36irGZd3j8dYxEvFaJ`)
- Accesible: sólo `raw.githubusercontent.com` (HTTP 200).
- Bloqueados (proxy: `Tunnel connection failed: 403 Forbidden`; WebFetch: `ENOTFOUND`): mundusmapp.org, euroculturemaster.eu, todo `*.europa.eu` (MSCA, EURAXESS, research-and-innovation, REA, erasmus-plus), epfl.ch, daad.de, studyinnl.org, chevening.org y hasta example.com.
- Conclusión: el entorno `Default` tiene acceso de red restringido y no incluye las fuentes oficiales. Las rutinas no pueden cambiarlo (la API de rutinas no expone la configuración del entorno): lo cambia el propietario en claude.ai/code. Mientras tanto la rutina termina en `skipped` ("red de la nube sin acceso a <dominio>") sin publicar.
- Tras cambiarlo hay que repetir la prueba integral en borrador (`claude/prueba-*`) antes de dar por validado el sistema.

## Formato vídeo: pruebas y límites (2026-10-28)
- Buffer: un borrador con `metadata.linkedin.linkAttachment` (enlace de YouTube, sin imágenes) devolvió `linkAttachment` con título, descripción y miniatura. Es la vista previa que Buffer genera; el aspecto final en LinkedIn sólo se confirma con la primera publicación real (el enlace también va en el texto como respaldo).
- Nube (diagnóstico `cse_01HRCw39jqtMGQJSrzT7Y3Nf`): `watch?v=` y `m.youtube.com` → HTTP 429; `/embed/` y `youtube-nocookie` → 200 pero sin duración/subtítulos/fecha; `oembed` → 200 (título, canal, miniatura); RSS del canal → 200 (fecha y descripción); `timedtext` → vacío; Data API sin clave → 403. Consecuencia: desde la nube no se pueden verificar duración ni subtítulos; modo limitado = sólo vídeos en español (ver `CLAUDE.md`).
- Local (Windows) la inspección completa funciona (duración, fecha, subtítulos, traducción automática).
- El aviso "MCP buffer requires authentication" de las sesiones en la nube se refiere al servidor `buffer` de `.mcp.json` (sólo local); el conector `Buffer` de claude.ai funciona (comprobado con `get_channel` y `list_posts`).
- Opcional (no aplicado, requiere acción del propietario): una clave gratuita de la YouTube Data API v3 como variable del entorno permitiría leer la duración y si hay subtítulos (no su idioma).

## Estado de validación (2026-10-28 16:40 CET)
| Comprobación | Resultado |
|---|---|
| Red de la nube (entorno Default en acceso completo) | OK (EURAXESS da 403 antirrobots; YouTube bloquea la página del vídeo) |
| Prueba integral miércoles, imagen, borrador | OK (ETH ESOP; verificador aprobó; borrador creado/borrado) |
| Prueba integral viernes, imagen, borrador | OK (COST; el verificador rechazó la 1.ª versión, corregida) |
| Prueba integral vídeo, nube, borrador (E2E 5) | OK con 2 fallos hallados y corregidos (canal erróneo, página 200 sin datos); vista previa con título y miniatura; `assets` vacío; historial con `format`/`video_url`; prueba negativa (vídeo en inglés) bloqueada |
| `video.py inspect` en la nube, 5 repeticiones | Estable (modo `feed`) |
| Pruebas automáticas | 58 OK en local (Windows) y en la nube |
| Buffer en la nube | OK con el conector `mcp__Buffer__*` |
| Rutina semanal | Activa; primera ejecución programada 2026-10-30 06:05 UTC |
| **No verificado** | Ejecución real programada por el planificador con publicación real; elección autónoma entre vídeo e imagen sin vídeo sugerido; push a `main` desde la nube; aspecto final de la tarjeta de vídeo en LinkedIn |

## Cambios 2026-10-31
- Sábado añadido: guía práctica (`educativo`) a las 11:00 Europe/Stockholm (`config/publishing.json` → `calendar.sabado`; `prepare_publish.py --slot` usa la hora de cada día). Rutina `trig_01Np3DtdUEyuYobQKkbePAox` actualizada a `0 6 * * 3,5,6` UTC, mismo modelo (Sonnet), mismo conector Buffer.
- Lenguaje sencillo obligatorio en `validate_post.py`: siglas sin explicar, palabras burocráticas o calcos, frases > 32 palabras y `metadata.plain_language_check` (respuesta «sí» del verificador sobre el texto exacto, con hash) bloquean la publicación. 65 pruebas OK en local.
- Buffer comprobado: sin publicaciones programadas, en envío, en borrador ni con error en el canal (sin conflictos).
- Lunes añadido (variado, 12:30): uno de los tres tipos, alternando. Rutina a `0 6 * * 1,3,5,6` UTC.
- Primera guía de sábado publicada a mano el 2026-10-31 (DAAD, shareNow).
- **No verificado**: primeras ejecuciones automáticas de lunes (2026-11-02) y sábado (2026-11-07).

## Instagram (2026-11-01)
- Canal: `config/instagram_channel.json` (diegovalacademy, Buffer). Publicación en modo automático (`schedulingType: automatic`; nunca «Notify Me»), mismos días y horas que LinkedIn (lunes 12:30, miércoles 12:30, viernes 12:30, sábado 11:00; Europe/Stockholm).
- Estado: `instagram.enabled=false` en `config/publishing.json` hasta validar el diseño y la integración con `main`; después, comprobar la rutina completa en la nube y activar con autorización del propietario.
- Reels: sólo originales o con licencia adecuada; sin descargar vídeos de terceros.
- Borradores de revisión (no publicados): LinkedIn `6ae728f2f0984eef33624a55` (ETH ESOP) e Instagram `6ae728fd21c807e9d5b7e5b7` (carrusel Erasmus Mundus). No se programa nada para el lunes 2026-11-02.

## Cambios 2026-11-02 — política de repetición LinkedIn/Instagram
- Incidente: el lunes 2026-11-02 LinkedIn preparó Eiffel (ya publicado en Instagram el 11-01 como extra) e Instagram intentó DAAD (publicado en LinkedIn el 10-31), `validate_post.py` lo bloqueó comparándolo con el historial de LinkedIn y la rutina omitió Instagram sin buscar otro tema.
- Corregido: `history.find_repeats` única; mismo día en dos redes permitido; temas de días anteriores bloqueados en cualquier plataforma (salvo `repeat_justification`); `validate_post.py --platform`; `plan_day.py` devuelve `reuse_rejected`; `history.py check --date` y `recent`; la rutina exige buscar de nuevo (≥ 3 rondas) antes de omitir; reconciliación de Buffer también para Instagram.
- Pruebas: `tests/test_repeticion.py` (reproduce el caso real) y ajustes en `tests/test_instagram.py`; 124 pruebas OK en local.
- Verificación en la nube: ver el apartado siguiente (se completa tras la ejecución).

## Vídeos, entrevistas y Reels — estado (2026-11-02)
**Ya existía (LinkedIn, vídeo-enlace "opción B"):** `video.py inspect/feed`, validación en vivo en `validate_post.py` (procedencia, 90-1200 s, ≤ 24 meses, subtítulos sin promesas falsas), `prepare_publish.py` con `linkAttachment`, paso 3b de la rutina y `tests/test_video.py`. No se tocó salvo la frase opcional «No olvides activar los subtítulos en español», solo con subtítulos comprobados (`es_oficial`/`es_automatico`).
**Añadido (solo lo que faltaba):**
| Pieza | Qué hace |
|---|---|
| `scripts/render_reel.py` | Reel original 1080×1920 (9:16), 30 fps, H.264 + AAC en silencio, desde el MISMO `carousel.json` (mismos textos ya revisados). Texto que aparece poco a poco, fundido entre escenas, barra de progreso, zona segura de Instagram. Falla en vez de recortar si el texto no cabe (entonces: carrusel). |
| `scripts/validate_reel.py` | Exige el carrusel aprobado; huellas del MP4; formato real leído con FFmpeg; duración 15-90 s; letra ≥ 38 px; **fotogramas decodificados** sin contenido en las zonas que tapa Instagram; sin textos fuera de `carousel.json`; el caption no promete audio ni subtítulos; decisión de formato registrada. |
| `scripts/prepare_publish_reel.py` | Payload de Buffer (`metadata.instagram.type=reel`, vídeo, miniatura); URL pública idéntica byte a byte; un tema una sola vez en Instagram; **solo `--draft` mientras `instagram.reels.enabled=false`**. |
| `requirements-video.txt` | `imageio-ffmpeg` (FFmpeg gratuito dentro de un paquete de Python; no hace falta instalar nada en el sistema). |
| `validate_post.py` | Arreglo: las diapositivas `slide-N.png` del carrusel ya no cuentan como «más de una imagen» de LinkedIn. |
**Prueba en borrador (2026-11-02, equipo local):** Reel de 61,3 s / 1,4 MB renderizado en 22 s; `validate_reel.py` APROBADA (12 comprobaciones); borrador en el canal de Instagram de Buffer aceptado como `reel`, vídeo `video/mp4` de 61 300 ms, miniatura generada y legible; borrador borrado y rama de pruebas eliminada. No se publicó nada.
**Sin verificar todavía (por eso la publicación automática de Reels sigue APAGADA):** que el renderizado con FFmpeg funcione en el entorno de la nube; que Instagram acepte el primer Reel real publicado (Buffer solo valida el borrador); cómo se ve y se comporta en un móvil real (retención, recorte de interfaz). Antes de activar: ejecución de prueba en la nube con `requirements-video.txt` y revisión de un borrador por el propietario.
