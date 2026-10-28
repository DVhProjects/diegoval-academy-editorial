# Fuentes — Mundus MAPP 2027-2029

Consultado: 2026-10-27, entre 16:20 y 16:35 (Europe/Stockholm, CET +01:00). Método: lectura de la página oficial (WebFetch) + comprobación HTTP automática en `validation.md`.

| URL | Campos verificados | Cita literal clave |
|---|---|---|
| https://www.mundusmapp.org/admissions-calendar/ | Convocatoria abierta, cohorte, plazo con hora y zona, resultados | "We are now open to applications for the 2027-2029 Mundus MAPP cohort." · "December 1, 2026, 23:59 CET: Application deadline for applicants who wish to be considered for financial aid" · "April 14, 2027: 1st round decisions (incl. EMJM scholarship)" |
| https://www.mundusmapp.org/financial-aid/ | Importe, duración, matrícula, qué no cubre, regla de beca previa, sin formulario aparte | "monthly unit cost of 1400 EUR/month" · "a maximum scholarship amount of 33 600 Euros (24 months)" · "EMJM scholarship recipients receive a full tuition-fee waiver" · Study Visit / Winter School "in the range of 600-1000 EUR" no cubiertos · "Travel and visa costs between students' home countries and the consortium countries" no cubiertos · quienes ya tuvieron EMJM "are not eligible" · "will be asked in the online portal to indicate their interest in a potential scholarship" · "offered to outstanding applicants from both within and outside the EU" |
| https://www.mundusmapp.org/admissions-requirements/ | Grado, nota mínima, campos excluidos, inglés, movilidad, español | "Bachelors degree comprising at least three years of studies" · "class 2.1/Upper Second" · "GPA of at least 3.17/4.0 or equivalent" · "Candidates with a Bachelors degree in Natural Sciences or Engineering are not eligible to apply." · IELTS Academic 7, TOEFL iBT 95, Duolingo 130 · dos periodos de estudio en dos países distintos del país de residencia · "Proficiency in Spanish is not a requirement" · "Work experience is not an eligibility requirement" |
| https://www.mundusmapp.org/admissions-checklist/ | Documentos, itinerarios, último año | "two official letters of recommendation, preferably at least one of them from an academic" · statement of purpose "No more than 500 words" · "expected to complete their current course of study by August 15, 2027" · 4 itinerarios: CEU-IBEI (Global Public Policy), CEU-York (European Public Policy), ISS-IBEI (Political Economy and Development), ISS-York (Governance and Development) |
| https://www.mundusmapp.org/how-to-apply/ | Abierto, portal, tasa | "We are now open to applications for the 2027-2029 Mundus MAPP cohort." · "Applicants do not need to pay the CEU application fee unless they apply for other CEU programs." |
| https://www.mundusmapp.org/ | Consorcio y ciudades | CEU (Viena, Austria), IBEI (España), ISS – Erasmus University Rotterdam (La Haya, Países Bajos), University of York (Reino Unido) |

## Datos no verificables o no usados
- Nombre oficial completo del programa: la web sólo muestra "Mundus MAPP"; en el texto se describe como "máster Erasmus Mundus en Políticas Públicas" sin presentarlo como nombre oficial.
- Número de becas: la web dice "a limited number"; no se publica cifra → no se menciona ninguna cifra.
- Ciudad de IBEI: el nombre oficial de la institución es "Institut Barcelona d'Estudis Internacionals" (Barcelona).

## Selección editorial (candidatas evaluadas)
1. **Elegida — Mundus MAPP (EMJM).** Financiación completa de matrícula + 1400 €/mes, abierta a candidatos de dentro y fuera de la UE, plazo explícito con año, hora y zona (1 dic 2026, 23:59 CET), 35 días de margen, sin tasa CEU, itinerario en España (relevante para hispanohablantes).
2. Alternativa — EPFL Master Excellence Fellowship (https://www.epfl.ch/education/master/master-excellence-fellowships/how-to-apply/): CHF 10 000/semestre, plazo "December 15", pero la página no indica año ni cohorte → no publicable sin inferir el ciclo.
3. Alternativa — ETH Zurich ESOP: sólo fuentes secundarias indican ventana 1–30 nov 2026; no abierta al 2026-10-27 → descartada hoy, candidata para un miércoles de noviembre tras verificar en eth.ch.

## Verificación independiente (subagente `verificador-convocatorias`, claude-sonnet-5-5) — 2026-10-27 ~16:55
Primer veredicto: **BLOQUEADA**. Correcciones aplicadas y reconfirmadas literalmente en la web oficial:
1. (Bloqueante) "Abierto a cualquier nacionalidad" no era literal → ahora "Abierto a candidatos de dentro y fuera de la UE" ("offered to outstanding applicants from both within and outside the EU", /financial-aid/).
2. Movilidad → cita literal (/admissions-requirements/): "Mobility requirements: 2 study periods in 2 different countries, each min. 30 ECTS" · "You are eligible to apply if your residence (at the time of application/enrollment) is different from the countries..." · "(e.g. on the ISS-IBEI track: outside of the Netherlands and Spain)."
3. "Sin tasa" → "Sin tasa CEU" ("Applicants do not need to pay the CEU application fee unless they apply for other CEU programs.", /how-to-apply/).
4. Añadido: validez de exámenes ("taken within two years of the application deadline", /admissions-requirements/) y cartas ("The recommendation letters need to be submitted within 7 days of the application submission.", /admissions-checklist/).
5. IBEI = "Institut Barcelona d'Estudis Internacionals" (nombre oficial → Barcelona); la portada indica "Spain".

Re-verificación (mismo subagente, claude-sonnet-5-5) tras correcciones: **VEREDICTO: APROBADA** — ninguna afirmación del caption ni de la imagen sin respaldo literal.

## Re-verificación del día de publicación — 2026-10-28 ~09:30 (verificador-convocatorias, Sonnet)
Las 5 URLs oficiales reabiertas hoy: sin cambios respecto al 2026-10-27 (cohorte 2027-2029 abierta; plazo 1 dic 2026 23:59 CET; importes, requisitos, movilidad, cartas en 7 días, sin tasa CEU). validate_post.py APROBADA, sin duplicados. **VEREDICTO: APROBADA**.
