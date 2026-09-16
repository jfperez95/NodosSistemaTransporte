"""
Reto avanzado 2 - Analisis de resiliencia de la red.

Responde tres preguntas:

  1. **Que estaciones son criticas?** Se miden de dos formas complementarias:
     - *Centralidad de intermediacion* (betweenness): que fraccion de los caminos
       minimos de la red pasa por cada estacion. Es una medida estructural,
       barata, que senala los cuellos de botella topologicos.
     - *Impacto real de cierre*: se cierra la estacion, se recalculan las rutas y
       se mide cuanto empeora el tiempo promedio y cuantos pares quedan
       incomunicados. Es la medida honesta, y la que puede diferir de la
       intuicion: una estacion muy central puede tener alternativa, y una poco
       central puede ser un puente de corte (un vertice cuya eliminacion
       desconecta el grafo).

  2. **Que pasa si ocurre un evento disruptivo?** `red_con_evento` devuelve una
     copia del grafo con estaciones o tramos desactivados y, opcionalmente, con
     el clima degradado. Los algoritmos no cambian: `EspacioEstados` ya omite
     todo lo que este inactivo.

  3. **Cual es la ruta alternativa?** `responder_a_evento` calcula la ruta antes
     y despues del evento y cuantifica el sobrecosto para el usuario.
"""

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx

from src.algoritmos.benchmark import grafo_simple_de_tiempos
from src.algoritmos.dijkstra import dijkstra, dijkstra_todos_los_destinos
from src.algoritmos.ruta import Ruta
from src.modelo.pesos import CondicionesRed

# Origenes usados como muestra para estimar el tiempo promedio de la red.
# Cubren los cuatro extremos del sistema mas los principales intercambios, de
# modo que el promedio no quede sesgado hacia un solo corredor.
MUESTRA_ORIGENES = (
    "A01", "A21", "B06", "J03", "K03", "L01",
    "H02", "M02", "T08", "O01", "O12", "A11",
)


