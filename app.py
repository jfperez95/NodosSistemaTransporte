"""
Paso 4 - Interfaz de usuario del calculador de rutas.

Aplicacion Streamlit organizada en cinco pestanas:

  1. Ruta           - el MVP: origen, destino, criterio, hora y mapa con la ruta.
  2. La red         - metricas del grafo y comparacion de algoritmos.
  3. Resiliencia    - estaciones criticas, eventos disruptivos y desvios.
  4. Prediccion     - tiempos con intervalo de confianza.
  5. Optimizacion   - brechas de la red y simulacion de nuevas conexiones.

Ejecutar con:  streamlit run app.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import altair as alt          # noqa: E402  (lo trae Streamlit)
import pandas as pd           # noqa: E402
import streamlit as st        # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from src import config                                    # noqa: E402
from src.algoritmos.benchmark import comparar_lote        # noqa: E402
from src.algoritmos.bfs_transbordos import minimos_transbordos  # noqa: E402
from src.algoritmos.dijkstra import dijkstra              # noqa: E402
from src.algoritmos.k_rutas import k_rutas_alternativas   # noqa: E402
from src.analisis.optimizacion import proponer_conexiones  # noqa: E402
from src.analisis.prediccion import (                      # noqa: E402
    FACTOR_CLIMA,
    FACTOR_DIA,
    FACTOR_EVENTO,
    ajustar_modelo,
    comparar_con_la_verdad,
    generar_historico,
    perfil_de_incertidumbre,
    predecir_ruta,
)
from src.analisis.resiliencia import (                     # noqa: E402
    impacto_de_cierre,
    puntos_criticos,
    red_con_evento,
    responder_a_evento,
)
from src.modelo.grafo import construir_grafo, resumen_grafo  # noqa: E402
from src.modelo.pesos import CondicionesRed                  # noqa: E402
from src.visual.mapa import leyenda_html, mapa_de_la_red     # noqa: E402

TINTA = "#111827"
TINTA_SUAVE = "#6B7280"
PRIMARIO = config.COLOR_MODO["metro"]

st.set_page_config(
    page_title="Rutas optimas - Metro de Medellin",
    page_icon="M",
    layout="wide",
)


# --------------------------------------------------------------------------- #
# Carga con cache
# --------------------------------------------------------------------------- #
@st.cache_resource
def cargar_grafo():
    """El grafo se construye una sola vez por sesion."""
    return construir_grafo()


@st.cache_data(show_spinner="Analizando la resiliencia de la red...")
def criticos_cacheados(perfil: str, top: int):
    return puntos_criticos(cargar_grafo(), CondicionesRed(perfil_horario=perfil), top=top)


@st.cache_data(show_spinner="Simulando el historico de tiempos...")
def modelo_cacheado(observaciones: int = 6000):
    historico = generar_historico(cargar_grafo(), observaciones)
    return ajustar_modelo(historico), historico


@st.cache_data(show_spinner="Buscando mejoras a la red...")
def propuestas_cacheadas(perfil: str):
    return proponer_conexiones(cargar_grafo(), CondicionesRed(perfil_horario=perfil))


G = cargar_grafo()
NOMBRES = {n: d["nombre"] for n, d in G.nodes(data=True)}
ORDEN = sorted(G.nodes, key=lambda n: NOMBRES[n])


def etiqueta(nodo: str) -> str:
    d = G.nodes[nodo]
    return f"{d['nombre']}  ·  {config.NOMBRE_MODO[d['modo']]} ({', '.join(d['lineas'])})"


# --------------------------------------------------------------------------- #
# Barra lateral: la consulta
# --------------------------------------------------------------------------- #
st.sidebar.title("Planear viaje")

origen = st.sidebar.selectbox(
    "Origen", ORDEN, index=ORDEN.index("A01"), format_func=etiqueta
)
destino = st.sidebar.selectbox(
    "Destino", ORDEN, index=ORDEN.index("L01"), format_func=etiqueta
)

st.sidebar.divider()

criterio = st.sidebar.radio(
    "Optimizar por",
    list(config.CRITERIOS),
    format_func=lambda c: config.CRITERIOS[c]["etiqueta"],
)

perfil = st.sidebar.selectbox(
    "Momento del viaje",
    list(config.PERFILES_HORARIOS),
    index=list(config.PERFILES_HORARIOS).index("pico_manana"),
    format_func=lambda p: config.PERFILES_HORARIOS[p]["etiqueta"],
)

clima = st.sidebar.select_slider(
    "Clima",
    options=["Despejado", "Lluvia ligera", "Lluvia intensa"],
    value="Despejado",
)
FACTOR_POR_CLIMA = {"Despejado": 1.0, "Lluvia ligera": 1.12, "Lluvia intensa": 1.30}

with st.sidebar.expander("Filtros de preferencia"):
    evitar = st.multiselect(
        "Evitar estos modos",
        [m for m in config.MODOS if m != "peatonal"],
        format_func=lambda m: config.NOMBRE_MODO[m],
        help="Por ejemplo, evitar el Metrocable si el usuario tiene vertigo.",
    )
    k_rutas = st.slider("Rutas alternativas a mostrar", 1, 5, 3)

with st.sidebar.expander("Simular interrupciones"):
    cerradas = st.multiselect(
        "Estaciones cerradas", ORDEN, format_func=lambda n: NOMBRES[n]
    )
    lineas_disponibles = sorted(
        {d["linea"] for _, _, d in G.edges(data=True) if d["linea"] != "PEA"}
    )
    suspendidas = st.multiselect("Lineas suspendidas", lineas_disponibles)

st.sidebar.divider()
st.sidebar.markdown(leyenda_html(), unsafe_allow_html=True)

condiciones = CondicionesRed(
    perfil_horario=perfil,
    criterio=criterio,
    factor_clima=FACTOR_POR_CLIMA[clima],
    evitar_modos=frozenset(evitar),
)

hay_evento = bool(cerradas or suspendidas)
G_activo = red_con_evento(G, cerradas, (), suspendidas) if hay_evento else G


# --------------------------------------------------------------------------- #
# Encabezado
# --------------------------------------------------------------------------- #
st.title("Rutas optimas del Metro de Medellin")
st.caption(
    "Sistema Integrado de Transporte del Valle de Aburra modelado como grafo "
    "dirigido, ponderado y dinamico · Practica entregable #2, Equipo 2"
)

if hay_evento:
    st.warning(
        f"Simulacion activa: {len(cerradas)} estacion(es) cerrada(s) y "
        f"{len(suspendidas)} linea(s) suspendida(s). Todos los calculos usan la "
        "red interrumpida."
    )

pestanas = st.tabs(
    ["Ruta", "La red", "Resiliencia", "Prediccion", "Optimizacion"]
)


# --------------------------------------------------------------------------- #
# 1. Ruta (MVP)
# --------------------------------------------------------------------------- #
with pestanas[0]:
    # No se usa st.stop(): detendria el script entero y dejaria las demas
    # pestanas en blanco. El caso trivial se resuelve dentro de esta pestana.
    ruta = (
        None if origen == destino
        else dijkstra(G_activo, origen, destino, condiciones)
    )

    if ruta is None:
        st.info(
            "El origen y el destino son la misma estacion: el viaje dura 0 minutos "
            "y no cuesta nada. Elige un destino distinto para calcular una ruta."
        )
    elif not ruta.existe:
        st.error(
            f"No hay ruta entre **{NOMBRES[origen]}** y **{NOMBRES[destino]}** "
            f"con las condiciones actuales.\n\n{ruta.motivo}"
        )
        if evitar:
            st.caption("Prueba quitando alguno de los filtros de modo.")
        if hay_evento:
            st.caption("O reabriendo alguna de las estaciones cerradas.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tiempo", f"{ruta.minutos_totales:.0f} min")
        c2.metric("Costo", f"${ruta.costo_total_cop:,}")
        c3.metric("Transbordos", ruta.num_transbordos)
        c4.metric("Estaciones", ruta.num_estaciones)

        st.caption(
            f"Lineas: **{' → '.join(ruta.lineas_usadas)}**  ·  "
            f"{config.CRITERIOS[criterio]['etiqueta'].lower()}  ·  "
            f"{config.PERFILES_HORARIOS[perfil]['etiqueta'].lower()}  ·  "
            f"calculado con {ruta.algoritmo} expandiendo "
            f"{ruta.nodos_expandidos} estados"
        )

        izquierda, derecha = st.columns([3, 2])

        with izquierda:
            st_folium(
                mapa_de_la_red(G_activo, ruta, origen, destino),
                height=520,
                width=None,
                returned_objects=[],
            )

        with derecha:
            st.subheader("Itinerario")
            for i, t in enumerate(ruta.tramos, 1):
                marca = " · **transbordo**" if t.es_transbordo else ""
                st.markdown(
                    f"<div style='border-left:3px solid {config.COLOR_MODO[t.modo]};"
                    f"padding:2px 0 6px 10px;margin-bottom:4px'>"
                    f"<b>{i}. {t.nombre_origen} → {t.nombre_destino}</b><br>"
                    f"<span style='color:{TINTA_SUAVE};font-size:13px'>"
                    f"{config.NOMBRE_MODO[t.modo]} · linea {t.linea} · "
                    f"{t.minutos:.1f} min{marca}</span></div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        st.subheader("Rutas alternativas")
        alternativas = k_rutas_alternativas(
            G_activo, origen, destino, k=k_rutas, condiciones=condiciones
        )
        if len(alternativas) == 1:
            st.caption(
                "No hay alternativas razonablemente distintas: la red es poco "
                "mallada en este corredor y cualquier desvio repite casi las "
                "mismas estaciones."
            )
        else:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Opcion": i,
                        "Minutos": a.minutos_totales,
                        "Costo (COP)": a.costo_total_cop,
                        "Transbordos": a.num_transbordos,
                        "Estaciones": a.num_estaciones,
                        "Lineas": " → ".join(a.lineas_usadas),
                    }
                    for i, a in enumerate(alternativas, 1)
                ]),
                hide_index=True,
                width="stretch",
            )

        st.divider()
        st.subheader("El mismo viaje a lo largo del dia")
        por_hora = pd.DataFrame([
            {
                "Franja": config.PERFILES_HORARIOS[p]["etiqueta"],
                "Minutos": dijkstra(
                    G_activo, origen, destino,
                    CondicionesRed(
                        perfil_horario=p, criterio=criterio,
                        factor_clima=FACTOR_POR_CLIMA[clima],
                        evitar_modos=frozenset(evitar),
                    ),
                ).minutos_totales,
            }
            for p in config.PERFILES_HORARIOS
        ])
        # Serie unica: sin leyenda, el titulo de la seccion ya la nombra.
        st.altair_chart(
            alt.Chart(por_hora).mark_bar(size=18, cornerRadiusEnd=4, color=PRIMARIO)
            .encode(
                y=alt.Y("Franja:N", sort=None, title=None),
                x=alt.X("Minutos:Q", title="Minutos de viaje"),
                tooltip=["Franja", "Minutos"],
            ).properties(height=210),
            width="stretch",
        )
        st.caption(
            "Esta variacion es lo que hace del modelo un grafo *dinamico*: el peso "
            "de cada tramo se recalcula con la franja horaria y el clima."
        )


# --------------------------------------------------------------------------- #
# 2. La red
# --------------------------------------------------------------------------- #
with pestanas[1]:
    st.subheader("El sistema como grafo G = (V, E, w)")
    resumen = resumen_grafo(G)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Vertices |V|", resumen["orden_|V|"])
    c2.metric("Aristas |E|", resumen["tamano_|E|"])
    c3.metric("Grado promedio", resumen["grado_promedio"])
    c4.metric("Densidad", resumen["densidad"])

    if resumen["fuertemente_conexo"]:
        st.success(
            "El grafo es **fuertemente conexo**: existe al menos un camino "
            "dirigido entre cualquier par ordenado de estaciones, de modo que el "
            "calculador nunca falla por falta de recorrido."
        )

    st.caption(
        f"Solo el {100 * resumen['tamano_|E|'] / resumen['orden_|V|'] ** 2:.1f} % "
        "de la matriz de adyacencia tiene un 1: el grafo es **disperso**, y por eso "
        "se representa con listas de adyacencia y no con una matriz."
    )

    st.divider()
    st.subheader("Comparacion de algoritmos")
    st.caption(
        "Dijkstra explora por costo acumulado; A\\* lo hace guiado por la "
        "distancia geografica al destino. Al ser la heuristica admisible, ambos "
        "encuentran **el mismo optimo**, pero A\\* llega expandiendo menos estados."
    )

    if st.button("Ejecutar benchmark"):
        pares = [("A01", "A21"), ("K03", "J03"), ("H02", "A06"),
                 ("O01", "L01"), ("B06", "T08")]
        resultado = comparar_lote(G, pares, CondicionesRed(criterio="tiempo"))

        st.dataframe(
            pd.DataFrame(resultado["detalle"]).rename(columns={
                "origen": "Origen", "destino": "Destino",
                "dijkstra_expandidos": "Dijkstra (estados)",
                "a_estrella_expandidos": "A* (estados)",
                "reduccion_expansion_%": "Ahorro %",
                "dijkstra_ms": "Dijkstra (ms)", "a_estrella_ms": "A* (ms)",
                "mismo_optimo": "Mismo optimo",
            })[["Origen", "Destino", "Dijkstra (estados)", "A* (estados)",
                "Ahorro %", "Dijkstra (ms)", "A* (ms)", "Mismo optimo"]],
            hide_index=True,
            width="stretch",
        )

        r = resultado["resumen"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Ahorro medio de expansion", f"{r['reduccion_expansion_prom_%']} %")
        c2.metric("Dijkstra", f"{r['dijkstra_ms_prom']} ms")
        c3.metric("A*", f"{r['a_estrella_ms_prom']} ms")

        if r["todos_coinciden_en_el_optimo"]:
            st.success("A\\* y Dijkstra coinciden en el optimo en todos los pares.")
        else:
            st.error("A\\* difiere de Dijkstra: la heuristica no es admisible.")

    st.divider()
    st.subheader("Transbordos minimos por BFS")
    cota = minimos_transbordos(G, origen, destino)
    real = dijkstra(G, origen, destino, CondicionesRed(criterio="transbordos"))
    c1, c2 = st.columns(2)
    c1.metric("Minimo teorico (BFS sobre el grafo de lineas)", cota)
    c2.metric("Obtenido por Dijkstra", real.num_transbordos)
    st.caption(
        "Dos algoritmos distintos sobre dos representaciones distintas llegando al "
        "mismo numero: es la verificacion cruzada de que el modelo cuenta bien los "
        "transbordos."
    )


# --------------------------------------------------------------------------- #
# 3. Resiliencia
# --------------------------------------------------------------------------- #
with pestanas[2]:
    st.subheader("Estaciones criticas")
    st.caption(
        "Cada estacion se cierra y se recalcula la red completa. Se reportan los "
        "trayectos que dejan de existir -los **vertices de corte** del grafo- y "
        "cuanto se alarga el viaje promedio de los que sobreviven."
    )

    criticas = criticos_cacheados(perfil, 10)
    st.dataframe(
        pd.DataFrame(criticas).rename(columns={
            "nombre": "Estacion", "lineas": "Lineas", "grado": "Grado",
            "intermediacion": "Intermediacion",
            "incremento_%": "Viaje promedio +%",
            "pares_incomunicados": "Trayectos perdidos",
            "es_vertice_de_corte": "Vertice de corte",
        })[["Estacion", "Lineas", "Grado", "Intermediacion",
            "Viaje promedio +%", "Trayectos perdidos", "Vertice de corte"]],
        hide_index=True,
        width="stretch",
    )

    st.divider()
    st.subheader("Impacto del evento simulado")

    if not hay_evento:
        st.info(
            "Cierra estaciones o suspende lineas en **Simular interrupciones** "
            "(barra lateral) para medir el impacto y ver el desvio propuesto."
        )
    else:
        impacto = impacto_de_cierre(
            G, cerradas, (), suspendidas, condiciones=condiciones
        )
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Viaje promedio",
            f"{impacto['minutos_promedio_despues']:.1f} min",
            f"{impacto['incremento_%']:+.2f} %",
            delta_color="inverse",
        )
        c2.metric("Trayectos perdidos", impacto["pares_incomunicados_adicionales"])
        c3.metric("Componentes fuertes", impacto["componentes_fuertes"])

        if not impacto["sigue_fuertemente_conexa"]:
            st.error(
                "La red deja de ser fuertemente conexa: hay estaciones que ya no "
                "se pueden alcanzar desde otras."
            )

        respuesta = responder_a_evento(
            G, origen, destino, cerradas, (), suspendidas, condiciones
        )
        st.markdown("**Efecto sobre tu viaje**")
        if not respuesta["ruta_original_afectada"]:
            st.success("Tu ruta habitual no se ve afectada por este evento.")
        elif respuesta["sin_alternativa"]:
            st.error(
                "Tu ruta queda cortada y **no existe alternativa**: el sistema no "
                "puede llevarte a ese destino mientras dure la interrupcion."
            )
        else:
            st.warning(
                f"Tu ruta queda cortada. El desvio automatico anade "
                f"**{respuesta['minutos_extra']:.0f} minutos**."
            )
            st_folium(
                mapa_de_la_red(
                    G_activo, respuesta["ruta_alterna"], origen, destino,
                    marcas=[
                        {"estacion": e, "color": "#B91C1C", "texto": f"Cerrada: {NOMBRES[e]}"}
                        for e in cerradas
                    ],
                ),
                height=430, returned_objects=[],
            )


# --------------------------------------------------------------------------- #
# 4. Prediccion
# --------------------------------------------------------------------------- #
with pestanas[3]:
    st.subheader("Tiempo esperado, con intervalo de confianza")
    st.caption(
        "Un tiempo puntual es una promesa que la red no puede cumplir. Sobre un "
        "historico sintetico de recorridos se estima el efecto del dia, el clima y "
        "los eventos, y se propaga la incertidumbre a lo largo de la ruta."
    )

    modelo, historico = modelo_cacheado()

    c1, c2, c3, c4 = st.columns(4)
    dia = c1.selectbox("Dia", list(FACTOR_DIA), index=2)
    clima_pred = c2.selectbox("Clima", list(FACTOR_CLIMA))
    evento = c3.selectbox("Evento especial", list(FACTOR_EVENTO))
    confianza = c4.selectbox("Confianza", [0.80, 0.90, 0.95], index=1,
                             format_func=lambda x: f"{x:.0%}")

    ruta_pred = dijkstra(G_activo, origen, destino, condiciones)
    prediccion = predecir_ruta(ruta_pred, modelo, dia, clima_pred, evento, confianza)

    if prediccion is None:
        st.info("No hay ruta que predecir con las condiciones actuales.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Tiempo esperado", f"{prediccion['minutos_esperados']:.0f} min")
        c2.metric(
            f"Intervalo al {confianza:.0%}",
            f"{prediccion['minutos_min']:.0f} – {prediccion['minutos_max']:.0f} min",
        )
        c3.metric("Desviacion", f"± {prediccion['desviacion_min']:.1f} min")

        perfil_dias = perfil_de_incertidumbre(
            ruta_pred, modelo, clima=clima_pred, evento=evento, confianza=confianza
        )
        base = alt.Chart(perfil_dias).encode(
            y=alt.Y("dia:N", sort=None, title=None)
        )
        st.altair_chart(
            (
                base.mark_rule(strokeWidth=2, color=TINTA_SUAVE).encode(
                    x=alt.X("min:Q", title="Minutos de viaje",
                            scale=alt.Scale(zero=False)),
                    x2="max:Q",
                    tooltip=["dia", "min", "esperado", "max"],
                )
                + base.mark_point(size=90, filled=True, color=PRIMARIO,
                                  stroke="#FFFFFF", strokeWidth=2).encode(
                    x="esperado:Q",
                    tooltip=["dia", "min", "esperado", "max"],
                )
            ).properties(height=230),
            width="stretch",
        )
        st.caption(
            f"Punto = tiempo esperado; barra = intervalo al {confianza:.0%}. "
            f"{prediccion['supuesto']}"
        )

    with st.expander("Validacion del modelo"):
        st.caption(
            "El modelo no recibe los factores con que se simularon los datos: los "
            "estima. Si el error es pequeno, recupero la estructura real del "
            "fenomeno y no memorizo ruido."
        )
        c1, c2 = st.columns(2)
        c1.metric("Observaciones", f"{modelo.observaciones:,}")
        c2.metric("Varianza explicada (R²)", f"{modelo.r2:.3f}")
        st.dataframe(comparar_con_la_verdad(modelo), hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# 5. Optimizacion
# --------------------------------------------------------------------------- #
with pestanas[4]:
    st.subheader("Donde convendria construir")
    st.caption(
        "Se buscan pares de estaciones **geograficamente cercanas pero "
        "topologicamente lejanas**: el factor de rodeo mide cuantas veces mas "
        "tarda el viaje real frente a la linea recta. Cada candidata se construye "
        "en el grafo y se mide la mejora real del tiempo promedio de la red."
    )

    propuestas = propuestas_cacheadas(perfil)

    if not propuestas:
        st.info("Ninguna de las candidatas mejora el promedio de la red.")
    else:
        st.dataframe(
            pd.DataFrame(propuestas).rename(columns={
                "nombre_origen": "Desde", "nombre_destino": "Hasta",
                "km_de_via_nueva": "Km de via",
                "factor_rodeo_previo": "Rodeo actual",
                "minutos_par_antes": "Min. antes", "minutos_par_despues": "Min. despues",
                "mejora_red_%": "Mejora de la red %",
                "mejora_por_km": "Min. ahorrados por km",
            })[["Desde", "Hasta", "Km de via", "Rodeo actual", "Min. antes",
                "Min. despues", "Mejora de la red %", "Min. ahorrados por km"]],
            hide_index=True,
            width="stretch",
        )

        mejor = propuestas[0]
        st.success(
            f"La mejor propuesta une **{mejor['nombre_origen']}** con "
            f"**{mejor['nombre_destino']}**: {mejor['km_de_via_nueva']:.1f} km de "
            f"via nueva bajan ese trayecto de {mejor['minutos_par_antes']:.0f} a "
            f"{mejor['minutos_par_despues']:.0f} minutos y mejoran el tiempo "
            f"promedio de toda la red un {mejor['mejora_red_%']:.2f} %."
        )

        st_folium(
            mapa_de_la_red(G, propuestas=propuestas),
            height=480, returned_objects=[],
        )
        st.caption("Las lineas punteadas negras son las conexiones propuestas.")
