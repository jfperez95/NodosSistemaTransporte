"""
BFS sobre el grafo de lineas: minimo numero de transbordos.

Motivacion
----------
"Menos transbordos" se puede aproximar con Dijkstra dandole al transbordo una
penalizacion enorme, y asi lo hace el criterio `transbordos` de `config.py`. Pero
existe una formulacion exacta y mas barata: si el costo de una ruta es
simplemente *cuantas veces se cambia de linea*, entonces todas las aristas valen
1 en un grafo auxiliar y el camino minimo se obtiene con BUSQUEDA EN AMPLITUD.

BFS recorre el grafo por niveles usando una COLA (FIFO), como indica la guia del
curso, y garantiza encontrar el camino con menos aristas en O(|V| + |E|), sin el
factor logaritmico de la cola de prioridad.

Grafo auxiliar
--------------
  * Vertices: las lineas de servicio (A, B, K, J, T, ...).
  * Aristas: dos lineas son adyacentes si comparten al menos una estacion, o si
    un transbordo a pie une una estacion de cada una; es decir, si es posible
    pasar directamente de una a otra.

El numero minimo de transbordos entre dos estaciones es entonces la distancia en
ese grafo entre el conjunto de lineas del origen y el del destino. El resultado
sirve para verificar de forma independiente lo que devuelve Dijkstra: si ambos
coinciden, la implementacion multicriterio esta contando bien los transbordos.
"""

from collections import deque
from typing import Dict, List, Optional, Set

import networkx as nx

from src.algoritmos.dijkstra import dijkstra
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed


def construir_grafo_de_lineas(G: nx.MultiDiGraph) -> Dict[str, Set[str]]:
    """
    Lista de adyacencia del grafo auxiliar de lineas.

    {linea: {lineas con las que comparte al menos una estacion}}
    """
    adyacencia: Dict[str, Set[str]] = {}

    # (a) Dos lineas son adyacentes si comparten una estacion.
    for _, datos in G.nodes(data=True):
        lineas = set(datos["lineas"])
        for linea in lineas:
            adyacencia.setdefault(linea, set()).update(lineas - {linea})

    # (b) Tambien lo son si un transbordo a pie une una estacion de una con una
    #     estacion de la otra: caminar entre andenes sigue siendo un transbordo.
    for u, v, datos in G.edges(data=True):
        if datos["tipo"] != "transbordo_peatonal":
            continue
        for lu in G.nodes[u]["lineas"]:
            for lv in G.nodes[v]["lineas"]:
                if lu == lv:
                    continue
                adyacencia.setdefault(lu, set()).add(lv)
                adyacencia.setdefault(lv, set()).add(lu)

    return adyacencia


def minimos_transbordos(G: nx.MultiDiGraph, origen: str, destino: str) -> Optional[int]:
    """
    Numero minimo de cambios de linea entre dos estaciones, via BFS.

    Devuelve 0 si comparten linea, y None si no hay forma de conectarlas.
    """
    lineas_origen = set(G.nodes[origen]["lineas"])
    lineas_destino = set(G.nodes[destino]["lineas"])

    if not lineas_origen or not lineas_destino:
        return None
    if lineas_origen & lineas_destino:
        return 0

    adyacencia = construir_grafo_de_lineas(G)

    # BFS multi-origen: se arranca simultaneamente desde todas las lineas que
    # pasan por la estacion de origen.
    cola = deque((linea, 0) for linea in lineas_origen)
    visitadas = set(lineas_origen)

    while cola:
        linea, nivel = cola.popleft()
        for vecina in adyacencia.get(linea, ()):
            if vecina in visitadas:
                continue
            if vecina in lineas_destino:
                return nivel + 1
            visitadas.add(vecina)
            cola.append((vecina, nivel + 1))

    return None


def camino_de_lineas(G: nx.MultiDiGraph, origen: str, destino: str) -> Optional[List[str]]:
    """Secuencia de lineas a tomar que realiza el minimo numero de transbordos."""
    lineas_origen = set(G.nodes[origen]["lineas"])
    lineas_destino = set(G.nodes[destino]["lineas"])

    if not lineas_origen or not lineas_destino:
        return None
    comunes = lineas_origen & lineas_destino
    if comunes:
        return [sorted(comunes)[0]]

    adyacencia = construir_grafo_de_lineas(G)
    predecesor: Dict[str, Optional[str]] = {l: None for l in lineas_origen}
    cola = deque(sorted(lineas_origen))

    while cola:
        linea = cola.popleft()
        for vecina in sorted(adyacencia.get(linea, ())):
            if vecina in predecesor:
                continue
            predecesor[vecina] = linea
            if vecina in lineas_destino:
                camino = [vecina]
                while predecesor[camino[-1]] is not None:
                    camino.append(predecesor[camino[-1]])
                return list(reversed(camino))
            cola.append(vecina)

    return None


def bfs_minimos_transbordos(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    condiciones: CondicionesRed = None,
) -> Ruta:
    """
    Ruta concreta que minimiza los transbordos.

    BFS entrega el numero optimo de cambios de linea, pero no un itinerario
    estacion por estacion. La ruta final se obtiene con Dijkstra bajo el criterio
    `transbordos` y se ETIQUETA con la cota calculada por BFS, de modo que la
    interfaz puede advertir si ambas medidas difieren.
    """
    condiciones = condiciones or CondicionesRed(criterio="transbordos")
    if condiciones.criterio != "transbordos":
        condiciones = CondicionesRed(
            perfil_horario=condiciones.perfil_horario,
            criterio="transbordos",
            factor_clima=condiciones.factor_clima,
            evitar_modos=condiciones.evitar_modos,
        )

    ruta = dijkstra(G, origen, destino, condiciones)
    ruta.algoritmo = "BFS(lineas) + Dijkstra"

    cota = minimos_transbordos(G, origen, destino)
    if ruta.existe and cota is not None and ruta.num_transbordos > cota:
        ruta.motivo = (
            f"BFS demuestra que bastan {cota} transbordo(s); la ruta encontrada "
            f"usa {ruta.num_transbordos} por restricciones de tiempo o filtros"
        )
    return ruta
