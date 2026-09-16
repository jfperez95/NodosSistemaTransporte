"""Pruebas de los retos avanzados: resiliencia, prediccion y optimizacion."""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.algoritmos.dijkstra import dijkstra  # noqa: E402
from src.analisis.optimizacion import (  # noqa: E402
    agregar_conexion,
    detectar_brechas,
    evaluar_propuesta,
)
from src.analisis.prediccion import (  # noqa: E402
    FACTOR_CLIMA,
    FACTOR_DIA,
    ajustar_modelo,
    comparar_con_la_verdad,
    generar_historico,
    predecir_ruta,
)
from src.analisis.resiliencia import (  # noqa: E402
    centralidad_intermediacion,
    impacto_de_cierre,
    puntos_criticos,
    red_con_evento,
    responder_a_evento,
)
from src.modelo.grafo import construir_grafo  # noqa: E402
from src.modelo.pesos import CondicionesRed  # noqa: E402

# Muestra reducida: las pruebas verifican propiedades, no cifras de produccion.
MUESTRA = ("A01", "A21", "B06", "K03", "T08", "O01")


@pytest.fixture(scope="module")
def G():
    return construir_grafo()


@pytest.fixture(scope="module")
def cond():
    return CondicionesRed(criterio="tiempo")


# --------------------------------------------------------------------------- #
# Resiliencia
# --------------------------------------------------------------------------- #
def test_red_con_evento_no_altera_la_original(G):
    H = red_con_evento(G, estaciones_cerradas=["A11"])
    assert H.nodes["A11"]["activa"] is False
    assert G.nodes["A11"]["activa"] is True


def test_suspender_una_linea_desactiva_todos_sus_tramos(G):
    H = red_con_evento(G, lineas_suspendidas=["K"])
    tramos_k = [d for _, _, d in H.edges(data=True) if d["linea"] == "K"]
    assert tramos_k
    assert all(not d["activa"] for d in tramos_k)


def test_cerrar_estacion_inexistente_falla(G):
    with pytest.raises(KeyError):
        red_con_evento(G, estaciones_cerradas=["NO_EXISTE"])


def test_la_intermediacion_es_mayor_en_los_intercambios(G, cond):
    """San Antonio concentra tres lineas; una terminal de cable casi no ve paso."""
    c = centralidad_intermediacion(G, cond)
    assert c["A11"] > c["L01"]
    assert all(0.0 <= v <= 1.0 for v in c.values())


def test_cerrar_una_estacion_nunca_mejora_la_red(G, cond):
    """
    Con el promedio medido sobre los pares que sobreviven, cerrar no puede bajar
    el tiempo: si saliera negativo habria sesgo de supervivencia en la metrica.
    """
    for estacion in ("A11", "A14", "B03", "T05"):
        impacto = impacto_de_cierre(
            G, [estacion], condiciones=cond, origenes=MUESTRA
        )
        assert impacto["incremento_%"] >= -1e-9, estacion


def test_los_puntos_criticos_salen_ordenados_por_dano(G, cond):
    criticos = puntos_criticos(G, cond, top=5, origenes=MUESTRA)
    assert len(criticos) == 5
    perdidos = [c["pares_incomunicados"] for c in criticos]
    assert perdidos == sorted(perdidos, reverse=True)


def test_industriales_es_vertice_de_corte(G, cond):
    """
    La linea A es un camino: cualquier estacion intermedia separa el sur del
    norte. Industriales debe aparecer como vertice de corte.
    """
    impacto = impacto_de_cierre(G, ["A14"], condiciones=cond, origenes=MUESTRA)
    assert impacto["pares_incomunicados_adicionales"] > 0
    assert not impacto["sigue_fuertemente_conexa"]


def test_responder_a_evento_detecta_ruta_sin_alternativa(G, cond):
    r = responder_a_evento(G, "A01", "A21", ["A14"], condiciones=cond)
    assert r["ruta_original_afectada"]
    assert r["sin_alternativa"]
    assert not r["ruta_alterna"].existe


def test_responder_a_evento_ignora_cierres_lejanos(G, cond):
    """Cerrar una terminal de cable no afecta un viaje por la linea A."""
    r = responder_a_evento(G, "A01", "A21", ["J03"], condiciones=cond)
    assert not r["ruta_original_afectada"]
    assert r["minutos_extra"] == 0


# --------------------------------------------------------------------------- #
# Prediccion
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def modelo(G):
    return ajustar_modelo(generar_historico(G, observaciones=4000))


def test_el_historico_es_reproducible(G):
    a = generar_historico(G, observaciones=400, semilla=7)
    b = generar_historico(G, observaciones=400, semilla=7)
    assert a["minutos_observados"].equals(b["minutos_observados"])


def test_semillas_distintas_dan_historicos_distintos(G):
    a = generar_historico(G, observaciones=400, semilla=1)
    b = generar_historico(G, observaciones=400, semilla=2)
    assert not a["minutos_observados"].equals(b["minutos_observados"])


def test_el_modelo_recupera_los_factores_reales(modelo):
    """
    Prueba central del reto: el ajuste no conoce FACTOR_DIA ni FACTOR_CLIMA, los
    estima desde los datos. Un error por debajo del 5 % demuestra que recupero la
    estructura del fenomeno en vez de memorizar ruido.
    """
    comparacion = comparar_con_la_verdad(modelo)
    assert comparacion["error_%"].max() < 5.0


