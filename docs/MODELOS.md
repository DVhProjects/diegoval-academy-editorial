# Política de selección de modelos (Claude y Codex)

## 0. Reparto de responsabilidades (2026-10-28)
| | Claude (agente editorial) | Codex (especialista técnico) |
|---|---|---|
| Hace | investigar becas y tendencias, evaluar popularidad/relevancia/elegibilidad, verificar fuentes, elegir temas mié/vie, redactar, ejecutar `render_post.py` y validaciones, publicar con Buffer MCP, registrar historial y radar | scripts Python, plantilla 1080×1350, `render_post.py`, validaciones de texto/imagen/enlaces/fechas, pruebas, corrección de errores de código, reproducibilidad |
| No hace | — | buscar becas, elegir temas, captions habituales, publicar, repetir verificaciones |
| Modelos | Haiku (extracción), Sonnet esfuerzo medio (investigación, verificación, redacción, rutina). Opus sólo a petición expresa | `low` mantenimiento · `medium` por defecto · `high` sólo justificado · `xhigh`/`max`/`ultra` prohibidos |
| Dónde corre | local y rutina en la nube | sólo local (ordenador del propietario) |

**Mecanismo real para delegar en Codex**: plugin oficial `codex` de Claude Code (`/codex:rescue --effort low|medium|high <tarea>`) o `codex -c model_reasoning_effort=… ` en la terminal. Comprobado con `codex-companion setup` (2026-10-28): CLI 0.158.0, sesión ChatGPT activa, `ready: true`. No se lanzó ninguna tarea de Codex en esta actualización (no había trabajo técnico pendiente: no se ejecuta "porque sí").
**La rutina en la nube no usa Codex** (no está instalado allí y depende del ordenador local); todo lo que necesita la rutina son los scripts Python del repositorio.

Objetivo: usar el modelo y el nivel de razonamiento más bajos que hagan bien cada tarea, para no agotar los límites de Claude Pro y ChatGPT Plus. **Regla de calidad:** el ahorro nunca rebaja la verificación de becas, fechas, requisitos, enlaces oficiales ni la calidad de la imagen; si una tarea lo necesita, se sube de nivel.

## 1. Claude

| Nivel | Modelo | Tareas | Mecanismo |
|---|---|---|---|
| Rápido | Haiku (`claude-haiku-5-5`) | Clasificar candidatas, extraer campos literales, ordenar archivos, tareas repetitivas | Subagente `extractor-fuentes` (`model: haiku`) |
| Equilibrado | Sonnet (`claude-sonnet-5-5`) | Investigación semanal, comparación de oportunidades, redacción, **verificación previa a publicar** | Subagentes `investigador-editorial` y `verificador-convocatorias` (`model: sonnet`); rutina en la nube |
| Avanzado | Opus (`claude-opus-5-5`) | Sólo arquitectura o errores que los anteriores no resuelvan | Subagente `depurador-avanzado` (`model: opus`), con justificación anotada abajo |

- La verificación de convocatorias usa Sonnet como mínimo, nunca Haiku. Haiku sólo extrae; su salida siempre la revisa el verificador.
- Sesión interactiva: el modelo lo elige el propietario con `/model` (recomendado: Sonnet, esfuerzo medio). Opus no se usa automáticamente.
- Rutina en la nube: `claude-sonnet-5-5`, fijado en la configuración de la rutina.

## 2. Codex

| Esfuerzo | Tareas | Cómo |
|---|---|---|
| `low` | Cambios pequeños, mantenimiento | `codex -c model_reasoning_effort="low"` · `/codex:rescue --effort low …` |
| `medium` | Plantillas, automatización, Python, comprobaciones habituales | Por defecto (`.codex/config.toml`, ver limitaciones) |
| `high` | Arquitectura compleja, depuración difícil, errores persistentes | `-c model_reasoning_effort="high"` · `--effort high` |
| `xhigh`/`max`/`ultra` | **Prohibido en este proyecto** | — |

