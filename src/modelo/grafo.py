"""
Construccion del grafo dirigido y ponderado de la red SITVA.

Se usa `MultiDiGraph` con la LINEA como clave de arista: dos estaciones pueden
estar unidas por varios servicios y el algoritmo necesita distinguir por cual se
viaja para contar transbordos. Una estacion de intercambio es UN SOLO vertice; el
costo de cambiar de linea se aplica en el espacio de estados (nodo, linea).
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
            activa=True,
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
                activa=True,
            )

    # Indice auxiliar: que lineas sirve cada estacion.
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
    Metricas descriptivas del grafo: orden, tamano, grados, densidad y conexidad.

    La conexidad fuerte garantiza que exista un camino dirigido entre cualquier
    par ordenado de estaciones.
    """
    no_dirigido = nx.Graph(G)
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
    Matriz de adyacencia A (|V| x |V|): A[i][j] = 1 si existe la arista (i, j).

    El proyecto usa listas de adyacencia porque el grafo es disperso; la matriz
    se incluye como la otra representacion clasica del curso.
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
