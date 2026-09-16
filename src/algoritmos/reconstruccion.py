"""Reconstruccion del itinerario a partir de los predecesores de la busqueda."""

from typing import Dict, Optional, Tuple

from src.algoritmos.espacio_estados import Estado, EspacioEstados
from src.algoritmos.ruta import Ruta, Tramo


def construir_ruta(
    espacio: EspacioEstados,
    predecesor: Dict[Estado, Tuple[Estado, dict]],
    estado_final: Optional[Estado],
    origen: str,
    destino: str,
    peso_total: float,
    algoritmo: str,
    nodos_expandidos: int,
) -> Ruta:
    """
    Recorre la cadena de predecesores hacia atras y arma la `Ruta`.

    Si `estado_final` es None significa que la busqueda agoto la cola sin llegar
    al destino: no existe camino bajo las condiciones actuales.
    """
    base = dict(
        origen=origen,
        destino=destino,
        algoritmo=algoritmo,
        criterio=espacio.cond.criterio,
        perfil_horario=espacio.cond.perfil_horario,
        nodos_expandidos=nodos_expandidos,
    )

    if estado_final is None:
        return Ruta(
            existe=False,
            motivo="No existe camino entre las estaciones bajo las condiciones actuales",
            **base,
        )

    G = espacio.G
    tramos = []
    actual = estado_final

    while actual in predecesor:
        anterior, datos = predecesor[actual]
        det = espacio.detalle(anterior, datos)
        tramos.append(
            Tramo(
                origen=anterior[0],
                destino=actual[0],
                nombre_origen=G.nodes[anterior[0]]["nombre"],
                nombre_destino=G.nodes[actual[0]]["nombre"],
                linea=datos["linea"],
                modo=datos["modo"],
                minutos=det["minutos"],
                costo_cop=det["costo_cop"],
                riesgo=det["riesgo"],
                es_transbordo=espacio.es_transbordo(anterior, datos),
                penalizacion_transbordo_min=det["penalizacion_transbordo_min"],
                peso=det["peso"],
            )
        )
        actual = anterior

    tramos.reverse()
    return Ruta(tramos=tramos, peso_total=peso_total, **base)
