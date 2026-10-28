# Estilo v2 (compacto) — 2026-10-28

Motivo: la primera publicación (Mundus MAPP, 2026-10-28) era correcta pero densa: 4 datos + "primer paso" en la imagen y un caption de 2950 caracteres que repetía la imagen con jerga (EMJM, GPA, itinerarios, 2.1/Upper Second).

## Plantilla de imagen (`scripts/render_post.py`)
| | v1 (MAPP) | v2 |
|---|---|---|
| Bloques de información | 7 (antetítulo, número, titular, entradilla, plazo, 4 datos, primer paso) | 5 (antetítulo+número, titular, entradilla, plazo/idea clave, 2-3 datos, "Lo que pocos explican") |
| Titular | 74 px, hasta 4 líneas | 84 px, máx. 3 líneas (ideal 2, ≤ 55 caracteres) |
| Entradilla | 33 px, hasta 4 líneas | 35 px, máx. 2 líneas (≤ 110 caracteres) |
| Valor destacado | 46 px | 58 px |
| Datos | 3-5, 31 px, hasta 3 líneas | 2-3, 34 px, máx. 2 líneas (≤ 48 caracteres) |
| Bloque final | "Primer paso" (genérico) | "Lo que pocos explican": dato práctico verificado, sobre fondo tintado del color de la serie |
| Espaciado | fijo; el sobrante quedaba abajo | el sobrante se reparte entre secciones |
| Compatibilidad | — | v2 se activa con el campo `tip`; las fichas v1 se siguen generando idénticas (comprobado byte a byte) |

Identidad visual sin cambios: papel crema, tinta azul noche, Source Serif 4 + Inter (OFL), terracota (oportunidades) / azul petróleo (research & career), sin fotos, sin IA generativa.

## Caption
| | v1 | v2 |
|---|---|---|
| Longitud | ≤ 3000 (MAPP: 2950) | ≤ 1300 (objetivo ~1000-1200) |
| Estructura | todo el detalle: ofrece, no incluye, itinerarios, requisitos, fechas, pasos, 5 enlaces | gancho · "En corto:" 3-4 viñetas · "Lo que pocos explican:" · "Cómo empezar:" 2-3 pasos · 1-2 enlaces · Verificado el · 2-3 hashtags |
| Lenguaje | siglas y términos técnicos | frases cortas; siglas explicadas la primera vez |
| Relación con la imagen | la repetía | la complementa |

## Reglas automáticas nuevas
- `validate_post.py` bloquea si falta el bloque `tip` en la imagen o la línea "Lo que pocos explican" en el caption, y si el caption supera 1300 caracteres.
- Anti-ruido (`prompts/RUTINA_SEMANAL.md`): máximo una publicación al día salvo petición del propietario; no dos del mismo tipo en menos de 72 h.

## Publicación de Mundus MAPP ya enviada
- Buffer no permite editarla: la publicación enviada sólo admite `viewPost, sharePostLink, copyPostLink, updatePostTags, addPostNote, duplicatePost, updateShopGridLink` (sin `updatePost`). No se borra.
- LinkedIn sí permite editar a mano el TEXTO (no la imagen). Versión compacta lista para pegar: `posts/2026-10-28_miercoles_mundus-mapp-2027/revision_v2/caption.md` (1071 caracteres).
- Ficha v2 de comparación (no publicada): `posts/2026-10-28_miercoles_mundus-mapp-2027/revision_v2/post.png`.
