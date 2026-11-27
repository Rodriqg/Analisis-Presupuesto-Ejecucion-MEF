# Métricas: propuesta para los 6 dashboards

> **Estado:** propuesta para revisar con el profesor. Sale del inventario de fuentes (`01_inventario.ipynb`).
> Primero se acuerdan los dashboards y las métricas; después se ajustan Silver y Gold para calcularlas.
> **Prototipo con datos reales:** <https://claude.ai/artifact/9VXZAefHhbPXN8jkahvLBj> (privado; se comparte desde *Share*).

## Historia central

**¿Las municipalidades tienen la capacidad para generar y gestionar sus propios ingresos, y cómo se refleja eso en los servicios que prestan?**

- **SIAF** dice *cuánto* dinero hay y *de dónde* viene.
- **RENAMU** dice *con qué* cuenta la municipalidad (personal, equipamiento) y *qué hace* (servicios).
- **SISMEPRE** dice *cómo gestiona* su principal ingreso propio, el impuesto predial.

El valor está en **cruzarlas**: dinero ÷ capacidad, gestión → recaudación, recursos → servicios.

## Cómo se arma cada métrica

| Parte | Qué es |
| --- | --- |
| Pregunta | Qué decisión ayuda a tomar |
| Fórmula | Numerador ÷ denominador (o suma, conteo, variación) |
| Fuente | Tabla y columna de donde sale cada parte |
| Grano | A qué nivel se calcula (municipalidad × año, salvo que se diga otra cosa) |
| Lectura | Qué significa un valor alto o bajo |

## Reglas comunes

- **Período:** 2020–2025, con 2026 como año parcial (hasta noviembre en el SIAF). En las comparaciones anuales, 2026 se marca o se excluye.
- **Año del dato:** la edición *N* del RENAMU describe el año *N − 1*. Se cruza con el SIAF del año *N − 1*.
- **Cruce:** por `ubigeo` + año (el SISMEPRE, por `sec_ejec` → `ubigeo`).
- **PIA y PIM siempre anuales** (suma de los meses). Solo el recaudado se analiza por mes.
- **Promedios:** sin las municipalidades que no informaron el cuadro o la pregunta.
- **Sin población:** las fuentes no traen habitantes. Las comparaciones se hacen entre municipalidades del mismo tipo (provincial o distrital, clasificación A–G) o por trabajador.
- **Filtros en todos los dashboards:** año, departamento → provincia → distrito, tipo de municipalidad y clasificación A–G.

---

## Dashboard 1 — Panorama financiero

*¿Cuánto dinero tienen las municipalidades, de dónde viene y cuánto ejecutan de lo presupuestado?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Recaudado total | Σ `monto_recaudado` | SIAF | Tarjeta + línea por año | Tamaño de los ingresos |
| 1.2 | PIA y PIM | Σ `monto_pia`, Σ `monto_pim` por año | SIAF | Tarjetas + columnas agrupadas | Presupuesto inicial y final |
| 1.3 | % de ejecución | Recaudado ÷ PIM | SIAF | Medidor + mapa por departamento | Más de 100 % = recaudó más de lo previsto |
| 1.4 | Variación interanual | (Recaudado *t* − *t−1*) ÷ *t−1* | SIAF | Columnas verde/rojo | Crecimiento de los ingresos |
| 1.5 | Composición del ingreso | Recaudado por categoría I–IV (genéricas agrupadas*) | SIAF | Barras al 100 % por año | Cuánto es corriente, capital, transferencias o financiamiento |
| 1.6 | Estacionalidad | Recaudado por mes | SIAF | Columnas por mes o mapa de calor año × mes | Meses de mayor ingreso (p. ej. el predial en febrero) |
| 1.7 | **Por departamento** | % de ejecución, % de autonomía, % del canon, recaudado o predial, agrupando por los 2 primeros dígitos del `ubigeo` | SIAF | **Mapa coroplético** (Shape map) + ranking en barras, con selector de métrica y año | Dónde se ejecuta mejor o se depende más |

Serie histórica: **2009–2026** (el SIAF tiene todos los años en Silver; en 2009–2011 el PIA venía repartido en el año, pero el total anual es comparable).

\* Categorías del RENAMU a partir de la genérica del SIAF: I = 1, 2, 3, 5 · II = 6, 7 · III = 4 · IV = 8, 9 (comprobado: coinciden a menos del 0,6 %).

## Dashboard 2 — Autonomía vs. dependencia

