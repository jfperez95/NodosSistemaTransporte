# Calculador de Rutas Óptimas para el Metro de Medellín usando Grafos Dinámicos

Práctica entregable #2 — Teoría de Grafos
Matemáticas para la Informática Avanzada · Ingeniería de Sistemas · Séptimo semestre
**Equipo 2** · Entrega y sustentación: 30 de septiembre de 2026

Modela el Sistema Integrado de Transporte del Valle de Aburrá (Metro, Metrocable,
Tranvía y bus eléctrico) como un **grafo dirigido, ponderado y dinámico**, y
calcula rutas óptimas entre estaciones según distintos criterios.

---

## Ejecución

```bash
pip install -r requirements.txt

streamlit run app.py     # la aplicación
python -m pytest -q      # 105 pruebas
```

---

## Estado: completo

| Paso | Contenido | Estado |
|------|-----------|--------|
| 0 | Organización y estructura del repositorio | Hecho |
| 1 | Datos de la red (61 estaciones, 62 tramos) | Hecho |
| 2 | Grafo y función de peso dinámica | Hecho |
| 3 | Algoritmos: Dijkstra, A\*, BFS, Yen y benchmark | Hecho |
| 4 | Interfaz de usuario (Streamlit, 5 paneles) | Hecho |
| 5 | Visualización georreferenciada (Folium) | Hecho |
| 6 | Retos avanzados: resiliencia, predicción, optimización | Hecho |
| 7 | Pruebas y casos límite (105 pruebas) | Hecho |
| 8 | Manual de usuario y documento técnico | Hecho |
| 9 | Guion de sustentación | Hecho |

---

## Estructura

```
NodosSistemaTransporte/
├── app.py                      # interfaz Streamlit (paso 4)
├── datos/
│   ├── estaciones.csv          # 61 vértices con atributos
│   └── conexiones.csv          # 62 tramos → 124 aristas dirigidas
├── src/
│   ├── config.py               # tarifas, perfiles horarios, criterios, paleta
│   ├── modelo/
│   │   ├── entidades.py        # Estacion y Conexion
│   │   ├── carga_datos.py      # lectura estricta y validación de los CSV
│   │   ├── grafo.py            # construcción de G = (V, E) y métricas
│   │   └── pesos.py            # función de peso dinámica multicriterio
│   ├── algoritmos/
│   │   ├── espacio_estados.py  # búsqueda sobre estados (estación, línea)
│   │   ├── dijkstra.py         # implementación propia con cola de prioridad
│   │   ├── a_estrella.py       # A* con heurística Haversine admisible
│   │   ├── bfs_transbordos.py  # BFS sobre el grafo de líneas
│   │   ├── k_rutas.py          # algoritmo de Yen (rutas alternativas)
│   │   ├── evaluacion.py       # reevaluación exacta de rutas concatenadas
│   │   ├── benchmark.py        # comparación Dijkstra / A* / networkx
│   │   └── ruta.py             # resultado: Ruta y Tramo
│   ├── analisis/
│   │   ├── resiliencia.py      # puntos críticos y eventos disruptivos
│   │   ├── prediccion.py       # tiempos con intervalo de confianza
│   │   └── optimizacion.py     # brechas y nuevas conexiones
│   ├── visual/mapa.py          # mapa georreferenciado
│   └── utils/geo.py            # Haversine y cota inferior de tiempo
├── docs/
│   ├── manual_usuario.md       # entregable (1 página)
│   ├── documento_tecnico.md    # entregable (1 página)
│   └── guion_sustentacion.md   # guion de los 10 minutos
└── tests/                      # 105 pruebas
```

---

## El modelo en términos de teoría de grafos

**G = (V, E, w)**, dirigido, ponderado y multigrafo.

| Concepto | En este proyecto |
|----------|------------------|
| Vértice | Estación o parada (nombre, coordenadas, dirección, tipo, accesibilidad, servicios) |
| Arista dirigida | Tramo entre dos estaciones por una línea concreta |
| Peso w(e) | Combinación dinámica de tiempo, costo, transbordo y riesgo |
| Orden \|V\| | 61 |
| Tamaño \|E\| | 124 aristas dirigidas (62 tramos bidireccionales) |
| Grado promedio | 4.07 (máximo 8: Acevedo y San Antonio) |
| Densidad | 0.034 — **disperso**, por eso lista de adyacencia y no matriz |
| Conectividad | **Fuertemente conexo**: hay ruta entre todo par ordenado |

### Decisiones de modelado

1. **Dirigido.** Cada tramo bidireccional se expande en dos aristas opuestas, para
   poder representar un cierre que afecte un solo sentido.
