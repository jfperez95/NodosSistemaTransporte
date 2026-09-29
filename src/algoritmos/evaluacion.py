"""
Reevaluacion exacta de una ruta construida por partes.

Cuando Yen concatena la raiz de una ruta con un desvio calculado por separado, el
primer tramo del desvio quedo evaluado como si el pasajero acabara de entrar al
sistema. Esta funcion recorre el itinerario completo y recalcula minutos, costo,
riesgo, transbordos y peso con la linea previa correcta.
"""

from typing import Optional

import networkx as nx

from src.algoritmos.espacio_estados import EspacioEstados
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed


def _datos_arista(G: nx.MultiDiGraph, origen: str, destino: str, linea: str) -> Optional[dict]:
    try:
        return G[origen][destino][linea]
    except KeyError:
        return None


def evaluar_ruta(G: nx.MultiDiGraph, ruta: Ruta, condiciones: CondicionesRed) -> Ruta:
    """
    Recalcula en el sitio las metricas de `ruta` y actualiza su `peso_total`.

    Devuelve la misma instancia para poder encadenar llamadas.
    """
    if not ruta.existe or not ruta.tramos:
        return ruta

    espacio = EspacioEstados(G, condiciones)
    linea_previa = None
    total = 0.0

    for tramo in ruta.tramos:
        datos = _datos_arista(G, tramo.origen, tramo.destino, tramo.linea)
        if datos is None:
            ruta.existe = False
            ruta.motivo = (
                f"El tramo {tramo.origen}->{tramo.destino} por la linea "
                f"{tramo.linea} ya no existe en el grafo"
            )
            return ruta

        estado_previo = (tramo.origen, linea_previa)
        det = espacio.detalle(estado_previo, datos)

        tramo.minutos = det["minutos"]
        tramo.costo_cop = det["costo_cop"]
        tramo.riesgo = det["riesgo"]
        tramo.penalizacion_transbordo_min = det["penalizacion_transbordo_min"]
        tramo.es_transbordo = espacio.es_transbordo(estado_previo, datos)
        tramo.peso = det["peso"]

        total += det["peso"]
        linea_previa = tramo.linea

    ruta.peso_total = total
    return ruta