*¿Quién vive de sus propios ingresos y quién de transferencias? ¿Alcanzan para cubrir el gasto?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 2.1 | Ingresos propios | Recaudado de los rubros 08 (impuestos municipales) + 09 (RDR) | SIAF | Tarjeta | Lo que la municipalidad genera |
| 2.2 | Transferencias | Rubros 07 (FONCOMUN) + 13 (donaciones) + 18 (canon y regalías) | SIAF | Tarjeta | Lo que recibe del Estado |
| 2.3 | % de autonomía | Propios ÷ total recaudado | SIAF | Mapa + ranking | Más alto = más independiente |
| 2.4 | Dependencia del canon | Rubro 18 ÷ total | SIAF | Barras: top 15 | Riesgo si cae el precio de los minerales |
| 2.5 | Mezcla de fuentes | Recaudado por rubro y año | SIAF | Áreas apiladas | Cómo cambia la dependencia en el tiempo |
| 2.6 | Cobertura del gasto | `ing_total` ÷ `gas_total` | RENAMU | Línea por año | Menos de 100 % = gasta más de lo que ingresa |
| 2.7 | Peso de la inversión | `gas_capital` ÷ `gas_total` | RENAMU | Mapa | Cuánto del gasto va a obras |
| 2.8 | **Evolución de la autonomía** | % de autonomía y % del canon por año, 2009–2025 | SIAF | Líneas | La autonomía casi no creció (19–28 %): lo propio creció, pero las transferencias también |
| 2.9 | **Departamentos más y menos independientes** | % de autonomía por departamento, 2009 vs. 2025 | SIAF | Gráfico de pesas (*dumbbell*) | Lima 51 % vs. Loreto 7,6 %; las regiones mineras dependen del canon |

En el prototipo, la cobertura del gasto (2.6) va como tarjeta de cifra.

## Dashboard 3 — Capacidad institucional

*¿Con qué personal y equipamiento cuentan? ¿Las que tienen más capacidad generan más ingresos propios?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 3.1 | Personal total | `P19D_T` | RENAMU | Tarjeta + barras por tipo | Tamaño de la organización |
| 3.2 | % de funcionarios y directivos | `P19_1_T` ÷ `P19D_T` | RENAMU | Columnas por tipo A–G | Peso de la plana directiva |
| 3.3 | **Ingresos propios por trabajador** | Propios (SIAF 2.1) ÷ `P19D_T` | SIAF + RENAMU | Dispersión: X personal, Y propios | Productividad recaudatoria |
| 3.4 | Computadoras con internet por cada 10 trabajadores | `P14A_1` ÷ `P19D_T` × 10 | RENAMU | Barras por tipo | Nivel de equipamiento |
| 3.5 | Vehículos operativos | `P11A_1_1` | RENAMU | Barras | Capacidad operativa |
| 3.6 | Digitalización | % con pago en línea (`P31_3`) | RENAMU | Tarjeta + barras por tipo | En 2024 solo el 5 % acepta pago por la web |
| 3.7 | **Herramientas de gestión** | % con personal de rentas (`P32`), pago en línea (`P31_3`) y oficina ambiental (`P96`), por A–G | RENAMU | Columnas agrupadas | Qué tan equipada está cada tipo de municipalidad para gestionar |

## Dashboard 4 — Gestión del impuesto predial

*¿Cuánto de lo que emiten cobran? ¿Cuánta deuda acumulan? ¿Influye tener personal de rentas o ejecución coactiva?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 4.1 | Predial recaudado | Clasificador `1.2.1.1.1` + `1.2.1.1.2` | SIAF | Tarjeta + línea | Principal ingreso propio |
| 4.2 | Peso del predial | Predial ÷ ingresos propios | SIAF | Columnas por tipo A–G | Cuánto depende de este impuesto |
| 4.3 | **Tasa de cobranza** | Recaudación del año ÷ emisión | SISMEPRE (ESAT) | Medidor + ranking | Qué parte de lo que debía cobrar cobró |
| 4.4 | **Morosidad** | Saldo por cobrar ÷ emisión | SISMEPRE (ESAT) | Mapa | Deuda acumulada frente a lo emitido |
| 4.5 | % de cobranza coactiva | Recaudación coactiva ÷ recaudación total | SISMEPRE (ESAT) | Barras al 100 % | Cuánto se cobra por la vía forzosa |
| 4.6 | **Predial por trabajador de rentas** | Predial (SIAF 4.1) ÷ `P32_1_T` | SIAF + RENAMU | Dispersión por tipo A–G | ¿Más personal de rentas = más recaudación? |
| 4.7 | Con o sin capacidad tributaria | Tasa de cobranza según tenga personal de rentas (`P32`) y área coactiva (`P33A`) | SISMEPRE + RENAMU | Columnas agrupadas | Efecto de la capacidad en la gestión |

> La tasa de cobranza y la morosidad requieren tomar cada medida de su formulario del ESAT (3A emisión, 3B recaudación, 3C saldos) y del cierre del año. Se resuelve en Silver (`04_sismepre`).

## Dashboard 5 — Servicios a la ciudadanía

