# DiegoVal Academy — instrucciones para Codex

Las reglas del proyecto (propósito, aislamiento, política editorial, verificación, formato y Buffer) están en `CLAUDE.md` y son obligatorias también para Codex. Léelo antes de cualquier cambio; no se duplican aquí.

## Papel de Codex en este proyecto
- Mantenimiento de código: `scripts/*.py`, plantilla de imagen, validaciones y pruebas.
- Codex NO publica en Buffer, NO elige temas editoriales y NO modifica `config/buffer_channel.json`.
- Sólo este directorio; nunca configuración global (`~/.codex`) ni otros proyectos. Sin APIs de pago.

## Nivel de esfuerzo (`model_reasoning_effort`)
Usa el nivel más bajo que resuelva bien la tarea. Por defecto el proyecto fija `medium` en `.codex/config.toml`.

| Nivel | Cuándo | Cómo |
|---|---|---|
| `low` | cambios pequeños, textos, mantenimiento | `codex -c model_reasoning_effort="low"` |
| `medium` | plantillas, automatización, Python, comprobaciones habituales | por defecto |
| `high` | arquitectura compleja, depuración difícil, errores persistentes | `codex -c model_reasoning_effort="high"` |
| `xhigh` | evitar; sólo con necesidad técnica demostrada y anotada en `docs/MODELOS.md` | `codex -c model_reasoning_effort="xhigh"` |

Desde Claude Code (plugin oficial de Codex): `/codex:rescue --effort low|medium|high <tarea>`.

## Comprobación obligatoria tras cambiar código
```
python scripts/render_post.py posts/2026-10-28_miercoles_mundus-mapp-2027/post.json --out %TEMP%/prueba.png
python scripts/validate_post.py posts/2026-10-28_miercoles_mundus-mapp-2027 --skip-network --now 2026-10-28T09:00:00+01:00
```
Un cambio que rompa la validación, el tamaño 1080×1350 o la legibilidad de la imagen no se acepta.
