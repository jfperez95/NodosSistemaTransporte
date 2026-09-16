"""
Funcion de peso dinamica y multicriterio.

Este modulo es lo que convierte el grafo estatico en un GRAFO DINAMICO: el peso
de una arista no es un numero fijo del dataset, sino el resultado de evaluar

    w(e) = alfa * tiempo(e, hora)
         + beta * costo(e, sistema_previo) / COSTO_POR_UNIDAD_PESO
         + gamma * transbordo(linea_previa, linea(e))
         + delta * riesgo(e, hora)

donde (alfa, beta, gamma, delta) los fija el CRITERIO elegido por el usuario
(mas rapida, mas economica, menos transbordos, mas confiable) y la hora fija el
PERFIL HORARIO que multiplica tiempos y ocupacion.

Propiedad clave: **w(e) > 0 siempre**. Todos los terminos son no negativos y el
termino de tiempo tiene una cota inferior estrictamente positiva. Esa es
exactamente la condicion que exige el algoritmo de Dijkstra, y es la razon por la
que se eligio Dijkstra y no Bellman-Ford (ver documento tecnico).
"""

from dataclasses import dataclass
from typing import Optional

from src import config


@dataclass(frozen=True)
class CondicionesRed:
    """
    Estado dinamico de la red en el momento de calcular la ruta.

    Es el "instante" en que se congela el grafo dinamico para poder aplicarle un
    algoritmo de camino minimo: mientras dura un calculo los pesos son fijos,
    pero entre un calculo y otro cambian con la hora, el clima o los incidentes.
    """

    perfil_horario: str = config.PERFIL_POR_DEFECTO
    criterio: str = config.CRITERIO_POR_DEFECTO
    factor_clima: float = 1.0        # 1.0 despejado; >1 lluvia, incidentes
    evitar_modos: frozenset = frozenset()

    def __post_init__(self):
        if self.perfil_horario not in config.PERFILES_HORARIOS:
            raise ValueError(
                f"Perfil horario desconocido: {self.perfil_horario!r}. "
                f"Opciones: {sorted(config.PERFILES_HORARIOS)}"
            )
        if self.criterio not in config.CRITERIOS:
            raise ValueError(
                f"Criterio desconocido: {self.criterio!r}. "
                f"Opciones: {sorted(config.CRITERIOS)}"
            )
        if self.factor_clima <= 0:
            raise ValueError("factor_clima debe ser positivo")

    @property
    def perfil(self) -> dict:
        return config.PERFILES_HORARIOS[self.perfil_horario]

    @property
    def coeficientes(self) -> dict:
        return config.CRITERIOS[self.criterio]


# --------------------------------------------------------------------------- #
# Componentes del peso
# --------------------------------------------------------------------------- #
def tiempo_arista(datos: dict, cond: CondicionesRed) -> float:
    """
    Tiempo de viaje real (minutos) del tramo bajo las condiciones dadas.

    tiempo = tiempo_base * factor_hora * factor_clima * (1 + s_modo * ocupacion)

    El ultimo factor modela la congestion: a igual ocupacion, un bus se degrada
    mucho mas que el metro, porque comparte via con el trafico general.
    """
    if datos["modo"] == "peatonal":
        return max(datos["tiempo_base_min"], config.TIEMPO_MIN_TRAMO)

    perfil = cond.perfil
    sensibilidad = config.SENSIBILIDAD_CONGESTION.get(datos["modo"], 0.2)
    factor_congestion = 1.0 + sensibilidad * perfil["ocupacion"]

    minutos = (
        datos["tiempo_base_min"]
        * perfil["factor_tiempo"]
        * cond.factor_clima
        * factor_congestion
    )
    return max(minutos, config.TIEMPO_MIN_TRAMO)