# --------------------------------------------------------------------------- #
# 1. Medidas de criticidad
# --------------------------------------------------------------------------- #
def centralidad_intermediacion(
    G: nx.MultiDiGraph, condiciones: CondicionesRed = None
) -> Dict[str, float]:
    """
    Centralidad de intermediacion de cada estacion, ponderada por tiempo.

    Para cada par (s, t) se calcula la fraccion de caminos minimos de s a t que
    pasan por el vertice v. Sumada sobre todos los pares y normalizada, da una
    medida de "cuanto trafico de paso" soporta la estacion.

    Se evalua sobre la proyeccion simple del multigrafo (peso = minutos), que es
    la representacion sobre la que la medida esta definida.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")
    H = grafo_simple_de_tiempos(G, condiciones)
    return nx.betweenness_centrality(H, weight="minutos", normalized=True)


def _distancias_desde_muestra(
    G: nx.MultiDiGraph,
    condiciones: CondicionesRed,
    origenes: Sequence[str],
) -> Dict[Tuple[str, str], float]:
    """
    Distancia minima de cada par (origen de la muestra, destino alcanzable).

    Se usa `dijkstra_todos_los_destinos`: una sola ejecucion por origen resuelve
    ese origen contra las 60 estaciones restantes, en vez de 60 busquedas
    independientes. Esa es la razon de conservar la variante sin parada temprana.
    """
    distancias: Dict[Tuple[str, str], float] = {}

    for origen in origenes:
        if not G.nodes[origen].get("activa", True):
            continue
        for destino, minutos in dijkstra_todos_los_destinos(
            G, origen, condiciones
        ).items():
            if destino == origen or not G.nodes[destino].get("activa", True):
                continue
            distancias[(origen, destino)] = minutos

    return distancias


def _comparar_escenarios(
    base: Dict[Tuple[str, str], float],
    nuevo: Dict[Tuple[str, str], float],
) -> Tuple[float, float, int]:
    """
    (promedio antes, promedio despues, pares que dejaron de existir).

    El promedio se calcula SOLO sobre los pares que siguen siendo alcanzables
    despues del evento. Compararlo contra el promedio de todos los pares
    originales seria enganoso: al desaparecer los trayectos largos -que son
    justamente los que el cierre rompe-, el promedio de los que sobreviven BAJA,
    y un cierre grave parece una mejora. Es sesgo de supervivencia; aqui se evita
    midiendo ambos escenarios sobre el mismo conjunto de pares.
    """
    comunes = [par for par in base if par in nuevo]
    perdidos = len(base) - len(comunes)

    if not comunes:
        return (float("inf"), float("inf"), perdidos)

    antes = sum(base[par] for par in comunes) / len(comunes)
    despues = sum(nuevo[par] for par in comunes) / len(comunes)
    return (antes, despues, perdidos)


def _tiempos_desde_muestra(
    G: nx.MultiDiGraph,
    condiciones: CondicionesRed,
    origenes: Sequence[str],
) -> Tuple[float, int]:
    """
    (tiempo promedio de viaje, pares inalcanzables) en la red tal como esta.

    Util para medir una red contra si misma -por ejemplo antes y despues de
    agregar una conexion nueva-, donde el conjunto de pares no se reduce.
    """
    distancias = _distancias_desde_muestra(G, condiciones, origenes)
    activos = [n for n, d in G.nodes(data=True) if d.get("activa", True)]
    posibles = len([o for o in origenes if G.nodes[o].get("activa", True)]) * (
        len(activos) - 1
    )

    if not distancias:
        return float("inf"), posibles

    promedio = sum(distancias.values()) / len(distancias)
    return promedio, max(posibles - len(distancias), 0)


def puntos_criticos(
    G: nx.MultiDiGraph,
    condiciones: CondicionesRed = None,
    top: int = 10,
    origenes: Sequence[str] = MUESTRA_ORIGENES,
) -> List[dict]:
    """
    Ordena las estaciones por el dano real que causaria cerrarlas.

    Para cada estacion se cierra la red en ella y se recalcula el tiempo promedio
    de viaje sobre la muestra de origenes. El resultado combina:

      * `incremento_%`: cuanto se alarga el viaje promedio.
      * `pares_incomunicados`: cuantos trayectos dejan de existir. Este es el
        indicador grave: senala los VERTICES DE CORTE del grafo, aquellos cuya
        eliminacion aumenta el numero de componentes conexas.

    Complejidad: |V| x |muestra| ejecuciones de Dijkstra. Con 61 estaciones y 12
    origenes son ~730 busquedas, alrededor de un segundo.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")
    base = _distancias_desde_muestra(G, condiciones, origenes)
    intermediacion = centralidad_intermediacion(G, condiciones)

    resultados = []
    for estacion in G.nodes:
        H = G.copy()
        H.nodes[estacion]["activa"] = False

        nuevo = _distancias_desde_muestra(H, condiciones, origenes)
        antes, despues, perdidos = _comparar_escenarios(base, nuevo)

        incremento = (
            float("inf") if antes == float("inf")
            else 100 * (despues - antes) / antes
        )

        resultados.append({
            "estacion": estacion,
            "nombre": G.nodes[estacion]["nombre"],
            "lineas": ",".join(G.nodes[estacion]["lineas"]),
            "grado": G.degree(estacion),
            "intermediacion": round(intermediacion.get(estacion, 0.0), 4),
            "incremento_%": round(incremento, 2) if incremento != float("inf") else None,
            "pares_incomunicados": perdidos,
            "es_vertice_de_corte": perdidos > 0,
        })

    resultados.sort(
        key=lambda r: (r["pares_incomunicados"], r["incremento_%"] or 0), reverse=True
    )
    return resultados[:top]


# --------------------------------------------------------------------------- #
# 2. Simulacion de eventos disruptivos
# --------------------------------------------------------------------------- #
def red_con_evento(
    G: nx.MultiDiGraph,
    estaciones_cerradas: Iterable[str] = (),
    tramos_cerrados: Iterable[Tuple[str, str, str]] = (),
    lineas_suspendidas: Iterable[str] = (),
) -> nx.MultiDiGraph:
    """
    Copia del grafo con los elementos afectados desactivados.

    Modela cierres por mantenimiento, incidentes o suspension completa de una
    linea. No se borran vertices ni aristas: se marcan como inactivos, de modo
    que la red original queda intacta y el evento es reversible.

    `tramos_cerrados` recibe tuplas (origen, destino, linea); se desactivan los
    DOS sentidos, porque un cierre de via fisica afecta ambos.
    """
    H = G.copy()

    for estacion in estaciones_cerradas:
        if estacion not in H:
            raise KeyError(f"La estacion {estacion} no existe en la red")
        H.nodes[estacion]["activa"] = False

    for origen, destino, linea in tramos_cerrados:
        for u, v in ((origen, destino), (destino, origen)):
            if H.has_edge(u, v, linea):
                H[u][v][linea]["activa"] = False

    suspendidas = set(lineas_suspendidas)
    if suspendidas:
        for u, v, clave, datos in H.edges(keys=True, data=True):
            if datos["linea"] in suspendidas:
                H[u][v][clave]["activa"] = False

    return H


