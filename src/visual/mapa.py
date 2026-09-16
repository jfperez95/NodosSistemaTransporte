"""
Paso 5 - Mapa georreferenciado de la red sobre Medellin.

Decisiones de diseno
--------------------
* **La red completa se dibuja recesiva** (trazo fino, opacidad baja) y la ruta
  calculada se dibuja encima, gruesa y con un reborde blanco. Asi el mapa
  contextualiza sin competir: el ojo va primero a la ruta.

* **El color identifica el MODO, no la ruta.** Cada tramo de la ruta conserva el
  color de su modo, de forma que el usuario ve de un vistazo "aqui voy en metro,
  aqui en cable". Un color unico de ruta perderia esa informacion.

* **Codificacion secundaria por patron de trazo.** La separacion entre el naranja
  del cable y el verde del tranvia queda en el minimo admisible bajo
  deuteranopia, asi que el modo tambien se distingue por el patron de la linea.
  El mapa sigue siendo legible en escala de grises.

* **Los marcadores llevan la informacion, no las etiquetas.** Rotular 61
  estaciones satura el mapa; el nombre y los atributos aparecen al pasar el
  cursor o hacer clic.
"""

from typing import Iterable, List, Optional, Sequence, Tuple

import folium
import networkx as nx

from src import config
from src.algoritmos.ruta import Ruta

CENTRO_MEDELLIN = (6.2450, -75.5750)
ZOOM_INICIAL = 12

# Mapa base. Se usa OpenStreetMap porque no exige clave de API: los tiles claros
# de CartoDB empezaron a requerirla y el mapa quedaria en blanco en la maquina de
# quien clone el repositorio -incluida la del dia de la sustentacion-.
TILES = "OpenStreetMap"

COLOR_RUTA_BORDE = "#FFFFFF"
COLOR_ESTACION_EXTREMO = "#111827"
COLOR_ESTACION_INACTIVA = "#9CA3AF"


def _coord(G: nx.MultiDiGraph, nodo: str) -> Tuple[float, float]:
    return (G.nodes[nodo]["latitud"], G.nodes[nodo]["longitud"])


def _popup_estacion(G: nx.MultiDiGraph, nodo: str) -> str:
    """Ficha de la estacion: lo que el MVP pide mostrar de cada elemento."""
    d = G.nodes[nodo]
    servicios = ", ".join(s.replace("_", " ") for s in d["servicios"]) or "-"
    estado = "Activa" if d.get("activa", True) else "CERRADA"
    return (
        f"<div style='font-family:system-ui;font-size:12px;min-width:210px'>"
        f"<b style='font-size:13px'>{d['nombre']}</b><br>"
        f"<span style='color:#6B7280'>{config.NOMBRE_MODO[d['modo']]} &middot; "
        f"lineas {', '.join(d['lineas']) or '-'}</span><hr style='margin:5px 0'>"
        f"<b>Direccion:</b> {d['direccion']}<br>"
        f"<b>Tipo:</b> {d['tipo_estacion']}<br>"
        f"<b>Accesibilidad:</b> {d['accesibilidad']}<br>"
        f"<b>Servicios:</b> {servicios}<br>"
        f"<b>Estado:</b> {estado}"
        f"</div>"
    )


def _popup_tramo(G: nx.MultiDiGraph, u: str, v: str, datos: dict) -> str:
    return (
        f"<div style='font-family:system-ui;font-size:12px'>"
        f"<b>{G.nodes[u]['nombre']} &rarr; {G.nodes[v]['nombre']}</b><br>"
        f"Linea {datos['linea']} &middot; {config.NOMBRE_MODO[datos['modo']]}<br>"
        f"{datos['distancia_km']:.2f} km &middot; "
        f"{datos['tiempo_base_min']:.1f} min (base)"
        f"</div>"
    )


