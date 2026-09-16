"""
Reto avanzado 3 - Optimizacion de la red: donde convendria construir.

La pregunta
-----------
Que par de estaciones esta *geograficamente cerca pero topologicamente lejos*?
Esos son los huecos de la red: dos puntos separados por pocos kilometros que
obligan a un rodeo de media hora porque no hay conexion directa.

La medida: factor de rodeo
--------------------------
Para cada par (u, v) no adyacente se compara

    rodeo(u, v) = tiempo_real_en_la_red(u, v) / tiempo_ideal_en_linea_recta(u, v)

El denominador es la cota inferior Haversine que ya usa A*. Un rodeo de 1.2
significa que la red es casi optima para ese par; un rodeo de 6 significa que el
usuario da una vuelta enorme para cubrir una distancia corta.

Los pares con mayor rodeo *y* con distancia fisica construible son los candidatos
naturales a una nueva conexion.

La verificacion
---------------
Proponer no basta: hay que demostrar que sirve. `evaluar_propuesta` agrega la
arista al grafo, recalcula el tiempo promedio de la red sobre la misma muestra de
origenes que usa el analisis de resiliencia, y reporta la mejora real. Una
propuesta que no mejora el promedio se descarta, por atractiva que parezca.
"""

from typing import Iterable, List, Optional, Sequence, Tuple

import networkx as nx

from src.analisis.resiliencia import MUESTRA_ORIGENES, _tiempos_desde_muestra
from src.algoritmos.dijkstra import dijkstra, dijkstra_todos_los_destinos
from src.modelo.pesos import CondicionesRed
from src.utils.geo import cota_inferior_minutos, haversine_km

# Una conexion nueva solo es plausible si es fisicamente construible: ni tan
# corta que no aporte, ni tan larga que equivalga a una linea entera.
DISTANCIA_MIN_PROPUESTA_KM = 0.8
DISTANCIA_MAX_PROPUESTA_KM = 6.0

# Parametros del servicio hipotetico que se construiria.
VELOCIDAD_PROPUESTA_KMH = 28.0
MODO_PROPUESTA = "tranvia"
LINEA_PROPUESTA = "NUEVA"