*¿Qué servicios prestan y cómo se relacionan con sus recursos?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 5.1 | Cobertura del serenazgo | % de municipalidades con serenazgo (`P69_1`) | RENAMU | Mapa | Presencia del servicio |
| 5.2 | Efectivos de serenazgo | `P69_1_T`; y unidades operativas por cada 10 efectivos (`P70A_1_2` ÷ `P69_1_T` × 10) | RENAMU | Barras por tipo | Tamaño y equipamiento |
| 5.3 | Residuos recogidos | `P41_1` (kg/día) | RENAMU | Tarjeta + mapa | Volumen del servicio de limpieza |
| 5.4 | Disposición adecuada | % con relleno sanitario (`P44_1`); % promedio a botadero (`P44_2_1`) | RENAMU | Anillo + mapa | Más relleno y menos botadero = mejor gestión ambiental |
| 5.5 | Programas sociales | Beneficiarios del Vaso de Leche (`P60A_1_2`) y de comedores (`P60A_2_2`) | RENAMU | Barras por departamento | Alcance social |
| 5.6 | Protección de la niñez | Casos de la DEMUNA (`P64_1_1`, …) | RENAMU | Columnas | Demanda atendida |
| 5.7 | **Servicios según recursos** | Las métricas 5.1–5.4 por quintil de ingresos propios (SIAF 2.1) | SIAF + RENAMU | Columnas agrupadas por quintil | ¿Las que más recaudan prestan mejores servicios? |

## Dashboard 6 — Ficha por municipalidad

*¿Cómo está esta municipalidad en dinero, capacidad y servicios, comparada con las de su mismo tipo?*

Se elige una municipalidad (departamento → municipalidad) y todo se compara con la **mediana de su grupo** (misma clasificación A–G, o "sin clasificación").

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| 6.1 | Recaudado, % de ejecución, % de autonomía, personal, ingresos propios por trabajador | Las de los dashboards 1–3, para la municipalidad y la mediana de su grupo | SIAF + RENAMU | Tarjetas con "Grupo: …" | Si está por encima o por debajo de sus pares |
| 6.2 | Evolución 2009–2025 | PIM, recaudado y propios de la municipalidad por año | SIAF | Líneas | Su trayectoria |
| 6.3 | De dónde viene su dinero | % del recaudado por fuente vs. promedio del grupo | SIAF | Dos columnas apiladas al 100 % | Si depende más que sus pares |
| 6.4 | **Posición en su grupo** | Percentil en autonomía, ejecución, propios por trabajador, predial, computadoras por cada 10 trabajadores y serenazgo | SIAF + RENAMU | Barras de 0 a 100 (50 = mediana) | En qué está bien y en qué atrasada |
| 6.5 | Servicios y gestión | Serenazgo, relleno sanitario, personal de rentas, pago en línea, oficina ambiental, residuos y Vaso de Leche, vs. % de su grupo que los tiene | RENAMU | Tabla con marca sí/no | Qué le falta frente a sus pares |

En Power BI: un *slicer* de municipalidad, y medidas DAX que calculan la mediana y el percentil dentro del grupo A–G de la municipalidad elegida.

## Anexo — Calidad de datos

No es uno de los 6 dashboards de decisión: muestra el control de calidad del pipeline (requisito 4).

*¿Qué tan confiables y al día están los datos? ¿Qué se excluyó y por qué?*

| ID | Métrica | Fórmula | Fuente | Visual | Lectura |
| --- | --- | --- | --- | --- | --- |
| A.1 | Recorrido de las filas | Bronze → fuera de alcance / cuarentena → Silver → Gold | `volumenes.parquet` | Embudo | Que no se pierda nada sin explicación |
| A.2 | Reglas por estado | N.º de reglas en OK, ALERTA, CUARENTENA y DETENIDO | Bitácoras | Matriz regla × ejecución | Salud del pipeline |
| A.3 | Filas con alerta | Filas con `_alertas` por regla | Hechos de Gold | Barras con detalle | Qué revisar |
| A.4 | Frescura | Última descarga y última carga por fuente | Manifest y bitácoras | Tarjetas (en rojo si es antigua) | Si los datos están al día |
| A.5 | Cobertura entre fuentes | % de municipalidades del SIAF con RENAMU y con SISMEPRE, por año | Gold | Columnas | Hasta dónde se puede cruzar |
| A.6 | Control RENAMU vs. SIAF | Diferencia entre `ing_total` y el recaudado anual | RENAMU + SIAF | Columnas + línea de diferencia | Consistencia entre fuentes (hoy ±0,6 %) |

---

## Qué implica para Silver y Gold (después de acordar esto)

| Capa | Cambio |
| --- | --- |
| Silver RENAMU | Rehacer `05a`/`05b` para las **ediciones 2020–2026** y los temas de arriba: personal, equipamiento, administración tributaria, seguridad, residuos, programas sociales, DEMUNA y finanzas |
| Silver SISMEPRE | Construir `04_sismepre`: clasificación A–G y ESAT por formulario (emisión, recaudación ordinaria y coactiva, saldos) |
| Silver SIAF | Sin cambios; el análisis usa 2020 en adelante |
| Gold | Ajustar el boceto de `data/gold/gold.md` a estas métricas |