def impacto_de_cierre(
    G: nx.MultiDiGraph,
    estaciones_cerradas: Iterable[str] = (),
    tramos_cerrados: Iterable[Tuple[str, str, str]] = (),
    lineas_suspendidas: Iterable[str] = (),
    condiciones: CondicionesRed = None,
    origenes: Sequence[str] = MUESTRA_ORIGENES,
) -> dict:
    """Metricas globales de la red antes y despues de un evento disruptivo."""
    condiciones = condiciones or CondicionesRed(criterio="tiempo")

    base = _distancias_desde_muestra(G, condiciones, origenes)

    H = red_con_evento(G, estaciones_cerradas, tramos_cerrados, lineas_suspendidas)
    nuevo = _distancias_desde_muestra(H, condiciones, origenes)
    base_promedio, nuevo_promedio, perdidos = _comparar_escenarios(base, nuevo)

    activas = [n for n, d in H.nodes(data=True) if d.get("activa", True)]
    subgrafo = H.subgraph(activas)

    return {
        "minutos_promedio_antes": round(base_promedio, 2),
        "minutos_promedio_despues": round(nuevo_promedio, 2),
        "incremento_%": round(100 * (nuevo_promedio - base_promedio) / base_promedio, 2),
        "pares_incomunicados_adicionales": perdidos,
        "estaciones_activas": len(activas),
        "sigue_fuertemente_conexa": nx.is_strongly_connected(subgrafo)
        if len(activas) > 1 else False,
        "componentes_fuertes": nx.number_strongly_connected_components(subgrafo),
    }


# --------------------------------------------------------------------------- #
# 3. Recalculo automatico de rutas
# --------------------------------------------------------------------------- #
def responder_a_evento(
    G: nx.MultiDiGraph,
    origen: str,
    destino: str,
    estaciones_cerradas: Iterable[str] = (),
    tramos_cerrados: Iterable[Tuple[str, str, str]] = (),
    lineas_suspendidas: Iterable[str] = (),
    condiciones: CondicionesRed = None,
) -> dict:
    """
    Ruta antes y despues del evento, con el sobrecosto para el usuario.

    Es la funcion que la interfaz llama cuando el usuario cierra una estacion:
    no hay que reimplementar nada, basta con recalcular sobre la red afectada.
    """
    condiciones = condiciones or CondicionesRed(criterio="tiempo")

    ruta_normal = dijkstra(G, origen, destino, condiciones)
    H = red_con_evento(G, estaciones_cerradas, tramos_cerrados, lineas_suspendidas)
    ruta_alterna = dijkstra(H, origen, destino, condiciones)

    afectada = _ruta_afectada(ruta_normal, H)

    minutos_extra: Optional[float] = None
    if ruta_normal.existe and ruta_alterna.existe:
        minutos_extra = round(
            ruta_alterna.minutos_totales - ruta_normal.minutos_totales, 2
        )

    return {
        "ruta_normal": ruta_normal,
        "ruta_alterna": ruta_alterna,
        "ruta_original_afectada": afectada,
        "minutos_extra": minutos_extra,
        "requiere_desvio": afectada and ruta_alterna.existe,
        "sin_alternativa": afectada and not ruta_alterna.existe,
    }


def _ruta_afectada(ruta: Ruta, H: nx.MultiDiGraph) -> bool:
    """Indica si el evento toca alguna estacion o tramo de la ruta original."""
    if not ruta.existe:
        return False
    for estacion in ruta.estaciones:
        if not H.nodes[estacion].get("activa", True):
            return True
    for tramo in ruta.tramos:
        if not H[tramo.origen][tramo.destino][tramo.linea].get("activa", True):
            return True
    return False
