# DiegoVal Academy — Opportunity Radar

Proyecto exclusivo para creación de contenido sobre becas y oportunidades académicas en Europa.

## Resultado esperado
- Miércoles: 1 imagen vertical (1080×1350) y 1 texto detallado con enlaces oficiales sobre una oportunidad vigente.
- Viernes: 1 imagen vertical y 1 texto sobre tendencias, ideas de investigación o preparación para PhD.
- Claude decide los temas semanalmente; el propietario no selecciona ni redacta contenidos.
- Se usa LinkedIn de la página DiegoVal Academy mediante Buffer MCP oficial.
- Sin gastos adicionales. El modo automático sólo se activa después de una prueba real satisfactoria.

## Iniciar en la terminal
Desde la carpeta de este proyecto: `claude`

En Claude Code: `/mcp` para revisar la conexión de Buffer, autenticarla mediante OAuth si hace falta y confirmar el canal por nombre e ID.

Primera petición de Claude: abre `prompts/PRIMERA_TAREA.md` y sigue sus instrucciones.

## Flujo por publicación
```
python scripts/render_post.py posts/<carpeta>/post.json      # imagen 1080×1350
python scripts/validate_post.py posts/<carpeta>              # APROBADA / BLOQUEADA
python scripts/prepare_publish.py posts/<carpeta> --image-url <URL pública> --mode customScheduled --due <ISO>
python scripts/history.py add posts/<carpeta> --status scheduled --buffer-post-id <id>
```
Procedimiento completo de la rutina: `prompts/RUTINA_SEMANAL.md`. Estado de la nube: `docs/AUTOMATIZACION.md`. Modelos: `docs/MODELOS.md`.

## Estructura
- `AGENTS.md` / `.codex/config.toml`: instrucciones y esfuerzo por defecto para Codex (remiten a `CLAUDE.md`).
- `.claude/agents/`: subagentes con modelo asignado (Haiku, Sonnet, Opus).
- `config/`: canal Buffer autorizado y reglas de publicación.
- `scripts/`: generador de imagen, validador, payload de Buffer e historial.
- `assets/fonts/`: Source Serif 4 e Inter (licencia SIL OFL, archivos `*-OFL.txt`).
- `CLAUDE.md`: memoria/instrucciones que Claude Code carga al entrar en la carpeta.
- `.mcp.json`: Buffer MCP limitado al **contexto de este proyecto**, sin secretos.
- `docs/EDITORIAL.md`: política y selección de temas.
- `docs/FUENTES.md`: fuentes oficiales para comenzar las búsquedas.
- `docs/CHECKLIST.md`: criterios de calidad y reglas de publicación.
- `templates/POST_SPEC.md`: formato de salida.
- `data/publication_history.csv`: temas publicados e historial.
- `posts/`: carpetas de resultados por semana.
- `assets/`: recursos visuales aprobados y plantillas.

## Advertencias
La carpeta creada en tu PC no existe automáticamente en Claude Cowork o Claude Code Cloud. El flujo en la nube necesita tener disponibles las instrucciones, los recursos y el generador de imágenes durante la ejecución. No confundir `claude` en la terminal local con una tarea recurrente remota.

Para mantener separado un proyecto, NO copies el contenido de este CLAUDE.md al archivo global `~/.claude/CLAUDE.md`.
