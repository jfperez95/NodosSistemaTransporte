"""Lectura y validacion de los archivos CSV que describen la red."""

import csv
from pathlib import Path
from typing import Dict, List

from src import config
from src.modelo.entidades import Conexion, Estacion
from src.utils.geo import haversine_km


class ErrorDatosRed(ValueError):
    """Se levanta cuando el dataset de la red no es consistente."""


def _a_float(valor: str, campo: str, fila: int) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise ErrorDatosRed(f"Fila {fila}: '{campo}' no es numerico: {valor!r}")


def cargar_estaciones(ruta: Path = None) -> Dict[str, Estacion]:
    """Lee `estaciones.csv` y devuelve {id_estacion: Estacion}."""
    ruta = Path(ruta or config.RUTA_ESTACIONES)
    if not ruta.exists():
        raise ErrorDatosRed(f"No se encontro el archivo de estaciones: {ruta}")

    estaciones: Dict[str, Estacion] = {}
    with ruta.open(encoding="utf-8") as f:
        for n, fila in enumerate(csv.DictReader(f), start=2):
            id_est = fila["id"].strip()
            if not id_est:
                raise ErrorDatosRed(f"Fila {n}: la estacion no tiene id")
            if id_est in estaciones:
                raise ErrorDatosRed(f"Fila {n}: id de estacion duplicado: {id_est}")

            modo = fila["modo"].strip()
            if modo not in config.MODOS:
                raise ErrorDatosRed(f"Fila {n}: modo desconocido {modo!r}")

            estaciones[id_est] = Estacion(
                id=id_est,
                nombre=fila["nombre"].strip(),
                linea=fila["linea"].strip(),
                modo=modo,
                latitud=_a_float(fila["latitud"], "latitud", n),
                longitud=_a_float(fila["longitud"], "longitud", n),
                direccion=fila["direccion"].strip(),
                tipo_estacion=fila["tipo_estacion"].strip(),
                accesibilidad=fila["accesibilidad"].strip(),
                servicios=tuple(
                    s for s in fila.get("servicios", "").split(";") if s.strip()
                ),
            )

    if not estaciones:
        raise ErrorDatosRed("El archivo de estaciones esta vacio")
    return estaciones


def cargar_conexiones(
    estaciones: Dict[str, Estacion], ruta: Path = None
) -> List[Conexion]:
    """Lee `conexiones.csv` validandolo contra el diccionario de estaciones."""
    ruta = Path(ruta or config.RUTA_CONEXIONES)
    if not ruta.exists():
        raise ErrorDatosRed(f"No se encontro el archivo de conexiones: {ruta}")

    conexiones: List[Conexion] = []
    vistas = set()

    with ruta.open(encoding="utf-8") as f:
        for n, fila in enumerate(csv.DictReader(f), start=2):
            origen, destino = fila["origen"].strip(), fila["destino"].strip()

            for extremo in (origen, destino):
                if extremo not in estaciones:
                    raise ErrorDatosRed(
                        f"Fila {n}: la estacion {extremo!r} no existe en estaciones.csv"
                    )
            if origen == destino:
                raise ErrorDatosRed(f"Fila {n}: bucle no permitido en {origen}")

            linea = fila["linea"].strip()
            clave = (origen, destino, linea)
            if clave in vistas:
                raise ErrorDatosRed(f"Fila {n}: conexion duplicada {clave}")
            vistas.add(clave)

            tiempo = _a_float(fila["tiempo_base_min"], "tiempo_base_min", n)
            if tiempo < config.TIEMPO_MIN_TRAMO:
                raise ErrorDatosRed(
                    f"Fila {n}: tiempo_base_min debe ser >= "
                    f"{config.TIEMPO_MIN_TRAMO} (Dijkstra exige pesos positivos)"
                )

            distancia = _a_float(fila["distancia_km"], "distancia_km", n)
            if distancia <= 0:
                raise ErrorDatosRed(f"Fila {n}: distancia_km debe ser positiva")

            tipo = fila["tipo"].strip()
            if tipo == "transbordo_peatonal":
                eo, ed = estaciones[origen], estaciones[destino]
                recta = haversine_km(eo.latitud, eo.longitud, ed.latitud, ed.longitud)
                if recta > config.DISTANCIA_MAX_PEATONAL_KM:
                    raise ErrorDatosRed(
                        f"Fila {n}: transbordo a pie {origen}-{destino} de "
                        f"{recta:.2f} km supera el maximo de "
                        f"{config.DISTANCIA_MAX_PEATONAL_KM} km"
                    )

            conexiones.append(
                Conexion(
                    origen=origen,
                    destino=destino,
                    linea=linea,
                    modo=fila["modo"].strip(),
                    tipo=tipo,
                    tiempo_base_min=tiempo,
                    distancia_km=distancia,
                    capacidad_pasajeros_hora=int(
                        _a_float(fila["capacidad_pasajeros_hora"],
                                 "capacidad_pasajeros_hora", n)
                    ),
                    bidireccional=fila["bidireccional"].strip() in ("1", "True", "true"),
                )
            )

    if not conexiones:
        raise ErrorDatosRed("El archivo de conexiones esta vacio")
    return conexiones
