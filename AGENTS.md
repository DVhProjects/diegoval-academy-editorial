# DiegoVal Academy — instrucciones para Codex

Las reglas del proyecto (propósito, aislamiento, política editorial, verificación, formato y Buffer) están en `CLAUDE.md` y son obligatorias también para Codex. Léelo antes de cualquier cambio; no se duplican aquí.

## Papel de Codex en este proyecto (especialista técnico)
- SÍ: crear/mejorar `scripts/*.py`, la plantilla 1080×1350 y `render_post.py`; validaciones de texto, imagen, enlaces y fechas; pruebas unitarias e de integración; corregir errores de código y automatización; estructura y reproducibilidad del repositorio.
- NO (de forma rutinaria): buscar becas, elegir temas, redactar captions habituales, publicar en LinkedIn/Buffer, repetir verificaciones ya hechas por Claude, modificar `config/buffer_channel.json`.
- No se usa "porque está disponible": sólo cuando haya una tarea técnica concreta. La rutina semanal en la nube no depende de Codex.
- Sólo este directorio; nunca configuración global (`~/.codex`) ni otros proyectos. Sin APIs de pago.

## Nivel de esfuerzo (`model_reasoning_effort`)
Usa el nivel más bajo que resuelva bien la tarea; nunca `high` si `medium` basta. Por defecto el proyecto fija `medium` en `.codex/config.toml`.

| Nivel | Cuándo | Cómo |
|---|---|---|
| `low` | cambios pequeños, textos, mantenimiento | `codex -c model_reasoning_effort="low"` |
| `medium` | plantillas, automatización, Python, comprobaciones habituales | por defecto |
| `high` | arquitectura compleja, depuración difícil, errores persistentes | `codex -c model_reasoning_effort="high"` |
| `xhigh` / `max` / `ultra` | **prohibido en este proyecto** | — |

Desde Claude Code (plugin oficial de Codex): `/codex:rescue --effort low|medium|high <tarea>`.

## Comprobación obligatoria tras cambiar código
```
python scripts/render_post.py posts/2026-10-28_miercoles_mundus-mapp-2027/post.json --out %TEMP%/prueba.png
python scripts/validate_post.py posts/2026-10-28_miercoles_mundus-mapp-2027 --skip-network --now 2026-10-28T09:00:00+01:00
```
Un cambio que rompa la validación, el tamaño 1080×1350 o la legibilidad de la imagen no se acepta.