2. **Multigrafo con la línea como clave.** Permite distinguir por qué servicio se
   viaja y, por tanto, contar transbordos.
3. **Las estaciones de intercambio son un solo vértice.** El costo de cambiar de
   línea no se modela duplicando nodos, sino ejecutando la búsqueda sobre el
   espacio de estados **(estación, línea)**. Es la decisión técnica central: el
   peso de una arista depende del camino por el que se llega, y un Dijkstra
   ingenuo sobre nodos no podría representarlo.

### Qué lo hace un grafo *dinámico*

El peso no está en el dataset: se calcula en cada consulta.

```
w(e) = α·tiempo(e, hora) + β·costo(e, sistema_previo)/300
     + γ·transbordo(línea_previa, e) + δ·riesgo(e, hora)
```

Seis perfiles horarios, factor de clima, sensibilidad a la congestión por modo y
tarifa integrada del SITVA. Niquía → La Estrella: **52 min** un domingo, **87 min**
en pico de la tarde, **113 min** con lluvia intensa.

---

## Algoritmos

| Algoritmo | Para qué | Por qué |
|-----------|----------|---------|
| **Dijkstra** (propio, `heapq`) | Ruta óptima bajo cualquier criterio | Todos los pesos son estrictamente positivos, que es su condición de validez. No hace falta Bellman-Ford ni Floyd-Warshall |
| **A\*** con heurística Haversine | Misma ruta, menos trabajo | La distancia en línea recta a velocidad máxima nunca sobreestima: heurística admisible y consistente |
| **BFS** sobre el grafo de líneas | Mínimo exacto de transbordos | Aristas de peso 1 ⇒ camino mínimo por niveles en O(\|V\|+\|E\|) |
| **Yen** | Rutas alternativas | La segunda mejor ruta es el mejor camino que no sea el primero |

**Optimizaciones:** cola de prioridad binaria O((|S|+|E_S|)·log|S|), *lazy
deletion*, parada temprana al extraer la meta, desempate determinista.

**Benchmark** (5 pares, criterio tiempo): A\* expande **21.5 % menos estados**
(47.2 frente a 59.8) y coincide con Dijkstra en el óptimo en los 5 pares.

**Tres validaciones cruzadas:** A\* contra Dijkstra (optimalidad), BFS contra
Dijkstra (conteo de transbordos) y networkx como referencia externa.

---

## Retos avanzados

- **Resiliencia.** Vértices de corte, centralidad de intermediación y simulación
  de eventos con recálculo automático de rutas. Cerrar **San Antonio** alarga el
  viaje promedio un **11.2 %** y deja **443 trayectos sin recorrido posible**.
- **Predicción.** Histórico sintético reproducible; el modelo estima los factores
  sin conocerlos y los recupera con **menos de 1 % de error**. La incertidumbre se
  separa en componente idiosincrática (se diluye al sumar tramos) y sistémica
  (no se diluye) — sin esa separación el intervalo saldría falsamente preciso.
- **Optimización.** Factor de rodeo para detectar brechas, y simulación de la
  mejora real. La mejor propuesta une **San Javier con la Universidad de
  Medellín**: 3.2 km bajan ese trayecto de 54 a 8 minutos y mejoran la red un
  **2.84 %**.

---

## Accesibilidad de la visualización

La paleta de modos se validó contra superficie clara: franja de luminosidad y
piso de croma correctos, separación para visión normal de 21.4 (mínimo 15) y
separación bajo deuteranopía en el suelo admisible. Por eso cada modo lleva
**además un patrón de trazo propio**, de modo que el mapa se entiende también en
blanco y negro o con daltonismo, y por eso la aplicación **fija tema claro**: una
paleta oscura sin validar sería peor que no ofrecer modo oscuro.

---

## Sobre los datos

Las líneas, la secuencia de estaciones y las coordenadas corresponden a la red
real del SITVA. Sin embargo:

* Las **coordenadas son aproximadas** (precisión de orden de 100 m); sirven para
  la heurística geográfica y el mapa, no para navegación real.
* El corredor de **bus eléctrico (línea O)** es una versión **simplificada y
  representativa** del corredor de Metroplús, no su trazado exacto.
* Tiempos, tarifas, ocupaciones y probabilidades de retraso son **parámetros de
  simulación verosímiles**, no datos oficiales de Metro de Medellín.

Las distancias de `datos/conexiones.csv` se obtuvieron aplicando la fórmula de
Haversine sobre las coordenadas de las estaciones, y los tiempos base se
derivaron de la velocidad comercial de cada modo de transporte.