def costo_arista(datos: dict, sistema_previo: Optional[str]) -> int:
    """
    Costo monetario (COP) de tomar este tramo, dado el sistema tarifario en que
    venia el pasajero.

    Refleja la integracion tarifaria del SITVA: se paga al entrar al sistema y
    los transbordos dentro del mismo sistema son gratuitos; pasar de riel a bus
    (o al reves) cobra solo un recargo, no la tarifa completa.

    `sistema_previo = None` significa que el pasajero apenas esta entrando.
    """
    sistema = config.SISTEMA_TARIFARIO[datos["modo"]]
    if sistema == "ninguno":
        return 0

    extra = config.RECARGO_LINEA_COP.get(datos["linea"], 0)

    if sistema_previo is None or sistema_previo == "ninguno":
        return config.TARIFA_ENTRADA_COP[sistema] + extra
    if sistema_previo == sistema:
        return extra
    return config.RECARGO_TRANSBORDO_COP.get((sistema_previo, sistema),
                                             config.TARIFA_ENTRADA_COP[sistema]) + extra


def penalizacion_transbordo(
    datos: dict, linea_previa: Optional[str], cond: CondicionesRed
) -> float:
    """
    Minutos perdidos por cambiar de linea al tomar este tramo.

    Es 0 si el pasajero sigue en la misma linea o si apenas inicia el viaje.
    En hora pico la espera del siguiente vehiculo es mayor, asi que la
    penalizacion se escala con el factor horario.
    """
    if linea_previa is None or linea_previa == datos["linea"]:
        return 0.0
    if datos["tipo"] == "transbordo_peatonal":
        return 0.0     # el tiempo de caminata ya esta en el propio tramo

    base = config.PENALIZACION_TRANSBORDO_MIN.get(datos["modo"], 4.0)
    return base * cond.perfil["factor_tiempo"]


def riesgo_arista(datos: dict, cond: CondicionesRed) -> float:
    """
    Riesgo de retraso del tramo, en [0, 1].

    Combina la probabilidad de retraso del perfil horario con la fragilidad del
    modo (un cable con baja capacidad se satura antes que el metro).
    """
    if datos["modo"] == "peatonal":
        return 0.0
    prob = cond.perfil["prob_retraso"] * cond.factor_clima
    fragilidad = config.SENSIBILIDAD_CONGESTION.get(datos["modo"], 0.2)
    return min(prob * (1.0 + fragilidad), 1.0)


# --------------------------------------------------------------------------- #
# Peso total
# --------------------------------------------------------------------------- #
def peso_arista(
    datos: dict,
    cond: CondicionesRed,
    linea_previa: Optional[str] = None,
    sistema_previo: Optional[str] = None,
) -> float:
    """
    Peso w(e) > 0 de la arista, segun el criterio y las condiciones actuales.

    `linea_previa` y `sistema_previo` describen COMO llego el pasajero al nodo de
    origen del tramo. Por eso los algoritmos de este proyecto no recorren nodos
    sino ESTADOS (nodo, linea): el peso de una arista depende del camino por el
    que se llega, y un Dijkstra ingenuo sobre nodos no podria contar transbordos
    correctamente.
    """
    c = cond.coeficientes

    minutos = tiempo_arista(datos, cond)
    transbordo_min = penalizacion_transbordo(datos, linea_previa, cond)
    pesos_cop = costo_arista(datos, sistema_previo)
    riesgo = riesgo_arista(datos, cond)

    w = (
        c["alfa_tiempo"] * minutos
        + c["beta_costo"] * (pesos_cop / config.COSTO_POR_UNIDAD_PESO)
        + c["gamma_transbordo"] * transbordo_min
        + c["delta_riesgo"] * riesgo
    )

    # Garantia de positividad estricta exigida por Dijkstra.
    return max(w, 1e-9)


def detalle_arista(
    datos: dict,
    cond: CondicionesRed,
    linea_previa: Optional[str] = None,
    sistema_previo: Optional[str] = None,
) -> dict:
    """Desglose de los componentes del peso, para mostrarlo en la interfaz."""
    return {
        "minutos": round(tiempo_arista(datos, cond), 2),
        "penalizacion_transbordo_min": round(
            penalizacion_transbordo(datos, linea_previa, cond), 2
        ),
        "costo_cop": costo_arista(datos, sistema_previo),
        "riesgo": round(riesgo_arista(datos, cond), 3),
        "peso": round(peso_arista(datos, cond, linea_previa, sistema_previo), 4),
    }
