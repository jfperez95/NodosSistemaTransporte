"""
Retos avanzados: analisis de la red mas alla del calculo de una ruta.

  * `resiliencia`  - puntos criticos, eventos disruptivos y recalculo de rutas.
  * `prediccion`   - tiempos de viaje con intervalos de confianza.
  * `optimizacion` - brechas de la red y simulacion de nuevas conexiones.
"""

from src.analisis.resiliencia import (
    centralidad_intermediacion,
    impacto_de_cierre,
    puntos_criticos,
    red_con_evento,
    responder_a_evento,
)
from src.analisis.prediccion import (
    ajustar_modelo,
    generar_historico,
    predecir_ruta,
)
from src.analisis.optimizacion import (
    detectar_brechas,
    evaluar_propuesta,
    proponer_conexiones,
)

__all__ = [
    "centralidad_intermediacion",
    "puntos_criticos",
    "red_con_evento",
    "impacto_de_cierre",
    "responder_a_evento",
    "generar_historico",
    "ajustar_modelo",
    "predecir_ruta",
    "detectar_brechas",
    "proponer_conexiones",
    "evaluar_propuesta",
]
