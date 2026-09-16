"""
Paso 2 - Construccion del grafo dirigido y ponderado de la red SITVA.

Decisiones de modelado
----------------------
1. **Dirigido.** Cada tramo bidireccional se expande en dos aristas opuestas.
   Aunque hoy sean simetricas, esto permite representar mas adelante cierres o
   demoras que afectan un solo sentido (reto de resiliencia).

2. **Multigrafo.** Se usa `networkx.MultiDiGraph` con la LINEA como clave de la
   arista: dos estaciones pueden estar unidas por mas de un servicio y el
   algoritmo necesita distinguir por cual linea se viaja para poder contar
   transbordos.

3. **Los transbordos NO son nodos.** Una estacion de intercambio (San Antonio,
   Acevedo, San Javier...) es UN SOLO vertice que sirve a varias lineas. El costo
   de cambiar de linea se aplica en el espacio de estados (nodo, linea), no
   duplicando vertices: ver `src/algoritmos/espacio_estados.py`.
"""

from typing import Dict, List

import networkx as nx

from src.modelo.carga_datos import cargar_conexiones, cargar_estaciones
from src.modelo.entidades import Conexion, Estacion


def construir_grafo(
    estaciones: Dict[str, Estacion] = None,
    conexiones: List[Conexion] = None,
) -> nx.MultiDiGraph:
    """
    Construye G = (V, E) a partir de las estaciones y conexiones.

    Si no se pasan argumentos, carga los datos desde los CSV por defecto.
    Los atributos quedan disponibles en `G.nodes[u]` y `G[u][v][linea]`.
    """
    if estaciones is None:
        estaciones = cargar_estaciones()
    if conexiones is None:
        conexiones = cargar_conexiones(estaciones)

    G = nx.MultiDiGraph(nombre="SITVA - Valle de Aburra")

    for est in estaciones.values():
        G.add_node(
            est.id,
            nombre=est.nombre,
            linea=est.linea,
            modo=est.modo,
            latitud=est.latitud,
            longitud=est.longitud,
            direccion=est.direccion,
            tipo_estacion=est.tipo_estacion,
            accesibilidad=est.accesibilidad,
            servicios=est.servicios,
            activa=True,          # el reto de resiliencia la puede desactivar
        )

    for con in conexiones:
        pares = [(con.origen, con.destino)]
        if con.bidireccional:
            pares.append((con.destino, con.origen))

        for u, v in pares:
            G.add_edge(
                u, v,
                key=con.linea,
                linea=con.linea,
                modo=con.modo,
                tipo=con.tipo,
                tiempo_base_min=con.tiempo_base_min,
                distancia_km=con.distancia_km,
                capacidad_pasajeros_hora=con.capacidad_pasajeros_hora,
                activa=True,      # el reto de resiliencia la puede desactivar
            )

    # Indice auxiliar: que lineas sirve cada estacion. Sirve para la interfaz y
    # para detectar estaciones de intercambio reales.
    for nodo in G.nodes:
        lineas = {d["linea"] for _, _, d in G.out_edges(nodo, data=True)}
        lineas |= {d["linea"] for _, _, d in G.in_edges(nodo, data=True)}
        lineas.discard("PEA")
        G.nodes[nodo]["lineas"] = tuple(sorted(lineas))
        G.nodes[nodo]["es_intercambio"] = len(lineas) > 1

    return G


def lineas_de(G: nx.MultiDiGraph, nodo: str) -> tuple:
    """Lineas de servicio que pasan por una estacion."""
    return G.nodes[nodo]["lineas"]


def resumen_grafo(G: nx.MultiDiGraph) -> dict:
    """
    Metricas descriptivas del grafo, en el vocabulario de la teoria de grafos.

    Incluye orden |V|, tamano |E|, grados, densidad y conectividad. La conexidad
    fuerte es la propiedad relevante aqui: garantiza que exista al menos un
    camino dirigido entre CUALQUIER par ordenado de estaciones, es decir, que el
    calculador de rutas nunca fallara por falta de recorrido.
    """
    no_dirigido = nx.Graph(G)          # colapsa sentidos y lineas paralelas
    grados = dict(G.degree())

    componentes_fuertes = list(nx.strongly_connected_components(G))
    componentes_debiles = list(nx.weakly_connected_components(G))

    return {
        "orden_|V|": G.number_of_nodes(),
        "tamano_|E|": G.number_of_edges(),
        "aristas_subyacentes": no_dirigido.number_of_edges(),
        "grado_promedio": round(sum(grados.values()) / G.number_of_nodes(), 3),
        "grado_maximo": max(grados.values()),
        "grado_minimo": min(grados.values()),
        "estacion_de_mayor_grado": max(grados, key=grados.get),
        "densidad": round(nx.density(G), 5),
        "fuertemente_conexo": nx.is_strongly_connected(G),
        "componentes_fuertes": len(componentes_fuertes),
        "componentes_debiles": len(componentes_debiles),
        "estaciones_de_intercambio": sum(
            1 for _, d in G.nodes(data=True) if d["es_intercambio"]
        ),
        "lineas": sorted({d["linea"] for _, _, d in G.edges(data=True)}),
    }


def matriz_adyacencia(G: nx.MultiDiGraph):
    """
    Matriz de adyacencia A (|V| x |V|) del grafo subyacente.

    A[i][j] = 1 si existe la arista dirigida (i, j); 0 en caso contrario.
    Se incluye porque la guia del curso trabaja las dos representaciones
    clasicas -matriz de adyacencia y lista de adyacencia-; la implementacion del
    proyecto usa lista de adyacencia (la que ofrece networkx) porque el grafo es
    disperso: |E| es del orden de |V|, no de |V|^2.
    """
    nodos = sorted(G.nodes())
    indice = {n: i for i, n in enumerate(nodos)}
    A = [[0] * len(nodos) for _ in nodos]
    for u, v in G.edges():
        A[indice[u]][indice[v]] = 1
    return nodos, A


def lista_adyacencia(G: nx.MultiDiGraph) -> Dict[str, List[tuple]]:
    """Lista de adyacencia: {estacion: [(vecino, linea), ...]}."""
    return {
        u: sorted((v, d["linea"]) for _, v, d in G.out_edges(u, data=True))
        for u in sorted(G.nodes())
    }
