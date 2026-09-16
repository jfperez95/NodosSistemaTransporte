"""
Paso 1 - Generacion del archivo de conexiones de la red SITVA.

Este script NO se ejecuta en tiempo de aplicacion: es la herramienta que produjo
`datos/conexiones.csv` a partir de (a) la topologia declarada aqui y (b) las
coordenadas de `datos/estaciones.csv`.

Se mantiene en el repositorio para que el dataset sea *reproducible* y auditable:
las distancias no se digitaron a mano, se calculan con la formula de Haversine, y
los tiempos base se derivan de la velocidad comercial de cada modo de transporte.

Uso:  python scripts/00_generar_conexiones.py
"""

import csv
import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

RUTA_ESTACIONES = RAIZ / "datos" / "estaciones.csv"
RUTA_SALIDA = RAIZ / "datos" / "conexiones.csv"

# Velocidad comercial (km/h) y tiempo de parada (min) por modo de transporte.
# Valores tomados como parametros verosimiles del SITVA para la simulacion.
PARAMETROS_MODO = {
    "metro": {"velocidad_kmh": 35.0, "parada_min": 0.4, "capacidad_hora": 35000},
    "tranvia": {"velocidad_kmh": 18.0, "parada_min": 0.4, "capacidad_hora": 3500},
    "cable": {"velocidad_kmh": 18.0, "parada_min": 0.0, "capacidad_hora": 3000},
    "bus": {"velocidad_kmh": 22.0, "parada_min": 0.5, "capacidad_hora": 2800},
    "peatonal": {"velocidad_kmh": 4.5, "parada_min": 0.0, "capacidad_hora": 99999},
}

# Secuencia de estaciones de cada linea. Las estaciones de intercambio aparecen
# en varias lineas porque son UN SOLO nodo del grafo que sirve a varias lineas.
LINEAS = {
    "A": ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
          "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18", "A19", "A20", "A21"],
    "B": ["A11", "B01", "B02", "B03", "B04", "B05", "B06"],
    "K": ["A04", "K01", "K02", "K03"],
    "L": ["K03", "L01"],
    "J": ["B06", "J01", "J02", "J03"],
    "P": ["A04", "P01", "P02", "P03"],
    "T": ["A11", "T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08"],
    "M": ["T05", "M01", "M02"],
    "H": ["T08", "H01", "H02"],
    "O": ["O01", "O02", "O03", "O04", "O05", "O06", "O07", "O08",
          "O09", "O10", "O11", "O12"],
}

# Transbordos a pie entre estaciones cercanas de sistemas distintos.
# (origen, destino, minutos_caminando)
TRANSBORDOS_PEATONALES = [
    ("O08", "A12", 4.0),   # Plaza Mayor  <-> Alpujarra
    ("O09", "A09", 5.0),   # Parque Bolivar <-> Prado
    ("O07", "A14", 5.0),   # Perpetuo Socorro <-> Industriales
]

# Distancia maxima admitida para un transbordo a pie (ver validaciones).
DISTANCIA_MAX_PEATONAL_KM = 0.8

RADIO_TIERRA_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia ortodromica en kilometros entre dos puntos geograficos."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def cargar_estaciones():
    with RUTA_ESTACIONES.open(encoding="utf-8") as f:
        return {fila["id"]: fila for fila in csv.DictReader(f)}


def construir_filas(estaciones):
    filas = []
    vistos = set()

    for linea, secuencia in LINEAS.items():
        for origen, destino in zip(secuencia, secuencia[1:]):
            clave = (origen, destino, linea)
            if clave in vistos:
                continue
            vistos.add(clave)

            eo, ed = estaciones[origen], estaciones[destino]
            modo = ed["modo"] if ed["linea"] == linea else eo["modo"]
            par = PARAMETROS_MODO[modo]

            km = haversine_km(float(eo["latitud"]), float(eo["longitud"]),
                              float(ed["latitud"]), float(ed["longitud"]))
            # Factor 1.15: la via real no es una linea recta entre estaciones.
            km_via = km * 1.15
            minutos = km_via / par["velocidad_kmh"] * 60 + par["parada_min"]

            filas.append({
                "origen": origen,
                "destino": destino,
                "linea": linea,
                "modo": modo,
                "tipo": "via",
                "tiempo_base_min": round(minutos, 2),
                "distancia_km": round(km_via, 3),
                "capacidad_pasajeros_hora": par["capacidad_hora"],
                "bidireccional": 1,
            })

    for origen, destino, minutos in TRANSBORDOS_PEATONALES:
        eo, ed = estaciones[origen], estaciones[destino]
        km = haversine_km(float(eo["latitud"]), float(eo["longitud"]),
                          float(ed["latitud"]), float(ed["longitud"]))
        filas.append({
            "origen": origen,
            "destino": destino,
            "linea": "PEA",
            "modo": "peatonal",
            "tipo": "transbordo_peatonal",
            "tiempo_base_min": round(minutos, 2),
            "distancia_km": round(km * 1.3, 3),
            "capacidad_pasajeros_hora": PARAMETROS_MODO["peatonal"]["capacidad_hora"],
            "bidireccional": 1,
        })

    return filas


def main():
    estaciones = cargar_estaciones()
    filas = construir_filas(estaciones)
    campos = ["origen", "destino", "linea", "modo", "tipo", "tiempo_base_min",
              "distancia_km", "capacidad_pasajeros_hora", "bidireccional"]

    with RUTA_SALIDA.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"Generadas {len(filas)} conexiones en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
