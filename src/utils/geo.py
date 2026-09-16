"""
Calculos geograficos sobre las coordenadas de las estaciones.

La funcion `haversine_km` es la base de la heuristica admisible que usa el
algoritmo A* (ver `src/algoritmos/a_estrella.py`): la distancia en linea recta
entre dos estaciones nunca sobreestima la distancia real por la via, por lo que
el coste estimado derivado de ella tampoco sobreestima el coste real.
"""

from math import asin, cos, radians, sin, sqrt

RADIO_TIERRA_KM = 6371.0088

# Velocidad maxima de cualquier modo del sistema (km/h). Se usa para convertir
# una distancia en una COTA INFERIOR de tiempo, requisito de admisibilidad de A*.
VELOCIDAD_MAXIMA_KMH = 40.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distancia ortodromica (en km) entre dos puntos dados en grados decimales.

    >>> round(haversine_km(6.2472, -75.5697, 6.2472, -75.5697), 6)
    0.0
    """
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def cota_inferior_minutos(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Cota inferior del tiempo de viaje (minutos) entre dos puntos.

    Se obtiene suponiendo el mejor caso posible: recorrer la distancia en linea
    recta a la velocidad maxima del sistema. Ningun recorrido real puede ser mas
    rapido, de modo que h(n) <= h*(n) y la heuristica es admisible.
    """
    km = haversine_km(lat1, lon1, lat2, lon2)
    return km / VELOCIDAD_MAXIMA_KMH * 60.0
