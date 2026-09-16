"""
Parametros de la simulacion: tarifas, perfiles horarios, pesos por criterio y
presentacion visual de cada modo de transporte.

Centralizar estos valores permite ajustar el comportamiento del modelo sin tocar
la logica del grafo ni la de los algoritmos.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Rutas del proyecto
# --------------------------------------------------------------------------- #
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ_PROYECTO / "datos"
RUTA_ESTACIONES = DIR_DATOS / "estaciones.csv"
RUTA_CONEXIONES = DIR_DATOS / "conexiones.csv"

# --------------------------------------------------------------------------- #
# Modos de transporte
# --------------------------------------------------------------------------- #
MODOS = ("metro", "tranvia", "cable", "bus", "peatonal")

# Identificador reservado de la "linea" que representa los recorridos a pie entre
# estaciones cercanas. No es un servicio: es el pegamento entre dos servicios.
LINEA_PEATONAL = "PEA"

# Color por modo, para la visualizacion georreferenciada (paso 5).
#
# Paleta CATEGORICA: el color identifica el modo de transporte, no una magnitud,
# asi que los tonos se asignan en orden fijo y nunca se reciclan. Se valido con el
# comprobador de contraste y daltonismo sobre superficie clara:
#   - franja de luminosidad y piso de croma: OK
#   - separacion para vision normal: peor par 21.4 (minimo exigido 15)
#   - separacion bajo deuteranopia: peor par (cable/tranvia) 6.9, en el suelo
#     admisible, lo que OBLIGA a una codificacion secundaria -> ESTILO_MODO.
# Por eso la aplicacion fija tema claro: una paleta oscura sin validar seria peor
# que no ofrecer modo oscuro.
COLOR_MODO = {
    "metro": "#0B5FA5",
    "tranvia": "#009A44",
    "cable": "#E4572E",
    "bus": "#A3005C",
    "peatonal": "#6B7280",   # neutral: no es un modo de servicio, es caminar
}

# Codificacion secundaria obligatoria: patron de trazo por modo, para que el modo
# siga siendo legible sin depender del color (daltonismo, impresion en blanco y
# negro, proyector de mala calidad en la sustentacion).
ESTILO_MODO = {
    "metro": None,            # linea continua
    "tranvia": "10, 4",
    "cable": "2, 6",
    "bus": "14, 4, 2, 4",
    "peatonal": "1, 6",
}

NOMBRE_MODO = {
    "metro": "Metro",
    "tranvia": "Tranvia",
    "cable": "Metrocable",
    "bus": "Bus electrico / Metroplus",
    "peatonal": "Recorrido a pie",
}

# --------------------------------------------------------------------------- #
# Sistema tarifario (pesos colombianos, valores de simulacion 2026)
# --------------------------------------------------------------------------- #
# Los modos que comparten "sistema tarifario" no cobran de nuevo al transbordar:
# el usuario paga una vez al entrar y los transbordos integrados son gratuitos.
SISTEMA_TARIFARIO = {
    "metro": "riel",
    "tranvia": "riel",
    "cable": "riel",
    "bus": "buses",
    "peatonal": "ninguno",
}

# Tarifa que se cobra al ENTRAR por primera vez a cada sistema tarifario.
TARIFA_ENTRADA_COP = {
    "riel": 3300,
    "buses": 3000,
    "ninguno": 0,
}

# Recargo al pasar de un sistema tarifario a otro dentro del mismo viaje
# (integracion SITVA: el transbordo riel <-> bus no cuesta la tarifa completa).
RECARGO_TRANSBORDO_COP = {
    ("riel", "buses"): 500,
    ("buses", "riel"): 500,
}

# Lineas con tarifa especial que se cobra aparte (Linea L, turistica a Arvi).
RECARGO_LINEA_COP = {"L": 12000}

# --------------------------------------------------------------------------- #
# Dinamica temporal: perfiles horarios
# --------------------------------------------------------------------------- #
# Multiplicador que se aplica al tiempo base y nivel de ocupacion esperado.
# Es el componente que convierte el grafo estatico en un GRAFO DINAMICO.
PERFILES_HORARIOS = {
    "pico_manana": {
        "etiqueta": "Pico manana (05:00-08:30)",
        "factor_tiempo": 1.35,
        "ocupacion": 0.92,
        "prob_retraso": 0.25,
    },
    "valle_manana": {
        "etiqueta": "Valle manana (08:30-11:30)",
        "factor_tiempo": 1.00,
        "ocupacion": 0.45,
        "prob_retraso": 0.08,
    },
    "medio_dia": {
        "etiqueta": "Medio dia (11:30-16:00)",
        "factor_tiempo": 1.10,
        "ocupacion": 0.60,
        "prob_retraso": 0.12,
    },
    "pico_tarde": {
        "etiqueta": "Pico tarde (16:00-19:30)",
        "factor_tiempo": 1.40,
        "ocupacion": 0.95,
        "prob_retraso": 0.30,
    },
    "noche": {
        "etiqueta": "Noche (19:30-23:00)",
        "factor_tiempo": 0.95,
        "ocupacion": 0.30,
        "prob_retraso": 0.05,
    },
    "fin_de_semana": {
        "etiqueta": "Fin de semana",
        "factor_tiempo": 0.90,
        "ocupacion": 0.50,
        "prob_retraso": 0.10,
    },
}

PERFIL_POR_DEFECTO = "valle_manana"

# Sensibilidad de cada modo a la congestion: cuanto se degrada su tiempo cuando
# la ocupacion es alta. El metro es el mas robusto; el bus, el mas sensible.
SENSIBILIDAD_CONGESTION = {
    "metro": 0.15,
    "tranvia": 0.20,
    "cable": 0.35,
    "bus": 0.45,
    "peatonal": 0.0,
}

# --------------------------------------------------------------------------- #
# Criterios de optimizacion
# --------------------------------------------------------------------------- #
# Cada criterio define los coeficientes (alfa, beta, gamma, delta) de la funcion
# de peso w = alfa*tiempo + beta*costo_normalizado + gamma*transbordo + delta*riesgo
CRITERIOS = {
    "tiempo": {
        "etiqueta": "Ruta mas rapida",
        "alfa_tiempo": 1.0,
        "beta_costo": 0.0,
        "gamma_transbordo": 1.0,     # el transbordo si cuesta tiempo real
        "delta_riesgo": 0.0,
    },
    "costo": {
        "etiqueta": "Ruta mas economica",
        "alfa_tiempo": 0.05,         # desempata entre rutas del mismo precio
        "beta_costo": 1.0,
        "gamma_transbordo": 0.05,
        "delta_riesgo": 0.0,
    },
    "transbordos": {
        "etiqueta": "Menos transbordos",
        "alfa_tiempo": 0.05,
        "beta_costo": 0.0,
        "gamma_transbordo": 100.0,   # penalizacion dominante
        "delta_riesgo": 0.0,
    },
    "confiable": {
        "etiqueta": "Ruta mas confiable",
        "alfa_tiempo": 0.6,
        "beta_costo": 0.0,
        "gamma_transbordo": 1.5,
        "delta_riesgo": 40.0,        # penaliza tramos con alta prob. de retraso
    },
}

CRITERIO_POR_DEFECTO = "tiempo"

# Penalizacion de tiempo (minutos) por cambiar de linea dentro de una estacion.
# Incluye caminar entre andenes y la espera del siguiente vehiculo.
PENALIZACION_TRANSBORDO_MIN = {
    "metro": 4.0,
    "tranvia": 5.0,
    "cable": 3.0,
    "bus": 6.0,
    "peatonal": 0.0,
}

# Factor para llevar pesos en COP a una escala comparable con los minutos.
# 1 unidad de peso == COSTO_POR_UNIDAD_PESO pesos colombianos.
COSTO_POR_UNIDAD_PESO = 300.0

# --------------------------------------------------------------------------- #
# Validaciones del dataset
# --------------------------------------------------------------------------- #
DISTANCIA_MAX_PEATONAL_KM = 0.8   # linea recta entre estaciones de un transbordo a pie
TIEMPO_MIN_TRAMO = 0.1            # minutos; evita aristas de peso cero
