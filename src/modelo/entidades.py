"""Entidades del dominio: la estacion (vertice) y la conexion (arista)."""

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

    Un tramo `bidireccional` se expande en dos aristas dirigidas opuestas al
    construir el grafo.
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
