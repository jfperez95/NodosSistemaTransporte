"""
Algoritmo de Yen: las k mejores rutas alternativas.

La segunda mejor ruta es el mejor camino que no sea igual al primero. Para cada
ruta aceptada y cada nodo de desvio se prohiben las aristas que reproducirian un
camino conocido y los nodos anteriores al desvio, y se corre Dijkstra desde ahi;
la raiz mas el desvio forman una candidata.

Complejidad: O(k |V| (|E| + |V| log |V|)). Ademas del orden por peso se aplica un
filtro de disimilitud, porque dos rutas casi identicas no son alternativas utiles.
"""

from dataclasses import replace
from typing import List

import networkx as nx

from src.algoritmos.dijkstra import dijkstra
from src.algoritmos.evaluacion import evaluar_ruta
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed


def _firma(ruta: Ruta) -> tuple:
    """Identidad de una ruta: su secuencia de estaciones y lineas."""
    return tuple((t.origen, t.destino, t.linea) for t in ruta.tramos)


def _firma_prefijo(ruta: Ruta, i: int) -> tuple:
    """Identidad de los primeros `i` tramos de una ruta (su raiz)."""
    return tuple((t.origen, t.destino, t.linea) for t in ruta.tramos[:i])


def _similitud(a: Ruta, b: Ruta) -> float:
    """Fraccion de estaciones compartidas (indice de Jaccard) entre dos rutas."""
    ea, eb = set(a.estaciones), set(b.estaciones)
    if not ea or not eb:
        return 0.0
    return len(ea & eb) / len(ea | eb)


def k_rutas_alternativas(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    k: int = 3,
    condiciones: CondicionesRed = None,
    max_similitud: float = 0.9,
) -> List[Ruta]:
    """
    Devuelve hasta `k` rutas distintas ordenadas de mejor a peor.

    `max_similitud` descarta alternativas demasiado parecidas a una ruta ya
    aceptada; con 1.0 se obtiene el comportamiento clasico de Yen.
    """
    if k < 1:
        raise ValueError("k debe ser al menos 1")

    condiciones = condiciones or CondicionesRed()

    mejor = dijkstra(G, origen, destino, condiciones)
    if not mejor.existe:
        return [mejor]

    aceptadas: List[Ruta] = [mejor]
    candidatas: List[Ruta] = []
    firmas_vistas = {_firma(mejor)}

    while len(aceptadas) < k:
        ultima = aceptadas[-1]
        estaciones = ultima.estaciones

        for i in range(len(estaciones) - 1):
            nodo_desvio = estaciones[i]
            raiz = ultima.tramos[:i]

            aristas_prohibidas = set()
            for ruta in aceptadas:
                if _firma_prefijo(ruta, i) == _firma_prefijo(ultima, i):
                    if len(ruta.tramos) > i:
                        t = ruta.tramos[i]
                        aristas_prohibidas.add((t.origen, t.destino, t.linea))

            nodos_prohibidos = frozenset(estaciones[:i])

            desvio = dijkstra(
                G, nodo_desvio, destino, condiciones,
                aristas_prohibidas=frozenset(aristas_prohibidas),
                nodos_prohibidos=nodos_prohibidos,
            )
            if not desvio.existe or not desvio.tramos:
                continue

            candidata = Ruta(
                origen=origen,
                destino=destino,
                tramos=[replace(t) for t in raiz] + [replace(t) for t in desvio.tramos],
                algoritmo="Yen (k rutas)",
                criterio=condiciones.criterio,
                perfil_horario=condiciones.perfil_horario,
                nodos_expandidos=desvio.nodos_expandidos,
            )
            # El desvio se calculo aparte: hay que reevaluar el itinerario
            # completo para contar bien el transbordo del punto de union.
            evaluar_ruta(G, candidata, condiciones)

            firma = _firma(candidata)
            if firma in firmas_vistas:
                continue
            firmas_vistas.add(firma)
            candidatas.append(candidata)

        if not candidatas:
            break

        candidatas.sort(key=lambda r: r.peso_total)

        siguiente = None
        for idx, cand in enumerate(candidatas):
            if all(_similitud(cand, a) <= max_similitud for a in aceptadas):
                siguiente = candidatas.pop(idx)
                break

        if siguiente is None:
            break
        aceptadas.append(siguiente)

    return aceptadas
