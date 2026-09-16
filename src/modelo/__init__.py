"""Modelado del problema: estaciones, conexiones, grafo y funcion de peso."""

from src.modelo.entidades import Conexion, Estacion
from src.modelo.carga_datos import cargar_conexiones, cargar_estaciones
from src.modelo.grafo import construir_grafo, resumen_grafo
from src.modelo.pesos import CondicionesRed, peso_arista

__all__ = [
    "Estacion",
    "Conexion",
    "cargar_estaciones",
    "cargar_conexiones",
    "construir_grafo",
    "resumen_grafo",
    "CondicionesRed",
    "peso_arista",
]
