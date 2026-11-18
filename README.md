# Frankfurt-Hahn – Nador | Günstige Flüge finden

Proyecto independiente para la página de Facebook **„Frankfurt-Hahn – Nador | Günstige Flüge finden“**.
Ayuda gratis a la comunidad de Nador en Alemania a encontrar vuelos baratos de **Ryanair** entre
**Frankfurt-Hahn (HHN)** y **Nador (NDR)**.

- Consulta los precios de los **próximos 6 meses** en ambos sentidos, en euros.
- Guarda un **historial persistente** de cada vuelo.
- Genera **calendarios mensuales** (PNG 1080 × 1350, modo oscuro, en alemán).
- Detecta **5 tipos de ofertas** y prepara imágenes y textos de Facebook.
- La **publicación en Facebook está DESACTIVADA** hasta que la apruebes.

> Este proyecto es completamente independiente del script de alertas por email
> (`github-ryanair-alerta`). No usa ni modifica nada de ese proyecto.

---

## Estructura

```
hahn-nador-flight-deals/
├─ config.toml                 Todos los umbrales, horarios, colores y textos fijos
├─ requirements.txt            Pillow, certifi
├─ requirements-dev.txt        + pytest
├─ assets/fonts/               Fuente Inter (licencia OFL)
├─ data/                       Historial persistente (lo guarda GitHub Actions)
│   ├─ history.json            Precio de cada vuelo a lo largo del tiempo + mínimos mensuales
│   └─ state.json              Ofertas ya avisadas, publicaciones del día
├─ output/                     Publicaciones preparadas (no se sube al repositorio)
├─ src/flightdeals/
│   ├─ config.py               Carga config.toml, zona horaria Europe/Berlin
│   ├─ fetch.py                Consulta de precios con reintentos y validación
│   ├─ storage.py              Historial y estado
│   ├─ analysis.py             Vuelos futuros y mejor combinación ida + vuelta
│   ├─ alerts.py               Detección de las 5 ofertas
│   ├─ texts.py                Textos, fechas y precios en alemán, enlaces de Ryanair
│   ├─ render/calendar.py      Imagen del calendario mensual
│   ├─ render/alert.py         Imágenes de ofertas con gráfico de evolución
│   ├─ posts.py                Publicaciones (imágenes + texto), verificación de precios
│   ├─ facebook.py             Publicación en Facebook (Meta Graph API) – desactivada
│   ├─ summary.py              Resumen de cada ejecución
│   └─ cli.py                  Comandos run / demo / publish
├─ tests/                      Pruebas automáticas (pytest)
└─ .github/workflows/flight-deals.yml
```

## Uso local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

PYTHONPATH=src .venv/bin/python -m flightdeals run                 # ejecución normal
PYTHONPATH=src .venv/bin/python -m flightdeals run --force daily   # forzar publicación diaria
PYTHONPATH=src .venv/bin/python -m flightdeals run --force weekly  # forzar publicación de 6 meses
PYTHONPATH=src .venv/bin/python -m flightdeals demo                # calendarios reales + 5 ofertas de ejemplo
PYTHONPATH=src .venv/bin/python -m flightdeals top3                # publicación "Top 3 Kombinationen"
.venv/bin/python -m pytest -q                                      # pruebas
```

## Qué hace cada ejecución (`run`)

1. **Consulta** los precios de HHN→NDR y NDR→HHN de los próximos 6 meses (12 peticiones,
   con pausa de 2 s entre ellas y hasta 3 reintentos).
2. **Valida** cada precio: moneda EUR, rango plausible y fecha correcta. Si un mes falla, sus días
   salen con **?** y **no se usan precios antiguos**. Si fallan todos los meses, no se publica nada.
3. **Detecta ofertas** comparando con el historial anterior.
4. **Guarda** los precios nuevos en el historial (solo cuando cambian).
5. Si es la hora, **prepara la publicación diaria o semanal**.
6. Si hay ofertas nuevas, **prepara una publicación adicional** (máximo 3 al día).
7. Escribe un **resumen** (`output/<fecha>/zusammenfassung_<hora>.md` y en GitHub Actions).

### Publicaciones

| Cuándo | Qué |
|---|---|
| Cada día a las **08:00** (Europe/Berlin) | 2 imágenes: mes actual y mes siguiente |
| **Domingo** a las 08:00 | 6 imágenes: los próximos 6 meses (sustituye a la diaria) |
| Durante el día | Solo si hay ofertas nuevas (agrupadas, máximo 3 publicaciones extra al día) |

El cambio de horario de verano e invierno se gestiona automáticamente.

### Top 3 Kombinationen

Publicación con las tres mejores combinaciones de ida y vuelta (salida en el mes actual y el siguiente),
cada una para un tipo de viaje distinto (configurable en `[top3]` de `config.toml`):

| Categoría | Noches |
|---|---|
| Günstigste Kombination | 3–30 |
| Familienbesuch | 14–21 |
| Kurztrip | 3–5 |

Nunca se repite la misma combinación y las medallas 🥇🥈🥉 se ordenan por precio total. Se genera a
mano con `python -m flightdeals top3` o desde GitHub Actions (opción `top3-kombinationen`).

### Ofertas (`alerts.py`)

| Tipo | Condición (configurable en `config.toml`) |
|---|---|
| **PREISSTURZ** | El precio baja **al menos 10 € y un 20 %** |
| **TOP-ANGEBOT** | Aparece un vuelo nuevo por **menos de 30 €** |
| **GÜNSTIGER HIN- UND RÜCKFLUG** | Combinación ida + vuelta por **menos de 50 €** |
| **NEUER TIEFSTPREIS** | Precio más bajo que el mínimo registrado ese mes |
| **LAST-MINUTE-ANGEBOT** | Vuelo en los **próximos 7 días** por menos de 30 € |

- Si un vuelo cumple varias condiciones, se genera **una sola oferta** (la de mayor prioridad) y las
  demás aparecen como etiqueta (*+ NEUER TIEFSTPREIS*).
- **Nunca se repite** una oferta del mismo vuelo con el mismo precio.
- En la **primera ejecución** solo se guarda la base: no se generan ofertas.
- Se excluyen siempre los vuelos que ya han salido.

### Combinación más barata
- La vuelta tiene que ser **posterior** a la ida, con una estancia entre `min_nights` y `max_nights`
  (por defecto 3–30 noches).
- La vuelta puede caer en el **mes siguiente**.

### Salida (`output/`)

```
output/2026-11-20/0803_taeglicher-kalender/
    01_kalender_2026-11.png
    02_kalender_2026-12.png
    beitrag.txt        ← texto de Facebook en alemán, con enlaces oficiales de Ryanair
    beitrag.json       ← metadatos (tipo, imágenes, enlaces, estado de publicación)