Las instrucciones para Codex están en `AGENTS.md`, que remite a `CLAUDE.md` para no duplicar reglas. Codex no publica ni elige temas.

## 3. Comprobaciones realizadas (2026-10-27)

| Comprobación | Resultado |
|---|---|
| Modelo de la sesión de configuración | `claude-opus-5-5` (justificado: diseño de arquitectura del sistema completo) |
| Subagente Haiku | **Funciona**: prueba de extracción en mundusmapp.org; el subagente informó `claude-haiku-5-5` y extrajo cohorte, plazo y fecha de resultados correctamente |
| Subagente Sonnet | **Funciona**: informó `claude-sonnet-5-5`; verificación independiente del lanzamiento → 1.º BLOQUEADA ("cualquier nacionalidad" no literal y 3 matices), corregido → APROBADA |
| Subagentes del proyecto (`.claude/agents/*.md`) | Creados. Claude Code los carga al iniciar sesión: disponibles desde la próxima sesión y en la rutina en la nube (vienen con el repositorio). Las pruebas de hoy se hicieron con el mismo modelo y las mismas instrucciones mediante el selector de modelo del subagente genérico |
| Codex CLI | `codex-cli 0.158.0` instalado (actualización 0.164.0 disponible; no se actualiza sin autorización) |
| Codex lee `AGENTS.md` | **Sí** (`codex debug prompt-input`, sin llamar al modelo) |
| Modelos Codex disponibles | `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-reserve`, `codex-auto-review` (`codex debug models`) |
| Integración Claude → Codex | Plugin oficial `codex` instalado en Claude Code: `/codex:rescue --effort <nivel>` |

## 4. Limitaciones técnicas
- **No hay selección automática por tarea** en Claude Code ni en Codex: el modelo se fija por subagente (`model:` en `.claude/agents/`), por rutina o con `/model`; el esfuerzo de Codex se fija por configuración o con `-c`. La "selección automática" consiste en que Claude delega cada tipo de tarea en el subagente con el modelo asignado.
- `.codex/config.toml` del proyecto: **no verificado**. `codex doctor` sólo muestra `~/.codex/config.toml` como capa cargada; Codex puede requerir que el proyecto esté marcado como confiable. Hasta comprobarlo, pasar el esfuerzo explícitamente con `-c model_reasoning_effort=…`. No se modifica la configuración global.
- Los subagentes heredan los límites de la suscripción del usuario; si Haiku/Opus no estuvieran disponibles en el plan, Claude Code usaría el modelo por defecto (no observado hoy).
- Las rutinas en la nube consumen el mismo límite de uso de la suscripción Claude; no usan API de pago por consumo.

## 5. Registro de uso
| Fecha | Tarea | Modelo / esfuerzo | Motivo |
|---|---|---|---|
| 2026-10-27 | Configuración y arquitectura del sistema, publicación de lanzamiento | claude-opus-5-5 (sesión principal) | Diseño inicial completo (justifica Opus) |
| 2026-10-27 | Prueba de extracción (subagente) | claude-haiku-5-5 | Tarea mecánica |
| 2026-10-27 | Verificación independiente del lanzamiento | Sonnet | Verificación crítica previa a publicar |
| 2026-10-28 | Investigación y redacción de muestras (MSCA, Euroculture) | investigador-editorial (Sonnet) ×2 | Política |
| 2026-10-28 | Verificación de muestras | verificador-convocatorias (Sonnet) ×2 (+ re-verificación) | Calidad |

## 6. Limitaciones pendientes
- El esfuerzo "medium" de Sonnet no se puede fijar en el frontmatter de los subagentes de forma verificada; la sesión interactiva lo fija el propietario con `/model`, y la rutina usa `claude-sonnet-5-5` con su esfuerzo por defecto.
- `.codex/config.toml` del proyecto: Codex no lo muestra como capa cargada en `codex doctor` (puede requerir marcar el proyecto como confiable); mientras tanto pasar el esfuerzo de forma explícita (`-c` o `--effort`).
- Codex no puede prohibir `xhigh` por configuración: la prohibición es una regla de `AGENTS.md`.
