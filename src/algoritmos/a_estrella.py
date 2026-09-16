"""
Algoritmo A* con heuristica geografica.

Idea
----
A* es Dijkstra guiado: en vez de ordenar la cola por g(n) -el costo acumulado-,
la ordena por

        f(n) = g(n) + h(n)

donde h(n) es una estimacion optimista de lo que falta para llegar al destino.
Aqui h(n) se obtiene de la distancia en linea recta (Haversine) entre la estacion
n y el destino, convertida a minutos suponiendo la velocidad maxima del sistema.

Admisibilidad y optimalidad
---------------------------
Ninguna ruta real puede ser mas corta que la linea recta ni mas rapida que la
velocidad maxima, luego h(n) <= h*(n) para todo n: la heuristica es ADMISIBLE y
A* devuelve el mismo camino optimo que Dijkstra. Ademas h cumple la desigualdad
triangular sobre la distancia geografica, es decir es CONSISTENTE, por lo que
basta con expandir cada estado una sola vez.

La heuristica se escala por `alfa_tiempo` del criterio activo para mantenerse en
las mismas unidades que el peso, y se anula cuando el criterio no es temporal
(costo o transbordos), caso en el que A* degenera -correctamente- en Dijkstra.
Esta comparacion Dijkstra vs A* es la que reporta `benchmark.py`.
"""

import heapq
from itertools import count
from typing import Dict, Optional, Tuple

import networkx as nx

from src.algoritmos.espacio_estados import Estado, EspacioEstados
from src.algoritmos.reconstruccion import construir_ruta
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed
from src.utils.geo import cota_inferior_minutos


def a_estrella(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    condiciones: CondicionesRed = None,
) -> Ruta:
    """Camino de peso minimo usando A* con heuristica Haversine admisible."""
    for nodo in (origen, destino):
        if nodo not in G:
            raise KeyError(f"La estacion {nodo} no existe en la red")

    condiciones = condiciones or CondicionesRed()

    if origen == destino:
        # Caso limite: el viaje trivial. Sin este corte, la parada temprana
        # ignoraria el estado inicial y la busqueda devolveria un ciclo de ida y
        # vuelta en vez del camino vacio.
        return Ruta(
            origen=origen,
            destino=destino,
            algoritmo="A*",
            criterio=condiciones.criterio,
            perfil_horario=condiciones.perfil_horario,
        )

    espacio = EspacioEstados(G, condiciones)

    lat_meta = G.nodes[destino]["latitud"]
    lon_meta = G.nodes[destino]["longitud"]
    escala = condiciones.coeficientes["alfa_tiempo"]

    def h(nodo: str) -> float:
        """Estimacion optimista del peso restante desde `nodo` hasta el destino."""
        if escala <= 0:
            return 0.0
        datos = G.nodes[nodo]
        minutos = cota_inferior_minutos(
            datos["latitud"], datos["longitud"], lat_meta, lon_meta
        )
        return escala * minutos

    inicio: Estado = espacio.estado_inicial(origen)

    g: Dict[Estado, float] = {inicio: 0.0}
    predecesor: Dict[Estado, Tuple[Estado, dict]] = {}
    cerrados = set()
    expandidos = 0

    orden = count()
    cola = [(h(origen), next(orden), inicio)]   # (f, orden, estado)

    estado_final: Optional[Estado] = None
    peso_final = 0.0

    while cola:
        _, _, estado = heapq.heappop(cola)

        if estado in cerrados:
            continue
        cerrados.add(estado)
        expandidos += 1

        if espacio.es_meta(estado, destino) and estado != inicio:
            estado_final, peso_final = estado, g[estado]
            break

        for sucesor, peso, datos in espacio.sucesores(estado):
            if sucesor in cerrados:
                continue
            tentativo = g[estado] + peso
            if tentativo < g.get(sucesor, float("inf")):
                g[sucesor] = tentativo
                predecesor[sucesor] = (estado, datos)
                heapq.heappush(cola, (tentativo + h(sucesor[0]), next(orden), sucesor))

    return construir_ruta(
        espacio, predecesor, estado_final, origen, destino,
        peso_final, "A*", expandidos,
    )
