"""
Espacio de estados sobre el que corren los algoritmos de busqueda.

El problema
-----------
El peso de un tramo NO depende solo de la arista: depende tambien de COMO llego
el pasajero al nodo de origen. Tomar A11 -> B01 cuesta 2 minutos si el pasajero
ya venia en la linea B, y 2 + 4 minutos si venia en la linea A y debe cambiar de
anden. Un Dijkstra clasico sobre los nodos del grafo no puede representar eso.

La solucion
-----------
Se ejecuta la busqueda sobre el grafo de estados

        S = V x (L U {None})

donde un estado (u, l) significa "estar en la estacion u habiendo llegado por la
linea l". El estado inicial es (origen, None) -el pasajero aun no ha abordado- y
son estados meta todos los (destino, *).

Este grafo de estados es a lo sumo |L| veces mas grande que G, pero como cada
estacion sirve a pocas lineas (1 a 3), en la practica |S| ~ 1.2 |V|. El costo es
despreciable y a cambio el conteo de transbordos es exacto.

Esta clase es tambien el unico punto donde se consulta si una estacion o un tramo
estan ACTIVOS, de modo que el reto de resiliencia (cerrar estaciones y recalcular)
se implementa sin tocar ningun algoritmo.
"""

from typing import Iterator, Optional, Tuple

import networkx as nx

from src import config
from src.modelo.pesos import CondicionesRed, detalle_arista, peso_arista

Estado = Tuple[str, Optional[str]]


class EspacioEstados:
    """Genera los sucesores ponderados de un estado (estacion, linea)."""

    def __init__(self, G: nx.MultiDiGraph, condiciones: CondicionesRed):
        self.G = G
        self.cond = condiciones
        # Mapa linea -> modo, para deducir el sistema tarifario del estado.
        self._modo_de_linea = {
            d["linea"]: d["modo"] for _, _, d in G.edges(data=True)
        }

    # -- Consultas basicas -------------------------------------------------- #
    def estado_inicial(self, origen: str) -> Estado:
        return (origen, None)

    def es_meta(self, estado: Estado, destino: str) -> bool:
        return estado[0] == destino

    def sistema_tarifario(self, linea: Optional[str]) -> Optional[str]:
        """Sistema tarifario en el que viene el pasajero, o None si aun no entra."""
        if linea is None:
            return None
        modo = self._modo_de_linea.get(linea)
        return config.SISTEMA_TARIFARIO.get(modo, "ninguno")

    def nodo_activo(self, nodo: str) -> bool:
        return self.G.nodes[nodo].get("activa", True)

    # -- Expansion ---------------------------------------------------------- #
    def sucesores(self, estado: Estado) -> Iterator[Tuple[Estado, float, dict]]:
        """
        Devuelve (estado_sucesor, peso_de_la_transicion, datos_de_la_arista).

        Se omiten las estaciones y tramos desactivados, y los modos que el
        usuario pidio evitar mediante los filtros de la interfaz.
        """
        nodo, linea_previa = estado
        if not self.nodo_activo(nodo):
            return

        sistema_previo = self.sistema_tarifario(linea_previa)

        for _, vecino, datos in self.G.out_edges(nodo, data=True):
            if not datos.get("activa", True):
                continue
            if not self.nodo_activo(vecino):
                continue
            if datos["modo"] in self.cond.evitar_modos:
                continue

            w = peso_arista(datos, self.cond, linea_previa, sistema_previo)
            yield (vecino, datos["linea"]), w, datos

    def detalle(self, estado_origen: Estado, datos: dict) -> dict:
        """Desglose del peso de una transicion, para construir el itinerario."""
        _, linea_previa = estado_origen
        return detalle_arista(
            datos, self.cond, linea_previa, self.sistema_tarifario(linea_previa)
        )

    def es_transbordo(self, estado_origen: Estado, datos: dict) -> bool:
        """
        Indica si tomar esta arista constituye un cambio de linea.

        Un transbordo a pie (O -> PEA -> A) es UN SOLO transbordo, no dos: se
        contabiliza al entrar al tramo peatonal y no se vuelve a contar al
        abordar la siguiente linea. De lo contrario el conteo de Dijkstra
        duplicaria estos transbordos y no coincidiria con la cota que calcula BFS
        sobre el grafo de lineas.
        """
        _, linea_previa = estado_origen
        if linea_previa is None or linea_previa == config.LINEA_PEATONAL:
            return False
        return linea_previa != datos["linea"]
