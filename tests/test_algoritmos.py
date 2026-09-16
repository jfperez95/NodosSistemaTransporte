"""
Pruebas de los algoritmos de busqueda de rutas.

Incluye los casos limite que exige la rubrica: origen igual a destino, estaciones
inexistentes, red interrumpida y filtros que dejan sin opciones al usuario.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.algoritmos.a_estrella import a_estrella  # noqa: E402
from src.algoritmos.benchmark import contrastar_con_networkx  # noqa: E402
from src.algoritmos.bfs_transbordos import minimos_transbordos  # noqa: E402
from src.algoritmos.dijkstra import dijkstra, dijkstra_todos_los_destinos  # noqa: E402
from src.algoritmos.k_rutas import k_rutas_alternativas  # noqa: E402
from src.modelo.grafo import construir_grafo  # noqa: E402
from src.modelo.pesos import CondicionesRed  # noqa: E402

PARES = [("A01", "A21"), ("K03", "J03"), ("H02", "A06"), ("O01", "L01"), ("B06", "T08")]


@pytest.fixture(scope="module")
def G():
    return construir_grafo()


# --------------------------------------------------------------------------- #
# Correccion de Dijkstra
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("origen,destino", PARES)
def test_dijkstra_encuentra_una_ruta_valida(G, origen, destino):
    ruta = dijkstra(G, origen, destino)
    assert ruta.existe
    assert ruta.estaciones[0] == origen
    assert ruta.estaciones[-1] == destino
    assert ruta.minutos_totales > 0


@pytest.mark.parametrize("origen,destino", PARES)
def test_la_ruta_es_un_camino_continuo(G, origen, destino):
    """Cada tramo debe empezar donde termino el anterior y existir en el grafo."""
    ruta = dijkstra(G, origen, destino)
    for anterior, siguiente in zip(ruta.tramos, ruta.tramos[1:]):
        assert anterior.destino == siguiente.origen
    for tramo in ruta.tramos:
        assert G.has_edge(tramo.origen, tramo.destino, tramo.linea)


@pytest.mark.parametrize("origen,destino", PARES)
def test_la_ruta_no_repite_estaciones(G, origen, destino):
    """Con pesos positivos, el camino minimo nunca contiene ciclos."""
    estaciones = dijkstra(G, origen, destino).estaciones
    assert len(estaciones) == len(set(estaciones))


def test_ruta_directa_por_la_linea_a_no_tiene_transbordos(G):
    ruta = dijkstra(G, "A01", "A21")
    assert ruta.num_transbordos == 0
    assert ruta.lineas_usadas == ["A"]
    assert ruta.num_estaciones == 21


def test_el_costo_de_un_viaje_solo_en_metro_es_una_tarifa(G):
    assert dijkstra(G, "A01", "A21").costo_total_cop == 3300


# --------------------------------------------------------------------------- #
# A* frente a Dijkstra
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("origen,destino", PARES)
def test_a_estrella_obtiene_el_mismo_optimo_que_dijkstra(G, origen, destino):
    """Si difirieran, la heuristica Haversine no seria admisible."""
    cond = CondicionesRed(criterio="tiempo")
    assert dijkstra(G, origen, destino, cond).peso_total == pytest.approx(
        a_estrella(G, origen, destino, cond).peso_total, abs=1e-9
    )


@pytest.mark.parametrize("origen,destino", PARES)
def test_a_estrella_no_expande_mas_estados_que_dijkstra(G, origen, destino):
    cond = CondicionesRed(criterio="tiempo")
    assert (
        a_estrella(G, origen, destino, cond).nodos_expandidos
        <= dijkstra(G, origen, destino, cond).nodos_expandidos
    )


@pytest.mark.parametrize("origen,destino", PARES[:3])
def test_coincide_con_networkx(G, origen, destino):
    c = contrastar_con_networkx(G, origen, destino)
    assert c["propio_no_mejora_la_cota"]


# --------------------------------------------------------------------------- #
# Criterios de optimizacion
# --------------------------------------------------------------------------- #
def test_cada_criterio_optimiza_su_propia_metrica(G):
    """
    La ruta mas rapida no puede ser mas lenta que la mas economica, y la mas
    economica no puede ser mas cara que la mas rapida.
    """
    origen, destino = "A12", "A14"
    cond = lambda c: CondicionesRed(criterio=c, perfil_horario="valle_manana")  # noqa: E731

    rapida = dijkstra(G, origen, destino, cond("tiempo"))
    economica = dijkstra(G, origen, destino, cond("costo"))

    assert rapida.minutos_totales <= economica.minutos_totales
    assert economica.costo_total_cop <= rapida.costo_total_cop


@pytest.mark.parametrize("criterio", sorted(config.CRITERIOS))
def test_todos_los_criterios_producen_ruta(G, criterio):
    ruta = dijkstra(G, "H02", "A06", CondicionesRed(criterio=criterio))
    assert ruta.existe


# --------------------------------------------------------------------------- #
# BFS: minimo de transbordos
# --------------------------------------------------------------------------- #
def test_misma_linea_implica_cero_transbordos(G):
    assert minimos_transbordos(G, "A01", "A21") == 0


@pytest.mark.parametrize("origen,destino", PARES)
def test_dijkstra_alcanza_la_cota_de_transbordos_de_bfs(G, origen, destino):
    """
    BFS da el minimo teorico de cambios de linea. Dijkstra con el criterio
    `transbordos` debe alcanzarlo exactamente: si lo supera, el conteo de
    transbordos del modelo esta mal.
    """
    cota = minimos_transbordos(G, origen, destino)
    ruta = dijkstra(G, origen, destino, CondicionesRed(criterio="transbordos"))
    assert cota is not None
    assert ruta.num_transbordos == cota


# --------------------------------------------------------------------------- #
# Yen: rutas alternativas
# --------------------------------------------------------------------------- #
def test_yen_devuelve_rutas_distintas_y_ordenadas(G):
    rutas = k_rutas_alternativas(G, "A09", "O08", k=3)
    assert len(rutas) >= 2

    firmas = {tuple(r.estaciones) for r in rutas}
    assert len(firmas) == len(rutas)

    pesos = [r.peso_total for r in rutas]
    assert pesos == sorted(pesos)


def test_la_primera_ruta_de_yen_es_la_de_dijkstra(G):
    cond = CondicionesRed(criterio="tiempo")
    mejor_yen = k_rutas_alternativas(G, "A09", "O08", k=3, condiciones=cond)[0]
    assert mejor_yen.estaciones == dijkstra(G, "A09", "O08", cond).estaciones


def test_yen_rechaza_k_invalido(G):
    with pytest.raises(ValueError):
        k_rutas_alternativas(G, "A01", "A21", k=0)


# --------------------------------------------------------------------------- #
# Casos limite
# --------------------------------------------------------------------------- #
def test_origen_igual_a_destino(G):
    ruta = dijkstra(G, "A11", "A11")
    assert ruta.existe
    assert ruta.tramos == []
    assert ruta.minutos_totales == 0
    assert ruta.costo_total_cop == 0


def test_estacion_inexistente(G):
    with pytest.raises(KeyError):
        dijkstra(G, "ZZZ", "A01")


def test_sin_ruta_cuando_se_cierra_la_unica_conexion(G):
    """
    Arvi solo se alcanza por la linea L desde Santo Domingo. Al desactivar esa
    estacion, la red queda sin camino y el sistema debe decirlo, no fallar.
    """
    H = construir_grafo()
    H.nodes["K03"]["activa"] = False

    ruta = dijkstra(H, "A01", "L01")
    assert not ruta.existe
    assert ruta.motivo


def test_filtrar_todos_los_modos_deja_sin_ruta(G):
    cond = CondicionesRed(evitar_modos=frozenset(config.MODOS))
    assert not dijkstra(G, "A01", "A21", cond).existe


def test_evitar_el_cable_cambia_la_ruta(G):
    """El usuario con vertigo debe poder pedir una ruta sin Metrocable."""
    sin_cable = CondicionesRed(evitar_modos=frozenset({"cable"}))
    ruta = dijkstra(G, "A04", "A11", sin_cable)
    assert ruta.existe
    assert all(t.modo != "cable" for t in ruta.tramos)


def test_dijkstra_a_todos_los_destinos_cubre_la_red(G):
    distancias = dijkstra_todos_los_destinos(G, "A11")
    assert len(distancias) == G.number_of_nodes()
    assert distancias["A11"] == 0
    assert all(d >= 0 for d in distancias.values())
