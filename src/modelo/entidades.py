"""
Entidades del dominio: la estacion (vertice) y la conexion (arista).

Formalmente el sistema se modela como un grafo dirigido y ponderado

        G = (V, E, w)

donde V es el conjunto de estaciones, E el conjunto de tramos dirigidos entre
estaciones y w: E -> R+ la funcion de peso dinamica definida en `pesos.py`.
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class Estacion:
    """Un vertice del grafo: una estacion o parada del SITVA."""

    id: str
    nombre: str
    linea: str
    modo: str
    latitud: float
    longitud: float
    direccion: str
    tipo_estacion: str        # terminal | sencilla | intercambio
    accesibilidad: str        # alta | media | baja
    servicios: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def coordenadas(self) -> Tuple[float, float]:
        return (self.latitud, self.longitud)

    def __str__(self) -> str:
        return f"{self.nombre} ({self.linea})"


@dataclass(frozen=True)
class Conexion:
    """
    Una arista del grafo: un tramo entre dos estaciones.

    `bidireccional` indica que el tramo se recorre en ambos sentidos; al
    construir el grafo dirigido se expande en DOS aristas opuestas. Modelarlo asi
    permite representar despues situaciones reales asimetricas (un cierre que
    afecta un solo sentido, o una pendiente que hace mas lento un sentido).
    """

    origen: str
    destino: str
    linea: str
    modo: str
    tipo: str                 # via | transbordo_peatonal
    tiempo_base_min: float
    distancia_km: float
    capacidad_pasajeros_hora: int
    bidireccional: bool = True

    def __str__(self) -> str:
        return f"{self.origen} -> {self.destino} [{self.linea}]"