# --------------------------------------------------------------------------- #
# Capas
# --------------------------------------------------------------------------- #
def _dibujar_red(mapa: folium.Map, G: nx.MultiDiGraph, tramos_en_ruta: set) -> None:
    """Capa base: todos los tramos, recesivos, coloreados por modo."""
    dibujados = set()

    for u, v, datos in G.edges(data=True):
        clave = (frozenset((u, v)), datos["linea"])
        if clave in dibujados:
            continue          # el tramo inverso ya se dibujo
        dibujados.add(clave)

        activo = datos.get("activa", True)
        en_ruta = (u, v, datos["linea"]) in tramos_en_ruta

        folium.PolyLine(
            locations=[_coord(G, u), _coord(G, v)],
            color=config.COLOR_MODO[datos["modo"]] if activo else COLOR_ESTACION_INACTIVA,
            weight=2,
            opacity=0.30 if (en_ruta or not activo) else 0.75,
            dash_array=config.ESTILO_MODO.get(datos["modo"]),
            tooltip=f"{G.nodes[u]['nombre']} - {G.nodes[v]['nombre']} ({datos['linea']})",
            popup=folium.Popup(_popup_tramo(G, u, v, datos), max_width=280),
        ).add_to(mapa)


def _dibujar_estaciones(
    mapa: folium.Map,
    G: nx.MultiDiGraph,
    origen: Optional[str],
    destino: Optional[str],
    en_ruta: set,
) -> None:
    """Marcadores de estacion. El tamano codifica el papel en la consulta."""
    for nodo, d in G.nodes(data=True):
        activa = d.get("activa", True)
        es_extremo = nodo in (origen, destino)

        if not activa:
            color, radio, relleno = COLOR_ESTACION_INACTIVA, 4, 0.9
        elif es_extremo:
            color, radio, relleno = COLOR_ESTACION_EXTREMO, 7, 1.0
        elif nodo in en_ruta:
            color, radio, relleno = config.COLOR_MODO[d["modo"]], 5, 1.0
        else:
            color, radio, relleno = config.COLOR_MODO[d["modo"]], 3, 0.55

        folium.CircleMarker(
            location=_coord(G, nodo),
            radius=radio,
            color=COLOR_RUTA_BORDE,
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=relleno,
            tooltip=d["nombre"],
            popup=folium.Popup(_popup_estacion(G, nodo), max_width=300),
        ).add_to(mapa)


def _dibujar_ruta(mapa: folium.Map, G: nx.MultiDiGraph, ruta: Ruta) -> None:
    """
    Capa destacada: la ruta optima, tramo a tramo y con el color de cada modo.

    Se dibuja en dos pasadas -primero un reborde blanco ancho, luego la linea de
    color- para que la ruta se lea sobre cualquier fondo del mapa.
    """
    if not ruta.existe or not ruta.tramos:
        return

    for tramo in ruta.tramos:
        puntos = [_coord(G, tramo.origen), _coord(G, tramo.destino)]
        folium.PolyLine(puntos, color=COLOR_RUTA_BORDE, weight=11, opacity=0.95).add_to(mapa)

    for i, tramo in enumerate(ruta.tramos, 1):
        puntos = [_coord(G, tramo.origen), _coord(G, tramo.destino)]
        folium.PolyLine(
            locations=puntos,
            color=config.COLOR_MODO[tramo.modo],
            weight=6,
            opacity=1.0,
            dash_array=config.ESTILO_MODO.get(tramo.modo),
            tooltip=(
                f"{i}. {tramo.nombre_origen} &rarr; {tramo.nombre_destino} "
                f"({tramo.linea}, {tramo.minutos:.1f} min)"
            ),
        ).add_to(mapa)


def _dibujar_marcas(mapa: folium.Map, G: nx.MultiDiGraph, marcas: Sequence[dict]) -> None:
    """Marcas puntuales sobre el mapa (estaciones criticas, cierres, propuestas)."""
    for marca in marcas:
        folium.CircleMarker(
            location=_coord(G, marca["estacion"]),
            radius=marca.get("radio", 10),
            color=marca.get("color", "#111827"),
            weight=2.5,
            fill=True,
            fill_color=marca.get("color", "#111827"),
            fill_opacity=0.25,
            tooltip=marca.get("texto", G.nodes[marca["estacion"]]["nombre"]),
        ).add_to(mapa)


