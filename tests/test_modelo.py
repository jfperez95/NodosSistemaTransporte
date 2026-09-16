"""Pruebas del modelado: carga de datos, construccion del grafo y pesos."""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.modelo.carga_datos import (  # noqa: E402
    ErrorDatosRed,
    cargar_conexiones,
    cargar_estaciones,
)
from src.modelo.grafo import construir_grafo, lista_adyacencia, matriz_adyacencia  # noqa: E402
from src.modelo.pesos import (  # noqa: E402
    CondicionesRed,
    costo_arista,
    peso_arista,
    tiempo_arista,
)


@pytest.fixture(scope="module")
def G():
    return construir_grafo()


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #
def test_estaciones_y_conexiones_se_cargan():
    estaciones = cargar_estaciones()
    conexiones = cargar_conexiones(estaciones)
    assert len(estaciones) > 50
    assert len(conexiones) > 50


def test_toda_conexion_apunta_a_estaciones_existentes():
    estaciones = cargar_estaciones()
    for con in cargar_conexiones(estaciones):
        assert con.origen in estaciones
        assert con.destino in estaciones


def test_archivo_inexistente_falla_con_mensaje_claro():
    with pytest.raises(ErrorDatosRed):
        cargar_estaciones(RAIZ / "datos" / "no_existe.csv")


# --------------------------------------------------------------------------- #
# Estructura del grafo
# --------------------------------------------------------------------------- #
def test_el_grafo_es_dirigido_y_multigrafo(G):
    assert G.is_directed()
    assert G.is_multigraph()


def test_los_tramos_bidireccionales_generan_dos_aristas(G):
    assert G.has_edge("A01", "A02")
    assert G.has_edge("A02", "A01")


def test_el_grafo_es_fuertemente_conexo(G):
    """Garantiza que siempre exista ruta entre cualquier par ordenado."""
    import networkx as nx

    assert nx.is_strongly_connected(G)


def test_no_hay_estaciones_aisladas(G):
    assert min(dict(G.degree()).values()) >= 1


def test_san_antonio_es_estacion_de_intercambio(G):
    datos = G.nodes["A11"]
    assert datos["es_intercambio"]
    assert set(datos["lineas"]) == {"A", "B", "T"}


def test_matriz_y_lista_de_adyacencia_son_consistentes(G):
    nodos, A = matriz_adyacencia(G)
    adyacencia = lista_adyacencia(G)
    indice = {n: i for i, n in enumerate(nodos)}

    for u, vecinos in adyacencia.items():
        for v, _ in vecinos:
            assert A[indice[u]][indice[v]] == 1


def test_el_grafo_es_disperso(G):
    """|E| del orden de |V|: justifica usar lista y no matriz de adyacencia."""
    assert G.number_of_edges() < 5 * G.number_of_nodes()


# --------------------------------------------------------------------------- #
# Funcion de peso
# --------------------------------------------------------------------------- #
def test_todos_los_pesos_son_estrictamente_positivos(G):
    """Condicion que exige Dijkstra; si falla, el algoritmo deja de ser valido."""
    for criterio in config.CRITERIOS:
        for perfil in config.PERFILES_HORARIOS:
            cond = CondicionesRed(perfil_horario=perfil, criterio=criterio)
            for _, _, datos in G.edges(data=True):
                assert peso_arista(datos, cond) > 0


def test_la_hora_pico_es_mas_lenta_que_el_valle(G):
    datos = G["A01"]["A02"]["A"]
    pico = tiempo_arista(datos, CondicionesRed(perfil_horario="pico_tarde"))
    valle = tiempo_arista(datos, CondicionesRed(perfil_horario="valle_manana"))
    assert pico > valle


def test_la_lluvia_aumenta_el_tiempo(G):
    datos = G["A01"]["A02"]["A"]
    normal = tiempo_arista(datos, CondicionesRed())
    lluvia = tiempo_arista(datos, CondicionesRed(factor_clima=1.3))
    assert lluvia > normal


def test_el_transbordo_integrado_no_cobra_de_nuevo(G):
    """Metro -> cable comparten sistema tarifario: el transbordo es gratuito."""
    datos_cable = G["A04"]["K01"]["K"]
    assert costo_arista(datos_cable, sistema_previo=None) == 3300
    assert costo_arista(datos_cable, sistema_previo="riel") == 0


def test_el_transbordo_entre_sistemas_cobra_solo_el_recargo(G):
    datos_bus = G["O01"]["O02"]["O"]
    assert costo_arista(datos_bus, sistema_previo=None) == 3000
    assert costo_arista(datos_bus, sistema_previo="riel") == 500


def test_la_linea_turistica_cobra_su_recargo(G):
    datos_arvi = G["K03"]["L01"]["L"]
    assert costo_arista(datos_arvi, sistema_previo="riel") == 12000


# --------------------------------------------------------------------------- #
# Validacion de entradas
# --------------------------------------------------------------------------- #
def test_criterio_invalido_es_rechazado():
    with pytest.raises(ValueError):
        CondicionesRed(criterio="teletransporte")


def test_perfil_horario_invalido_es_rechazado():
    with pytest.raises(ValueError):
        CondicionesRed(perfil_horario="madrugada_marciana")
