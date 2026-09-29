"""
Prediccion de tiempos de viaje con intervalos de confianza.

Sobre un historico sintetico reproducible se ajusta un modelo multiplicativo en
escala logaritmica por backfitting. El modelo no recibe los factores con que se
simularon los datos: los estima.

La incertidumbre tiene dos componentes. La idiosincratica es propia de cada tramo
y se diluye al sumar; la sistemica la comparten todos los tramos de una misma
jornada y no se diluye. La varianza de la ruta es

    Var(T) = SUMA_i (t_i * sigma_modo_i)^2 + (sigma_sistemica * T)^2
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from src import config
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed, tiempo_arista

# Factores "reales" con los que se simula el historico. El modelo NO los recibe:
# debe recuperarlos a partir de los datos.
FACTOR_DIA = {
    "lunes": 1.06, "martes": 1.02, "miercoles": 1.03,
    "jueves": 1.05, "viernes": 1.12, "sabado": 0.92, "domingo": 0.85,
}
FACTOR_CLIMA = {"despejado": 1.00, "lluvia_ligera": 1.08, "lluvia_intensa": 1.28}
FACTOR_EVENTO = {"ninguno": 1.00, "partido": 1.18, "feria": 1.10, "marcha": 1.35}

# Dispersion del ruido lognormal por modo: el bus es el mas impredecible porque
# comparte via con el trafico; el metro corre en via segregada.
SIGMA_MODO = {
    "metro": 0.06, "tranvia": 0.09, "cable": 0.08, "bus": 0.18, "peatonal": 0.04,
}

# Dispersion del factor compartido por jornada: cuanto varia el sistema COMPLETO
# de un dia a otro, por encima de los efectos de dia de semana, clima y eventos.
SIGMA_SISTEMICA = 0.10

# Numero de jornadas distintas que se simulan en el historico.
JORNADAS = 240

SEMILLA_POR_DEFECTO = 20260930


@dataclass
class ModeloTiempos:
    """Parametros estimados a partir del historico sintetico."""

    factor_dia: Dict[str, float] = field(default_factory=dict)
    factor_clima: Dict[str, float] = field(default_factory=dict)
    factor_evento: Dict[str, float] = field(default_factory=dict)
    sigma_por_modo: Dict[str, float] = field(default_factory=dict)
    sigma_sistemica: float = 0.0
    observaciones: int = 0
    r2: float = 0.0

    def factor(self, dia: str, clima: str, evento: str) -> float:
        return (
            self.factor_dia.get(dia, 1.0)
            * self.factor_clima.get(clima, 1.0)
            * self.factor_evento.get(evento, 1.0)
        )

    def sigma(self, modo: str) -> float:
        return self.sigma_por_modo.get(modo, 0.12)


# 1. Generacion del historico sintetico
def generar_historico(
    G: nx.MultiDiGraph,
    observaciones: int = 6000,
    semilla: int = SEMILLA_POR_DEFECTO,
) -> pd.DataFrame:
    """
    Simula `observaciones` mediciones de tiempo de recorrido de tramos.

    Cada fila es "un vehiculo recorrio este tramo, este dia, con este clima y este
    evento, y tardo t minutos". La semilla fija hace el experimento reproducible,
    requisito para que los resultados del informe sean verificables.
    """
    rng = np.random.default_rng(semilla)

    aristas = [
        (u, v, d) for u, v, d in G.edges(data=True) if d["modo"] != "peatonal"
    ]
    if not aristas:
        raise ValueError("El grafo no tiene tramos de transporte")

    perfiles = list(config.PERFILES_HORARIOS)
    dias = list(FACTOR_DIA)
    climas = list(FACTOR_CLIMA)
    eventos = list(FACTOR_EVENTO)

    # Los eventos son raros: la mayoria de los dias no pasa nada.
    prob_evento = np.array([0.88, 0.05, 0.04, 0.03])
    # La lluvia intensa tambien es minoritaria en un dia cualquiera.
    prob_clima = np.array([0.68, 0.24, 0.08])

    indices = rng.integers(0, len(aristas), size=observaciones)
    jornadas = rng.integers(0, JORNADAS, size=observaciones)

    # Factor compartido de cada jornada: el dia en que TODO el sistema va lento.
    factor_jornada = rng.lognormal(
        mean=-0.5 * SIGMA_SISTEMICA ** 2, sigma=SIGMA_SISTEMICA, size=JORNADAS
    )

    filas = []

    for n_obs, i in enumerate(indices):
        u, v, datos = aristas[i]
        perfil = perfiles[rng.integers(0, len(perfiles))]
        dia = dias[rng.integers(0, len(dias))]
        clima = climas[rng.choice(len(climas), p=prob_clima)]
        evento = eventos[rng.choice(len(eventos), p=prob_evento)]

        # Los perfiles de fin de semana solo aparecen sabado y domingo.
        if perfil == "fin_de_semana" and dia not in ("sabado", "domingo"):
            dia = "sabado" if rng.random() < 0.5 else "domingo"

        cond = CondicionesRed(perfil_horario=perfil, criterio="tiempo")
        esperado = tiempo_arista(datos, cond)

        sigma = SIGMA_MODO.get(datos["modo"], 0.12)
        ruido = float(rng.lognormal(mean=-0.5 * sigma ** 2, sigma=sigma))

        jornada = int(jornadas[n_obs])
        observado = (
            esperado
            * FACTOR_DIA[dia]
            * FACTOR_CLIMA[clima]
            * FACTOR_EVENTO[evento]
            * float(factor_jornada[jornada])
            * ruido
        )

        filas.append({
            "jornada": jornada,
            "origen": u,
            "destino": v,
            "linea": datos["linea"],
            "modo": datos["modo"],
            "perfil_horario": perfil,
            "dia": dia,
            "clima": clima,
            "evento": evento,
            "minutos_esperados": esperado,
            "minutos_observados": observado,
        })

    return pd.DataFrame(filas)


# 2. Ajuste del modelo
def ajustar_modelo(historico: pd.DataFrame) -> ModeloTiempos:
    """
    Estima los factores multiplicativos y la dispersion residual.

    Se trabaja en escala logaritmica: log(observado/esperado) = log f_dia +
    log f_clima + log f_evento + log e. Los factores se estiman iterativamente
    como la media de los residuos por grupo (backfitting), lo que evita que un
    factor absorba el efecto de otro cuando las categorias no estan balanceadas.
    """
    if historico.empty:
        raise ValueError("El historico esta vacio")

    df = historico.copy()
    df["residuo"] = np.log(df["minutos_observados"] / df["minutos_esperados"])

    log_dia = {d: 0.0 for d in df["dia"].unique()}
    log_clima = {c: 0.0 for c in df["clima"].unique()}
    log_evento = {e: 0.0 for e in df["evento"].unique()}

    for _ in range(12):   # backfitting: converge en pocas pasadas
        base = df["residuo"] - df["clima"].map(log_clima) - df["evento"].map(log_evento)
        log_dia = base.groupby(df["dia"]).mean().to_dict()

        base = df["residuo"] - df["dia"].map(log_dia) - df["evento"].map(log_evento)
        log_clima = base.groupby(df["clima"]).mean().to_dict()

        base = df["residuo"] - df["dia"].map(log_dia) - df["clima"].map(log_clima)
        log_evento = base.groupby(df["evento"]).mean().to_dict()

    ajuste = (
        df["dia"].map(log_dia) + df["clima"].map(log_clima) + df["evento"].map(log_evento)
    )
    residual = df["residuo"] - ajuste

    # La variacion entre jornadas es la sistemica; la de dentro, la idiosincratica.
    sigma_sistemica = float(residual.groupby(df["jornada"]).mean().std())
    idiosincratico = residual - residual.groupby(df["jornada"]).transform("mean")

    sigma_por_modo = idiosincratico.groupby(df["modo"]).std().to_dict()

    varianza_total = float(df["residuo"].var())
    r2 = 1 - float(residual.var()) / varianza_total if varianza_total > 0 else 0.0

    return ModeloTiempos(
        sigma_sistemica=sigma_sistemica,
        factor_dia={k: float(np.exp(v)) for k, v in log_dia.items()},
        factor_clima={k: float(np.exp(v)) for k, v in log_clima.items()},
        factor_evento={k: float(np.exp(v)) for k, v in log_evento.items()},
        sigma_por_modo={k: float(v) for k, v in sigma_por_modo.items()},
        observaciones=len(df),
        r2=round(r2, 4),
    )


def comparar_con_la_verdad(modelo: ModeloTiempos) -> pd.DataFrame:
    """
    Contrasta los factores estimados con los que generaron los datos.

    Es la prueba de que el modelo funciona: si el error relativo es pequeno, el
    ajuste recupero la estructura real del fenomeno y no solo memorizo ruido.
    """
    filas = []
    for nombre, reales, estimados in (
        ("dia", FACTOR_DIA, modelo.factor_dia),
        ("clima", FACTOR_CLIMA, modelo.factor_clima),
        ("evento", FACTOR_EVENTO, modelo.factor_evento),
    ):
        # Los factores solo se identifican salvo una constante multiplicativa
        # comun; se normalizan por su media geometrica antes de comparar.
        def normalizar(d):
            valores = np.array(list(d.values()), dtype=float)
            return {k: v / float(np.exp(np.mean(np.log(valores)))) for k, v in d.items()}

        r_norm, e_norm = normalizar(reales), normalizar(estimados)
        for clave in reales:
            real, est = r_norm[clave], e_norm.get(clave, float("nan"))
            filas.append({
                "grupo": nombre,
                "categoria": clave,
                "factor_real": round(real, 4),
                "factor_estimado": round(est, 4),
                "error_%": round(100 * abs(est - real) / real, 2),
            })
    return pd.DataFrame(filas)


# 3. Prediccion sobre una ruta
# Cuantiles de la normal estandar para los niveles de confianza mas usados.
Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600}


def predecir_ruta(
    ruta: Ruta,
    modelo: ModeloTiempos,
    dia: str = "miercoles",
    clima: str = "despejado",
    evento: str = "ninguno",
    confianza: float = 0.90,
) -> Optional[dict]:
    """
    Tiempo esperado de la ruta y su intervalo de confianza.

    Devuelve None si la ruta no existe. El intervalo se construye sumando las
    varianzas de los tramos (independencia supuesta) y aplicando el cuantil
    normal correspondiente.
    """
    if not ruta.existe or not ruta.tramos:
        return None
    if confianza not in Z:
        raise ValueError(f"Nivel de confianza no soportado: {confianza}. "
                         f"Opciones: {sorted(Z)}")

    factor = modelo.factor(dia, clima, evento)

    media = 0.0
    varianza_idiosincratica = 0.0
    minutos_en_vehiculo = 0.0

    for tramo in ruta.tramos:
        # El tramo peatonal no depende del clima ni del trafico del mismo modo.
        esperado = tramo.minutos * (1.0 if tramo.modo == "peatonal" else factor)
        media += esperado + tramo.penalizacion_transbordo_min
        if tramo.modo != "peatonal":
            minutos_en_vehiculo += esperado
            varianza_idiosincratica += (esperado * modelo.sigma(tramo.modo)) ** 2

    # El componente sistemico afecta al viaje completo a la vez: no se diluye al
    # sumar tramos, y es el que domina en los trayectos largos.
    varianza_sistemica = (modelo.sigma_sistemica * minutos_en_vehiculo) ** 2
    varianza = varianza_idiosincratica + varianza_sistemica

    desviacion = float(np.sqrt(varianza))
    z = Z[confianza]

    return {
        "minutos_esperados": round(media, 1),
        "minutos_min": round(max(media - z * desviacion, 0.0), 1),
        "minutos_max": round(media + z * desviacion, 1),
        "desviacion_min": round(desviacion, 2),
        "confianza": confianza,
        "factor_contexto": round(factor, 4),
        "contexto": {"dia": dia, "clima": clima, "evento": evento},
        "peso_componente_sistemico": (
            round(varianza_sistemica / varianza, 3) if varianza > 0 else 0.0
        ),
        "supuesto": "La incertidumbre combina el azar propio de cada tramo con un "
                    "componente sistemico compartido por todo el viaje. No modela "
                    "retrasos en cascada entre tramos contiguos.",
    }


def perfil_de_incertidumbre(
    ruta: Ruta,
    modelo: ModeloTiempos,
    dias: Sequence[str] = tuple(FACTOR_DIA),
    clima: str = "despejado",
    evento: str = "ninguno",
    confianza: float = 0.90,
) -> pd.DataFrame:
    """Prediccion de la misma ruta para cada dia de la semana."""
    filas: List[dict] = []
    for dia in dias:
        p = predecir_ruta(ruta, modelo, dia, clima, evento, confianza)
        if p is None:
            continue
        filas.append({
            "dia": dia,
            "esperado": p["minutos_esperados"],
            "min": p["minutos_min"],
            "max": p["minutos_max"],
        })
    return pd.DataFrame(filas)
