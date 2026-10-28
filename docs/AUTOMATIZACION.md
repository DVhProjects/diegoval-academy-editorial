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
| Rutina semanal | Creada, **DESACTIVADA** | `trig_01Np3DtdUEyuYobQKkbePAox`, sólo conector Buffer (mínimo privilegio) |
| Prueba en la nube (borrador) | **Parcial** (2026-10-28 10:14 CET) | Python 3.11 OK · render 1080×1350 OK (tras reinstalar Pillow) · Buffer get_channel OK · **git push 403: falta la app Claude de GitHub en DVhProjects** · borrador Buffer no ejecutado. `trig_0126GEUFSjqZUAHgDYq9YZCT` |
| **App Claude en GitHub (DVhProjects)** | **FALTA** | Instalar en https://github.com/apps/claude/installations/select_target con la cuenta DVhProjects, sólo para `diegoval-academy-editorial` |

## Modo autónomo
Se activa (enabled=true en la rutina semanal) sólo si la prueba en la nube completa: instalación de dependencias, render, push, URL pública y borrador en Buffer creado y borrado.

## Por qué no se usa otra cosa
- Cowork / tareas programadas de escritorio: dependen de que el ordenador esté encendido.
- Google Drive: el conector sólo comparte con personas concretas; no da enlaces públicos permanentes.
- Alojadores de imágenes anónimos: sin garantías de permanencia ni de términos de uso.
- El repositorio de la web (`diegoval-academy`, Vercel) no se usa para no provocar despliegues.
