"""
Algoritmo de Dijkstra sobre el espacio de estados (estacion, linea).

La funcion de peso es estrictamente positiva para toda arista, que es la
condicion de validez de Dijkstra: no se necesita Bellman-Ford (pesos negativos)
ni se justifica el O(|V|^3) de Floyd-Warshall (todos contra todos).

Se implementa explicitamente porque el peso de una arista depende del estado con
que se llega al nodo, algo que `networkx.shortest_path` no admite. Con cola de
prioridad binaria la complejidad es O((|S| + |E_S|) log |S|).
"""

import heapq
from itertools import count
from typing import Dict, Optional, Tuple

import networkx as nx

from src.algoritmos.espacio_estados import Estado, EspacioEstados
from src.algoritmos.reconstruccion import construir_ruta
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed


def dijkstra(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    condiciones: CondicionesRed = None,
    aristas_prohibidas: frozenset = frozenset(),
    nodos_prohibidos: frozenset = frozenset(),
) -> Ruta:
    """
    Camino de peso minimo entre `origen` y `destino`.

    `aristas_prohibidas` y `nodos_prohibidos` permiten que Yen y el analisis de
    resiliencia reutilicen este algoritmo sin modificar el grafo. Si no hay
    camino, `Ruta.existe` es False.
    """
    _validar(G, origen, destino)
    condiciones = condiciones or CondicionesRed()

    if origen == destino:
        # Sin este corte, la parada temprana ignoraria el estado inicial y la
        # busqueda devolveria un ciclo de ida y vuelta en vez del camino vacio.
        return Ruta(
            origen=origen,
            destino=destino,
            algoritmo="Dijkstra",
            criterio=condiciones.criterio,
            perfil_horario=condiciones.perfil_horario,
        )

    espacio = EspacioEstados(G, condiciones)
    inicio: Estado = espacio.estado_inicial(origen)

    distancia: Dict[Estado, float] = {inicio: 0.0}
    predecesor: Dict[Estado, Tuple[Estado, dict]] = {}
    visitados = set()
    expandidos = 0

    orden = count()                       # desempate determinista
    cola = [(0.0, next(orden), inicio)]

    estado_final: Optional[Estado] = None
    peso_final = 0.0

    while cola:
        d_actual, _, estado = heapq.heappop(cola)

        if estado in visitados:           # entrada obsoleta (lazy deletion)
            continue
        visitados.add(estado)
        expandidos += 1

        # Parada temprana: al extraer la meta, su distancia ya es la minima.
        if espacio.es_meta(estado, destino) and estado != inicio:
            estado_final, peso_final = estado, d_actual
            break

        for sucesor, peso, datos in espacio.sucesores(estado):
            if sucesor in visitados:
                continue
            if sucesor[0] in nodos_prohibidos:
                continue
            if (estado[0], sucesor[0], datos["linea"]) in aristas_prohibidas:
                continue

            nueva = d_actual + peso
            if nueva < distancia.get(sucesor, float("inf")):     # relajacion
                distancia[sucesor] = nueva
                predecesor[sucesor] = (estado, datos)
                heapq.heappush(cola, (nueva, next(orden), sucesor))

    return construir_ruta(
        espacio, predecesor, estado_final, origen, destino,
        peso_final, "Dijkstra", expandidos,
    )


def dijkstra_todos_los_destinos(
    G: nx.MultiDiGraph, origen: str, condiciones: CondicionesRed = None
) -> Dict[str, float]:
    """
    Distancia minima desde `origen` a todas las estaciones, sin parada temprana.

    Una sola ejecucion resuelve un origen contra el resto de la red; es la forma
    que usa el analisis de resiliencia.
    """
    _validar(G, origen, origen)
    condiciones = condiciones or CondicionesRed()
    espacio = EspacioEstados(G, condiciones)

    inicio = espacio.estado_inicial(origen)
    distancia = {inicio: 0.0}
    visitados = set()
    mejor_por_nodo: Dict[str, float] = {origen: 0.0}

    orden = count()
    cola = [(0.0, next(orden), inicio)]

    while cola:
        d_actual, _, estado = heapq.heappop(cola)
        if estado in visitados:
            continue
        visitados.add(estado)

        nodo = estado[0]
        if d_actual < mejor_por_nodo.get(nodo, float("inf")):
            mejor_por_nodo[nodo] = d_actual

        for sucesor, peso, _ in espacio.sucesores(estado):
            nueva = d_actual + peso
            if nueva < distancia.get(sucesor, float("inf")):
                distancia[sucesor] = nueva
                heapq.heappush(cola, (nueva, next(orden), sucesor))

    return mejor_por_nodo


def _validar(G: nx.MultiDiGraph, origen: str, destino: str) -> None:
    for nodo in (origen, destino):
        if nodo not in G:
            raise KeyError(f"La estacion {nodo} no existe en la red")
