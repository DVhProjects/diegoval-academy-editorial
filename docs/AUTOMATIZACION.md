# Automatización: estado, requisitos y bloqueos

Última revisión: 2026-10-28.

## Arquitectura
```
Rutina en la nube (Claude Code, claude.ai/code/routines)  ── mié y vie, cron 0 6 * * 3,5 (UTC)
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
| Rutina semanal | **ACTIVA** desde 2026-10-28 10:28 CET | `trig_01Np3DtdUEyuYobQKkbePAox` · cron `0 6 * * 3,5` UTC · Sonnet · sólo conector Buffer · primera ejecución 2026-10-30 07:05 CET · https://claude.ai/code/routines/trig_01Np3DtdUEyuYobQKkbePAox |
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