def _dibujar_propuestas(
    mapa: folium.Map, G: nx.MultiDiGraph, propuestas: Sequence[dict]
) -> None:
    """Conexiones hipoteticas del reto de optimizacion, en trazo punteado."""
    for p in propuestas:
        folium.PolyLine(
            locations=[_coord(G, p["origen"]), _coord(G, p["destino"])],
            color=COLOR_ESTACION_EXTREMO,
            weight=4,
            opacity=0.9,
            dash_array="6, 8",
            tooltip=(
                f"Propuesta: {p['nombre_origen']} - {p['nombre_destino']} "
                f"({p['km_de_via_nueva']:.1f} km, mejora {p['mejora_red_%']:.2f}%)"
            ),
        ).add_to(mapa)


# --------------------------------------------------------------------------- #
# API publica
# --------------------------------------------------------------------------- #
def mapa_de_la_red(
    G: nx.MultiDiGraph,
    ruta: Optional[Ruta] = None,
    origen: Optional[str] = None,
    destino: Optional[str] = None,
    marcas: Sequence[dict] = (),
    propuestas: Sequence[dict] = (),
) -> folium.Map:
    """
    Construye el mapa: red completa, ruta destacada y marcas opcionales.

    El encuadre se ajusta a la ruta cuando hay una, y a la red completa cuando no,
    para que el usuario no tenga que buscar el resultado en el mapa.
    """
    mapa = folium.Map(
        location=CENTRO_MEDELLIN,
        zoom_start=ZOOM_INICIAL,
        tiles=TILES,
        control_scale=True,
    )

    tramos_en_ruta = set()
    estaciones_en_ruta = set()
    if ruta is not None and ruta.existe:
        tramos_en_ruta = {(t.origen, t.destino, t.linea) for t in ruta.tramos}
        tramos_en_ruta |= {(t.destino, t.origen, t.linea) for t in ruta.tramos}
        estaciones_en_ruta = set(ruta.estaciones)

    _dibujar_red(mapa, G, tramos_en_ruta)
    if ruta is not None:
        _dibujar_ruta(mapa, G, ruta)
    _dibujar_estaciones(mapa, G, origen, destino, estaciones_en_ruta)
    _dibujar_propuestas(mapa, G, propuestas)
    _dibujar_marcas(mapa, G, marcas)

    puntos = [
        _coord(G, n) for n in (estaciones_en_ruta or G.nodes)
    ]
    if puntos:
        mapa.fit_bounds(puntos, padding=(30, 30))

    return mapa


def leyenda_html(modos: Iterable[str] = None) -> str:
    """
    Leyenda de modos: color + patron de trazo + nombre.

    La identidad nunca queda solo en el color, que es el requisito de
    accesibilidad de la paleta.
    """
    modos = list(modos or ("metro", "tranvia", "cable", "bus", "peatonal"))
    filas: List[str] = []

    for modo in modos:
        patron = config.ESTILO_MODO.get(modo)
        trazo = f'stroke-dasharray="{patron}"' if patron else ""
        filas.append(
            f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0'>"
            f"<svg width='34' height='10'>"
            f"<line x1='1' y1='5' x2='33' y2='5' "
            f"stroke='{config.COLOR_MODO[modo]}' stroke-width='3' {trazo}/></svg>"
            f"<span style='font-size:12px;color:#374151'>"
            f"{config.NOMBRE_MODO[modo]}</span></div>"
        )

    return (
        "<div style='font-family:system-ui;border:1px solid #E5E7EB;"
        "border-radius:8px;padding:10px 12px;background:#FFFFFF'>"
        "<div style='font-size:11px;text-transform:uppercase;letter-spacing:.05em;"
        "color:#6B7280;margin-bottom:6px'>Modos de transporte</div>"
        + "".join(filas) +
        "</div>"
    )
