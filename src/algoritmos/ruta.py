"""
Resultado de una busqueda: la ruta y sus tramos.

Los cuatro algoritmos devuelven este mismo tipo de objeto, de modo que la
interfaz y las pruebas no dependen de cual se uso.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import networkx as nx


@dataclass
class Tramo:
    """Un segmento del viaje: una arista recorrida del grafo."""

    origen: str
    destino: str
    nombre_origen: str
    nombre_destino: str
    linea: str
    modo: str
    minutos: float
    costo_cop: int
    riesgo: float
    es_transbordo: bool = False
    penalizacion_transbordo_min: float = 0.0
    peso: float = 0.0          # aporte de este tramo a w(ruta), segun el criterio

    def __str__(self) -> str:
        marca = " [transbordo]" if self.es_transbordo else ""
        return (
            f"{self.nombre_origen} -> {self.nombre_destino} "
            f"({self.linea}/{self.modo}, {self.minutos:.1f} min){marca}"
        )


@dataclass
class Ruta:
    """
    Camino minimo encontrado, con sus metricas agregadas.

    `existe = False` representa el caso en que no hay camino entre origen y
    destino bajo las condiciones actuales (por ejemplo, con estaciones cerradas).
    """

    origen: str
    destino: str
    tramos: List[Tramo] = field(default_factory=list)
    peso_total: float = 0.0
    algoritmo: str = ""
    criterio: str = ""
    perfil_horario: str = ""
    nodos_expandidos: int = 0
    existe: bool = True
    motivo: Optional[str] = None

    # -- Metricas derivadas ------------------------------------------------- #
    @property
    def estaciones(self) -> List[str]:
        if not self.tramos:
            return [self.origen] if self.existe else []
        return [self.tramos[0].origen] + [t.destino for t in self.tramos]

    @property
    def minutos_totales(self) -> float:
        return round(
            sum(t.minutos + t.penalizacion_transbordo_min for t in self.tramos), 2
        )

    @property
    def costo_total_cop(self) -> int:
        return sum(t.costo_cop for t in self.tramos)

    @property
    def num_transbordos(self) -> int:
        return sum(1 for t in self.tramos if t.es_transbordo)

    @property
    def num_estaciones(self) -> int:
        return len(self.estaciones)

    @property
    def lineas_usadas(self) -> List[str]:
        vistas, orden = set(), []
        for t in self.tramos:
            if t.linea not in vistas:
                vistas.add(t.linea)
                orden.append(t.linea)
        return orden

    @property
    def riesgo_maximo(self) -> float:
        return round(max((t.riesgo for t in self.tramos), default=0.0), 3)

    def resumen(self) -> dict:
        return {
            "existe": self.existe,
            "algoritmo": self.algoritmo,
            "criterio": self.criterio,
            "perfil_horario": self.perfil_horario,
            "minutos": self.minutos_totales,
            "costo_cop": self.costo_total_cop,
            "transbordos": self.num_transbordos,
            "estaciones": self.num_estaciones,
            "lineas": self.lineas_usadas,
            "riesgo_maximo": self.riesgo_maximo,
            "peso_total": round(self.peso_total, 4),
            "nodos_expandidos": self.nodos_expandidos,
        }

    def imprimir(self, G: nx.MultiDiGraph = None) -> str:
        """Representacion legible del itinerario, tramo por tramo."""
        if not self.existe:
            return f"Sin ruta entre {self.origen} y {self.destino}: {self.motivo}"

        lineas = [
            f"Ruta {self.origen} -> {self.destino}  [{self.algoritmo} / {self.criterio}]",
            f"  {self.minutos_totales:.1f} min | ${self.costo_total_cop:,} COP | "
            f"{self.num_transbordos} transbordo(s) | {self.num_estaciones} estaciones",
            f"  Lineas: {' > '.join(self.lineas_usadas)}",
            "",
        ]
        for i, t in enumerate(self.tramos, 1):
            lineas.append(f"  {i:2d}. {t}")
        return "\n".join(lineas)
