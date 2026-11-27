# Prototipo de los dashboards

Copia local del prototipo publicado en <https://claude.ai/artifact/9VXZAefHhbPXN8jkahvLBj> (privado; se comparte desde *Share*). Muestra los 6 dashboards de `metricas/metricas.md` más el anexo de calidad, con datos reales. Es la **referencia visual** para construir Gold y Power BI.

## Contenido

| Ruta | Qué es |
| --- | --- |
| `index.html` | La página: HTML, estilos y código (d3). Cada `dash.calc` es una métrica con su fórmula, y cada `dash.draw`, un gráfico |
| `datos/` | Los 11 archivos de datos que usa la página (CSV y los límites de los departamentos en GeoJSON) |
| `config/datasets/` | La ficha de cada fuente de datos: título, descripción, archivo y de dónde salió |
| `config/dash/` | Título (`meta.json`) y municipalidad inicial de la ficha (`params.json`, Arequipa provincial) |

## De dónde salen los datos (2026-11-22 / 2026-11-26)

| Archivo | Origen |
| --- | --- |
| `siaf_*.csv` | Silver `siaf_ingreso` (2009–2026), agregado por año, mes, rubro, categoría I–IV, departamento y municipalidad |
| `renamu_anual.csv` | Silver `renamu_finanzas` |
| `municipios_2024.csv` | Una fila por municipalidad: SIAF 2024 (Silver) + RENAMU 2025, que describe 2024 (**leído de Bronze, preliminar**) + clasificación A–G del SISMEPRE (**Bronze**) + finanzas del RENAMU (Silver) |
| `calidad_*.csv` | `data/auditoria/volumenes.parquet` y las bitácoras de 01, 03 y 05b |
| `departamentos_peru.json` | Límites de los 25 departamentos, simplificados, de <https://github.com/juaneladio/peru-geojson> (`peru_departamental_simple.geojson`) |

Cuando Silver tenga el RENAMU 2020–2026 completo y el SISMEPRE, estos archivos deben salir de Gold y no de Bronze.

## Cómo verlo o reconstruirlo

- **Verlo:** abrir el enlace de arriba.
- **El `index.html` no abre solo en el navegador:** usa el entorno del tipo de artifact *Data* de Claude (`dash.data`, `dash.calc`, `dash.draw`), que carga los datos y dibuja.
- **Reconstruirlo si se pierde el enlace:** pedir a Claude un dashboard nuevo del tipo *Data* y darle esta carpeta. Hay que subir cada archivo de `datos/`, crear cada fuente con la ficha de `config/datasets/` (cambiando la `url` por la del archivo subido) y guardar `index.html` como página.