def detectar_brechas(
    G: nx.MultiDiGraph,
    condiciones: CondicionesRed = None,
    top: int = 10,
    origenes: Sequence[str] = MUESTRA_ORIGENES,
) -> List[dict]:
    """
    Pares de estaciones con mayor factor de rodeo.

    Se limita a los pares que salen de la muestra de origenes para no evaluar las
    61x60 combinaciones: una ejecucion de `dijkstra_todos_los_destinos` por origen
    entrega de una vez todas sus distancias.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")
    brechas = []

    for origen in origenes:
        distancias = dijkstra_todos_los_destinos(G, origen, condiciones)
        lat_o = G.nodes[origen]["latitud"]
        lon_o = G.nodes[origen]["longitud"]

        for destino, minutos in distancias.items():
            if destino == origen or G.has_edge(origen, destino):
                continue

            lat_d = G.nodes[destino]["latitud"]
            lon_d = G.nodes[destino]["longitud"]

            km = haversine_km(lat_o, lon_o, lat_d, lon_d)
            if not DISTANCIA_MIN_PROPUESTA_KM <= km <= DISTANCIA_MAX_PROPUESTA_KM:
                continue

            ideal = cota_inferior_minutos(lat_o, lon_o, lat_d, lon_d)
            if ideal <= 0:
                continue

            brechas.append({
                "origen": origen,
                "destino": destino,
                "nombre_origen": G.nodes[origen]["nombre"],
                "nombre_destino": G.nodes[destino]["nombre"],
                "km_linea_recta": round(km, 2),
                "minutos_en_la_red": round(minutos, 1),
                "minutos_ideales": round(ideal, 1),
                "factor_rodeo": round(minutos / ideal, 2),
            })

    brechas.sort(key=lambda b: b["factor_rodeo"], reverse=True)

    # Se elimina el par simetrico: (u,v) y (v,u) describen la misma brecha.
    vistos = set()
    unicas = []
    for b in brechas:
        clave = frozenset((b["origen"], b["destino"]))
        if clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(b)

    return unicas[:top]


def agregar_conexion(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    modo: str = MODO_PROPUESTA,
    linea: str = LINEA_PROPUESTA,
    velocidad_kmh: float = VELOCIDAD_PROPUESTA_KMH,
) -> nx.MultiDiGraph:
    """
    Copia del grafo con una conexion hipotetica nueva, en ambos sentidos.

    El tiempo del tramo se deriva de la distancia real y de la velocidad del
    servicio propuesto, con el mismo factor de trazado 1.15 que usa el generador
    del dataset: la via nueva tampoco seria una linea recta perfecta.
    """
    for nodo in (origen, destino):
        if nodo not in G:
            raise KeyError(f"La estacion {nodo} no existe en la red")
    if origen == destino:
        raise ValueError("Una conexion debe unir dos estaciones distintas")

    H = G.copy()
    km = haversine_km(
        G.nodes[origen]["latitud"], G.nodes[origen]["longitud"],
        G.nodes[destino]["latitud"], G.nodes[destino]["longitud"],
    ) * 1.15
    minutos = km / velocidad_kmh * 60

    for u, v in ((origen, destino), (destino, origen)):
        H.add_edge(
            u, v, key=linea,
            linea=linea, modo=modo, tipo="via",
            tiempo_base_min=round(minutos, 2),
            distancia_km=round(km, 3),
            capacidad_pasajeros_hora=3500,
            activa=True,
        )

    # El indice de lineas por estacion debe reflejar el servicio nuevo.
    for nodo in (origen, destino):
        lineas = set(H.nodes[nodo]["lineas"]) | {linea}
        H.nodes[nodo]["lineas"] = tuple(sorted(lineas))
        H.nodes[nodo]["es_intercambio"] = len(lineas) > 1

    return H


def evaluar_propuesta(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    condiciones: CondicionesRed = None,
    origenes: Sequence[str] = MUESTRA_ORIGENES,
    modo: str = MODO_PROPUESTA,
    velocidad_kmh: float = VELOCIDAD_PROPUESTA_KMH,
) -> dict:
    """
    Mide el impacto global de construir la conexion propuesta.

    Reporta la mejora del tiempo promedio de viaje en toda la red, no solo entre
    las dos estaciones unidas: una conexion puede ser espectacular para un par y
    marginal para el sistema, y esa distincion es la que justifica una inversion.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")

    antes_promedio, _ = _tiempos_desde_muestra(G, condiciones, origenes)
    ruta_antes = dijkstra(G, origen, destino, condiciones)

    H = agregar_conexion(G, origen, destino, modo=modo, velocidad_kmh=velocidad_kmh)
    despues_promedio, _ = _tiempos_desde_muestra(H, condiciones, origenes)
    ruta_despues = dijkstra(H, origen, destino, condiciones)

    km = haversine_km(
        G.nodes[origen]["latitud"], G.nodes[origen]["longitud"],
        G.nodes[destino]["latitud"], G.nodes[destino]["longitud"],
    ) * 1.15

    mejora_par = None
    if ruta_antes.existe and ruta_despues.existe:
        mejora_par = round(
            ruta_antes.minutos_totales - ruta_despues.minutos_totales, 2
        )

    return {
        "origen": origen,
        "destino": destino,
        "nombre_origen": G.nodes[origen]["nombre"],
        "nombre_destino": G.nodes[destino]["nombre"],
        "km_de_via_nueva": round(km, 2),
        "modo": modo,
        "minutos_par_antes": ruta_antes.minutos_totales if ruta_antes.existe else None,
        "minutos_par_despues": ruta_despues.minutos_totales if ruta_despues.existe else None,
        "mejora_par_min": mejora_par,
        "promedio_red_antes": round(antes_promedio, 2),
        "promedio_red_despues": round(despues_promedio, 2),
        "mejora_red_%": round(
            100 * (antes_promedio - despues_promedio) / antes_promedio, 2
        ),
        # Indicador de eficiencia de la inversion: minutos ahorrados por cada
        # kilometro de via que habria que construir.
        "mejora_por_km": round(
            (antes_promedio - despues_promedio) / km, 4
        ) if km > 0 else None,
    }


def proponer_conexiones(
    G: nx.MultiDiGraph,
    condiciones: CondicionesRed = None,
    candidatos: int = 8,
    devolver: int = 3,
    origenes: Sequence[str] = MUESTRA_ORIGENES,
) -> List[dict]:
    """
    Detecta brechas, evalua las mas prometedoras y devuelve las que si mejoran.

    Flujo completo del reto: DETECTAR -> SIMULAR -> ORDENAR POR BENEFICIO REAL.
    Solo se devuelven propuestas con mejora positiva del promedio de la red.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")
    brechas = detectar_brechas(G, condiciones, top=candidatos, origenes=origenes)

    evaluadas = []
    for b in brechas:
        resultado = evaluar_propuesta(
            G, b["origen"], b["destino"], condiciones, origenes
        )
        resultado["factor_rodeo_previo"] = b["factor_rodeo"]
        if resultado["mejora_red_%"] > 0:
            evaluadas.append(resultado)

    evaluadas.sort(key=lambda r: r["mejora_red_%"], reverse=True)
    return evaluadas[:devolver]
