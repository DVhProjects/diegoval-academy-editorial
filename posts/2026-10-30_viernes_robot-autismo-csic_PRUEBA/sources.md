# Fuentes — PRUEBA E2E 5 (formato vídeo, modo nube) · consulta 2026-10-28

## Vídeo evaluado
- https://www.youtube.com/watch?v=-AYRssjyzOw — "El CSIC desarrolla un robot para ayudar en terapias de niños con autismo", canal CSIC Comunicación (`UCCzO-Rkos3KuKOfssqcjaqw`), publicado 2026-07-02 (RSS del canal). `video.py inspect`: source `feed`, ok true; duración y subtítulos NO verificados (YouTube responde 429 a la página). Idioma: español (título y descripción en español).
- Nota técnica: la primera ejecución de `inspect` falló porque `channel_id_of` tomaba el primer `"channelId"` de la página del canal (un canal de NASA). Se corrigió en `scripts/video.py` (prioriza `channel_id=` del enlace RSS) y el resultado anterior se descartó.

## Procedencia oficial
- Página oficial: https://www.csic.es/es — la web del CSIC enlaza su canal de YouTube en "Redes Sociales" con la URL `http://www.youtube.com/user/csicdptocomunicacion` (icono sin texto; no hay cita literal; el único texto cercano es el encabezado "Redes Sociales"). Esa URL resuelve a `https://www.youtube.com/channel/UCCzO-Rkos3KuKOfssqcjaqw`, el mismo canal del vídeo (comprobado con la cabecera canónica y el RSS del canal).
- csic.es NO incrusta este vídeo concreto ni la nota de prensa lo enlaza (0 menciones de "youtube"/"vídeo" en el PDF). La procedencia se apoya en el canal oficial enlazado desde csic.es, no en el vídeo.

## Contenido (nota de prensa oficial del CSIC, 2 de julio de 2026)
- https://www.csic.es/sites/default/files/noticia/2026-06-29/Nd_02julio2026_robot%20autismo_DEF.pdf
- "Las primeras pruebas se han llevado a cabo durante el mes de junio en Madrid, a través de actividades de aprendizaje diseñadas por especialistas de Deletrea"
- "El robot, desarrollado dentro del proyecto Emorobcare, “está diseñado para interactuar con personas, es de bajo coste y tiene múltiples usos potenciales”"
- "El robot es un coterapeuta: un mediador y facilitador de la comunicación social con los chicos" (Sandra Freire, Deletrea)
- Coliderazgo: ICMAT (David Ríos Insua) e IIIA (Juan Antonio Rodríguez Aguilar). "En esta primera fase, el robot se ha programado para mejorar las competencias de lenguaje de niños con autismo."
- No se publican resultados de eficacia: el texto se limita a "primeras pruebas".
- Los datos de la web del CSIC (csic.es/es/actualidad…) para esta noticia devolvieron 404 al probar rutas supuestas; se usa el PDF de la nota de prensa alojado en csic.es.

## Alternativas descartadas (vídeos del mismo canal, RSS)
- "Anna Traveset, ISLAS: Laboratorios naturales" (2026-10-20): no se evaluó a fondo; tema de menor relación con trayectorias de doctorado para la audiencia.
- "El eclipse solar como laboratorio científico" (2026-08-11): descartado por menos relevancia para carrera investigadora.
