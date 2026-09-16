"""
Pruebas de humo de la interfaz (`app.py`).

Usan `streamlit.testing`, que ejecuta el script de la aplicacion sin navegador y
expone los elementos renderizados. No comprueban la apariencia -eso se revisa a
ojo-, sino que la aplicacion **no se rompe** en los escenarios que el usuario
puede provocar: el viaje trivial, la red interrumpida y los filtros imposibles.

Son mas lentas que el resto de la suite porque cada `run()` reconstruye el grafo
y ejecuta los cinco paneles.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(RAIZ / "app.py")
TIEMPO_LIMITE = 300


def app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=TIEMPO_LIMITE)


def _widget(at: AppTest, tipo: str, etiqueta: str):
    """Localiza un control de la barra lateral por su etiqueta visible."""
    for elemento in getattr(at, tipo):
        if elemento.label == etiqueta:
            return elemento
    raise AssertionError(f"No se encontro el control {tipo!r} '{etiqueta}'")


@pytest.fixture(scope="module")
def inicial() -> AppTest:
    return app().run()


def test_la_aplicacion_arranca_sin_excepciones(inicial):
    assert not inicial.exception


def test_muestra_las_metricas_del_viaje(inicial):
    etiquetas = [m.label for m in inicial.metric]
    for esperada in ("Tiempo", "Costo", "Transbordos", "Estaciones"):
        assert esperada in etiquetas


def test_muestra_las_metricas_del_grafo(inicial):
    etiquetas = [m.label for m in inicial.metric]
    assert "Vertices |V|" in etiquetas
    assert "Aristas |E|" in etiquetas


def test_no_hay_errores_en_el_arranque(inicial):
    assert [e.value for e in inicial.error] == []


def test_origen_igual_a_destino_informa_y_no_falla():
    at = app().run()
    _widget(at, "selectbox", "Destino").set_value("A01")
    at.run()

    assert not at.exception
    assert not at.error
    assert any("misma estacion" in i.value for i in at.info)


def test_con_estacion_cerrada_advierte_y_recalcula():
    at = app().run()
    _widget(at, "multiselect", "Estaciones cerradas").set_value(["K03"])
    at.run()

    assert not at.exception
    # La Linea L solo se alcanza por Santo Domingo: el destino queda aislado.
    assert any("No hay ruta" in e.value for e in at.error)
    assert any("Simulacion activa" in w.value for w in at.warning)


def test_evitar_todos_los_modos_no_rompe_la_aplicacion():
    at = app().run()
    _widget(at, "multiselect", "Evitar estos modos").set_value(
        ["metro", "tranvia", "cable", "bus"]
    )
    at.run()

    assert not at.exception
    assert any("No hay ruta" in e.value for e in at.error)


def test_cambiar_de_criterio_recalcula_sin_fallar():
    at = app().run()
    at.sidebar.radio[0].set_value("costo")
    at.run()

    assert not at.exception
    assert "Tiempo" in [m.label for m in at.metric]