output/2026-11-20/1817_angebote/
    01_preissturz_hhn-ndr_2027-01-12.png
    ...
output/2026-11-20/zusammenfassung_1817.md
```

En GitHub Actions, toda la carpeta `output/` se descarga como **ZIP** desde la pestaña *Actions → la
ejecución → Artifacts* (`facebook-beitraege-<número>`).

### Equipaje
Todos los precios son **por persona** y de la tarifa más barata de Ryanair (**Basic**): solo incluye
una mochila o bolso pequeño (40 × 30 × 20 cm). El trolley de cabina y la maleta facturada se pagan aparte.
Este aviso aparece en las imágenes y en los textos.

## GitHub Actions

Archivo: `.github/workflows/flight-deals.yml`

- Cada **6 horas**: consulta precios, actualiza el historial y genera ofertas.
- A las **06:03 y 07:03 UTC**: una de las dos corresponde a las 08:00 en Berlín (verano o invierno).
  El script comprueba la hora de Berlín y solo crea una publicación diaria al día.
- **Ejecución manual**: *Actions → Flugpreise Hahn – Nador → Run workflow*, con las opciones
  `automatisch`, `tagesbeitrag-erzwingen`, `wochenbeitrag-erzwingen` y `demo`.
- Antes de cada ejecución se pasan las **pruebas**. El historial (`data/`) se guarda en el repositorio.

> GitHub retrasa o se salta a veces las ejecuciones programadas. Para más puntualidad se puede
> lanzar el workflow desde **cron-job.org**, igual que en el proyecto de alertas por email.

## Facebook (desactivado)

Para publicar automáticamente tienen que cumplirse **las cuatro** condiciones:

1. `config.toml` → `[facebook] autopublish = true`
2. Variable del repositorio `FACEBOOK_AUTOPUBLISH = true` (*Settings → Secrets and variables →
   Actions → Variables*)
3. Secrets `FACEBOOK_PAGE_ID` y `FACEBOOK_PAGE_ACCESS_TOKEN`
4. La publicación no contiene datos de prueba

Las credenciales solo se leen de variables de entorno: **nunca están en el código**. El módulo sube
las imágenes sin publicar y crea **una sola publicación** con el texto y todas las imágenes (Graph API).

**No se activa nada hasta que lo apruebes.**

## Configuración (`config.toml`)

| Sección | Qué controla |
|---|---|
| `[page]` | Nombre de la página, aviso legal, zona horaria, hashtags |
| `[route]` | Aeropuertos, aerolínea, moneda, meses a consultar |
| `[fare]` | Texto sobre el equipaje |
| `[fetch]` | Pausas, reintentos, rango de precios válido |
| `[stay]` | Noches mínimas y máximas para la combinación |
| `[price_colors]` | Límites de verde, amarillo, naranja y rojo |
| `[alerts]` | Umbrales de las 5 ofertas, máximo de publicaciones extra al día, prioridad |
| `[schedule]` | Hora de la publicación diaria, día de la semanal, número de meses |
| `[theme]` | Todos los colores del diseño |

## Fuente de datos y riesgo

Ryanair **no ofrece una API pública oficial** de precios. El proyecto usa el mismo servicio que
utiliza ryanair.com para su calendario de precios (`/api/farfnd/...`).

⚠️ **El `robots.txt` de Ryanair no permite el acceso automático a `/api`.** Su uso es una decisión
consciente del propietario de la página, que asume el riesgo: Ryanair podría bloquear las consultas,
cambiar el servicio sin aviso o pedir que se deje de usar. Para reducir la carga se hacen muy pocas
peticiones (12 cada 6 horas, con pausas). Si el servicio cambia, las consultas fallarán, los días
saldrán con **?** y no se publicarán precios.

La página es **solo informativa, gratuita e independiente**: no vende billetes ni hace reservas.
Todas las publicaciones incluyen: *„Unabhängige Informationsseite. Keine Verbindung zu Ryanair.
Preise können sich jederzeit ändern.“*