def test_el_modelo_explica_buena_parte_de_la_varianza(modelo):
    assert modelo.r2 > 0.4


def test_el_bus_es_mas_impredecible_que_el_metro(modelo):
    assert modelo.sigma("bus") > modelo.sigma("metro")


def test_el_intervalo_contiene_al_valor_esperado(G, cond, modelo):
    ruta = dijkstra(G, "A01", "A21", cond)
    p = predecir_ruta(ruta, modelo)
    assert p["minutos_min"] <= p["minutos_esperados"] <= p["minutos_max"]
    assert p["minutos_min"] >= 0


def test_mas_confianza_implica_intervalo_mas_ancho(G, cond, modelo):
    ruta = dijkstra(G, "A01", "A21", cond)
    estrecho = predecir_ruta(ruta, modelo, confianza=0.80)
    ancho = predecir_ruta(ruta, modelo, confianza=0.95)
    assert (ancho["minutos_max"] - ancho["minutos_min"]) > (
        estrecho["minutos_max"] - estrecho["minutos_min"]
    )


def test_la_lluvia_intensa_alarga_la_prediccion(G, cond, modelo):
    ruta = dijkstra(G, "A01", "A21", cond)
    seco = predecir_ruta(ruta, modelo, clima="despejado")
    mojado = predecir_ruta(ruta, modelo, clima="lluvia_intensa")
    assert mojado["minutos_esperados"] > seco["minutos_esperados"]


def test_el_domingo_es_mas_rapido_que_el_viernes(G, cond, modelo):
    ruta = dijkstra(G, "A01", "A21", cond)
    assert (
        predecir_ruta(ruta, modelo, dia="domingo")["minutos_esperados"]
        < predecir_ruta(ruta, modelo, dia="viernes")["minutos_esperados"]
    )


def test_predecir_ruta_inexistente_devuelve_none(G, cond, modelo):
    H = red_con_evento(G, estaciones_cerradas=["K03"])
    assert predecir_ruta(dijkstra(H, "A01", "L01", cond), modelo) is None


def test_nivel_de_confianza_no_soportado(G, cond, modelo):
    ruta = dijkstra(G, "A01", "A21", cond)
    with pytest.raises(ValueError):
        predecir_ruta(ruta, modelo, confianza=0.99)


def test_historico_vacio_es_rechazado():
    import pandas as pd

    with pytest.raises(ValueError):
        ajustar_modelo(pd.DataFrame())


# --------------------------------------------------------------------------- #
# Optimizacion
# --------------------------------------------------------------------------- #
def test_las_brechas_tienen_rodeo_mayor_que_uno(G, cond):
    brechas = detectar_brechas(G, cond, top=5, origenes=MUESTRA)
    assert brechas
    assert all(b["factor_rodeo"] > 1.0 for b in brechas)
    assert all(not G.has_edge(b["origen"], b["destino"]) for b in brechas)


def test_las_brechas_salen_ordenadas(G, cond):
    rodeos = [b["factor_rodeo"] for b in detectar_brechas(G, cond, top=6, origenes=MUESTRA)]
    assert rodeos == sorted(rodeos, reverse=True)


def test_agregar_conexion_crea_los_dos_sentidos(G):
    H = agregar_conexion(G, "B06", "O01")
    assert H.has_edge("B06", "O01", "NUEVA")
    assert H.has_edge("O01", "B06", "NUEVA")
    assert not G.has_edge("B06", "O01")


def test_agregar_conexion_rechaza_un_bucle(G):
    with pytest.raises(ValueError):
        agregar_conexion(G, "A11", "A11")


def test_una_conexion_nueva_nunca_empeora_la_red(G, cond):
    """
    Agregar una arista solo puede mantener o reducir el camino minimo: nunca
    alargarlo. Si la mejora saliera negativa, el calculo estaria mal.
    """
    r = evaluar_propuesta(G, "B06", "O01", cond, origenes=MUESTRA)
    assert r["mejora_red_%"] >= -1e-9
    assert r["minutos_par_despues"] <= r["minutos_par_antes"]


def test_unir_dos_extremos_lejanos_mejora_mucho_ese_par(G, cond):
    r = evaluar_propuesta(G, "O12", "A05", cond, origenes=MUESTRA)
    assert r["mejora_par_min"] > 10


def test_el_modelo_recupera_la_dispersion_sistemica(modelo):
    """
    La incertidumbre tiene dos componentes y el ajuste debe separarlos: la
    variacion ENTRE jornadas (sistemica) y la de cada tramo dentro de una misma
    jornada (idiosincratica).
    """
    from src.analisis.prediccion import SIGMA_SISTEMICA

    assert abs(modelo.sigma_sistemica - SIGMA_SISTEMICA) < 0.03


def test_en_rutas_largas_domina_el_componente_sistemico(G, cond, modelo):
    """
    Sin el termino sistemico, sumar 20 tramos independientes encogeria el
    intervalo por raiz de n y daria una precision falsa de +-1 minuto.
    """
    largo = predecir_ruta(dijkstra(G, "A01", "A21", cond), modelo)
    corto = predecir_ruta(dijkstra(G, "A11", "A10", cond), modelo)

    assert largo["peso_componente_sistemico"] > corto["peso_componente_sistemico"]
    assert largo["peso_componente_sistemico"] > 0.8
    # El intervalo debe ser de varios minutos, no de decimas.
    assert largo["minutos_max"] - largo["minutos_min"] > 5
