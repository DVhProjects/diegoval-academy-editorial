# Automatización: estado, requisitos y bloqueos

Última revisión: 2026-10-27.

## Arquitectura
```
Rutina en la nube (Claude Code, claude.ai/code/routines)  ── mié y vie, 06:00 UTC (07:00 CET / 08:00 CEST)
  ├─ clona el repositorio GitHub del proyecto
  ├─ sigue prompts/RUTINA_SEMANAL.md (modelo claude-sonnet-5-5)
  ├─ investiga → post.json → render_post.py → validate_post.py → verificador independiente
  ├─ commit + push del PNG → URL pública raw.githubusercontent.com/<owner>/<repo>/<sha>/…/post.png
  ├─ prepare_publish.py (comprueba la URL pública byte a byte) → buffer_payload.json
  └─ conector Buffer (claude.ai) → create_post customScheduled 12:30 Europe/Stockholm
```

## Estado de cada pieza

| Pieza | Estado | Evidencia |
|---|---|---|
| Buffer MCP local (este equipo) | OK | OAuth completado; `get_account`, `list_channels`, `get_channel` correctos; borrador de prueba creado y borrado (2026-10-27 16:41 CET) |
| Generador de imagen | OK | `render_post.py` (Pillow + fuentes OFL incluidas en el repo, sin dependencias de Windows) |
| Validador + historial | OK | Pruebas positivas y negativas (plazo vencido, verificación caducada, duplicado) |
| Rutinas en la nube | Disponible | `RemoteTrigger list` responde; entorno `Default (anthropic_cloud)`; 0 rutinas creadas |
| **Repositorio GitHub** | **FALTA** | El proyecto no estaba en git; una rutina en la nube sólo ve lo que está en GitHub |
| **Alojamiento público de la imagen** | **FALTA** | Buffer sólo acepta imágenes por URL pública permanente (no hay subida de archivos en su API) |
| **Conector Buffer en claude.ai** | **FALTA** | Buffer está configurado sólo en `.mcp.json` local; las rutinas sólo usan conectores de claude.ai |

## Lo que necesita hacer el propietario (una sola vez, sin coste)
1. **GitHub**: crear un repositorio **público** vacío (p. ej. `diegoval-academy`) en https://github.com/new y darme su URL. Público es necesario para que Buffer pueda descargar la imagen; el repositorio no contiene secretos.
   - Alternativa si no quieres que el código sea público: repositorio privado para el sistema + repositorio público sólo para imágenes (más complejo).
2. Instalar la app de GitHub de Claude en ese repositorio (lo pide claude.ai/code al crear la rutina) para que la rutina pueda hacer push.
3. **Buffer en claude.ai**: https://claude.ai/customize/connectors → añadir conector personalizado `https://mcp.buffer.com/mcp` → autorizar con OAuth (mismo usuario de Buffer).
4. Confirmar entonces y crearé la rutina, la ejecutaré una vez en modo borrador y sólo después la daré por activa.

## Por qué no se usa otra cosa
- Cowork / tareas programadas de escritorio: dependen de que el ordenador esté encendido → no cumplen el requisito.
- Google Drive (conector disponible): la herramienta sólo comparte con personas concretas; no permite enlaces públicos permanentes que Buffer pueda descargar.
- Alojadores de imágenes anónimos: sin garantías de permanencia ni de términos de uso; se descartan.

## Modo autónomo
NO activo. Se considerará activo sólo cuando: (a) exista la rutina persistente, (b) una ejecución de prueba en la nube haya completado el ciclo en modo borrador, y (c) el primer miércoles programado se haya verificado en Buffer.
