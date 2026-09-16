"""
Algoritmo de Yen: las k mejores rutas alternativas.

El MVP exige "permitir la visualizacion de rutas alternativas". Mostrar varias
rutas no es repetir Dijkstra: el segundo mejor camino debe ser el mejor camino
que NO sea igual al primero.

Yen resuelve esto sin modificar Dijkstra. Para cada ruta ya aceptada y cada nodo
de desvio (spur node) sobre ella:

  1. Se prohiben las aristas que reproducirian un camino ya conocido.
  2. Se prohiben los nodos anteriores al desvio, para no generar ciclos.
  3. Se corre Dijkstra desde el nodo de desvio hasta el destino.
  4. La raiz (tramo comun) mas el desvio forman una ruta candidata.

Las candidatas se guardan en una lista ordenada y la mejor pasa a ser la
siguiente ruta oficial. Complejidad: O(k |V| (|E| + |V| log |V|)), es decir k
ejecuciones de Dijkstra por cada nodo de desvio.

Ademas del orden por peso, se ofrece un filtro de DISIMILITUD: dos rutas que
comparten el 90 % de sus estaciones no son alternativas utiles para un usuario,
asi que se descartan las demasiado parecidas a las ya elegidas.
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

    `max_similitud` descarta alternativas que se parezcan demasiado a una ruta ya
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

            # 1. Prohibir las aristas que regenerarian una ruta ya conocida.
            aristas_prohibidas = set()
            for ruta in aceptadas:
                if _firma_prefijo(ruta, i) == _firma_prefijo(ultima, i):
                    if len(ruta.tramos) > i:
                        t = ruta.tramos[i]
                        aristas_prohibidas.add((t.origen, t.destino, t.linea))

            # 2. Prohibir los nodos de la raiz, para evitar ciclos.
            nodos_prohibidos = frozenset(estaciones[:i])

            desvio = dijkstra(
                G, nodo_desvio, destino, condiciones,
                aristas_prohibidas=frozenset(aristas_prohibidas),
                nodos_prohibidos=nodos_prohibidos,
            )
            if not desvio.existe or not desvio.tramos:
                continue

            # 3. Unir raiz + desvio en una ruta candidata completa.
            candidata = Ruta(
                origen=origen,
                destino=destino,
                tramos=[replace(t) for t in raiz] + [replace(t) for t in desvio.tramos],
                algoritmo="Yen (k rutas)",
                criterio=condiciones.criterio,
                perfil_horario=condiciones.perfil_horario,
                nodos_expandidos=desvio.nodos_expandidos,
            )
            # El desvio se calculo como un viaje independiente: hay que reevaluar
            # el itinerario completo para que el transbordo y la tarifa del punto
            # de union queden bien contados.
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
