# Guion de sustentación — 10 minutos

**Equipo 2 · Calculador de Rutas Óptimas para el Metro de Medellín**
30 de septiembre de 2026

> La rúbrica premia **estructura clara, dominio del tema y participación
> equitativa**. Cada integrante expone su bloque completo; nadie lee diapositivas.
> Ensayar cronometrado al menos dos veces.

---

## Reparto y tiempos

| # | Bloque | Minutos | Integrante |
|---|---|---|---|
| 1 | El problema y el modelo de grafo | 2:00 | |
| 2 | El grafo dinámico y los criterios | 1:30 | |
| 3 | Los algoritmos y su justificación | 2:30 | |
| 4 | Demostración en vivo | 2:30 | |
| 5 | Retos avanzados y cierre | 1:30 | |

Dejar los últimos segundos de cada bloque para pasar el turno explícitamente:
*"...y con eso paso a [nombre], que explica los algoritmos."*

---

## Bloque 1 — El problema y el modelo (2:00)

- **Abrir con la pregunta, no con el código.** *"¿Cuál es la mejor forma de ir de
  Niquía a Arví? Depende de qué signifique 'mejor', y de a qué hora se pregunte."*
- El SITVA como **G = (V, E, w)**: 61 estaciones, 124 aristas dirigidas,
  fuertemente conexo.
- **Tres decisiones y su porqué** (esto es el criterio 1 de la rúbrica, 20 pts):
  1. **Dirigido**, para poder cerrar un solo sentido.
  2. **Multigrafo con la línea como clave**, para poder contar transbordos.
  3. **Las estaciones de intercambio son un solo vértice**; el transbordo se
     modela en el **espacio de estados (estación, línea)**, no duplicando nodos.
- Mencionar que es **disperso** (3.3 % de la matriz de adyacencia): por eso listas
  de adyacencia y no matriz.

## Bloque 2 — El grafo dinámico (1:30)

- El peso **no está guardado**: se evalúa en cada consulta.
  `w = α·tiempo(hora) + β·costo + γ·transbordo + δ·riesgo`
- Los coeficientes los fija el criterio del usuario; la hora y el clima fijan el
  tiempo. **Ese es el "dinámico" del título.**
- Cifra que se recuerda: *Niquía → La Estrella son **52 minutos un domingo, 87 en
  pico de la tarde y 113 con lluvia intensa**.*
- La tarifa integrada: se paga al entrar, riel→riel gratis, riel↔bus con recargo.

## Bloque 3 — Los algoritmos (2:30)

- **Dijkstra, y por qué Dijkstra**: todos los pesos son estrictamente positivos,
  que es exactamente su condición de validez. No hace falta Bellman-Ford (existe
  para pesos negativos) ni Floyd-Warshall (todos contra todos, O(|V|³)).
- **Implementación propia**, no `networkx.shortest_path`, porque el peso depende
  del estado con que se llega al nodo. Cola de prioridad binaria:
  O((|S|+|E_S|)·log|S|). Parada temprana, *lazy deletion*, desempate determinista.
- **A\***: misma ruta, guiada por la distancia geográfica. Heurística admisible y
  consistente ⇒ conserva la optimalidad. **21.5 % menos estados expandidos.**
- **BFS** sobre el grafo de líneas para el mínimo exacto de transbordos.
- **Yen** para rutas alternativas.
- **El argumento fuerte:** *"No solo lo implementamos, lo verificamos de tres
  formas independientes: A\* coincide con Dijkstra en el óptimo, BFS coincide con
  Dijkstra en los transbordos, y networkx sirve de referencia externa. Son 105
  pruebas automatizadas."*

## Bloque 4 — Demostración en vivo (2:30)

Guion exacto, sin improvisar:

1. **Niquía → Arví**, ruta más rápida, pico de la mañana. Señalar el mapa: los
   colores dicen en qué modo va cada tramo.
2. Cambiar a **ruta más económica** en un par donde difiera (Alpujarra →
   Industriales): *"5 minutos por 3.300 pesos, o 22 minutos por 3.000."*
3. Mover el **momento del viaje** y mostrar el gráfico del día.
4. Activar el filtro **evitar Metrocable** para ese mismo viaje a Arví: la
   aplicación dice que no hay ruta, con un mensaje claro.
5. **Cerrar San Antonio** en *Simular interrupciones* → pestaña Resiliencia:
   *"+11.2 % en el viaje promedio y 443 trayectos que dejan de existir."*

> **Plan B:** si falla el entorno, abrir `docs/mapa_red.html` (el mapa exportado).
> Tenerlo probado en el portátil que se va a usar, no en otro.

## Bloque 5 — Retos avanzados y cierre (1:30)

- **Resiliencia**: vértices de corte, desvío automático, y el detalle honesto —
  medir el promedio solo sobre los pares que sobreviven, para no caer en sesgo de
  supervivencia.
- **Predicción**: intervalos de confianza. El modelo no recibe los factores con
  que se simularon los datos: los estima y los recupera con menos de 1 % de error.
- **Optimización**: San Javier ↔ Universidad de Medellín, 3.2 km que bajan ese
  trayecto de 54 a 8 minutos y mejoran toda la red un 2.84 %.
- **Cerrar declarando las limitaciones** antes de que las pregunten: coordenadas
  aproximadas, corredor de bus simplificado, tiempos y tarifas de simulación.

---

## Preguntas probables y respuestas preparadas

**¿Por qué Dijkstra y no otro algoritmo?**
Porque `w(e) > 0` para toda arista, que es su condición de validez, y solo
necesitamos un origen por consulta. Bellman-Ford resuelve pesos negativos, que no
tenemos; Floyd-Warshall resuelve todos contra todos en O(|V|³), que no
necesitamos. Además implementamos A\* y medimos que da el mismo óptimo.

**¿Cuál es la complejidad?**
O((|S| + |E_S|)·log|S|) con montículo binario, donde S es el espacio de estados
(estación, línea), de tamaño ≈ 1.2·|V|.

**¿Cómo manejan los transbordos?**
No con nodos duplicados: la búsqueda corre sobre estados (estación, línea), así el
peso de una arista puede depender de la línea con la que se llegó. Un transbordo
a pie cuenta **una sola vez**, y lo verificamos comparando contra BFS.

**¿Cómo saben que la ruta es correcta?**
Tres verificaciones cruzadas independientes (A\*, BFS, networkx) y 105 pruebas,
incluidos los casos límite: origen igual a destino, estación inexistente, red
cortada y filtros que dejan el viaje sin solución.

**¿Los datos son reales?**
Las líneas, estaciones y coordenadas siguen la red real, con precisión de ~100 m.
Los tiempos, tarifas y ocupaciones son parámetros de simulación verosímiles, y el
corredor de bus es una simplificación de Metroplús. Está declarado en el
documento técnico.

**¿Por qué el intervalo de confianza es tan ancho?**
Porque separamos la incertidumbre en dos: la de cada tramo, que se diluye al
sumar, y la sistémica compartida por todo el viaje, que no. Si solo usáramos la
primera, el intervalo saldría de ±1 minuto sobre 80 — falsamente preciso.

---

## Lista de verificación el día de la entrega

- [ ] `pip install -r requirements.txt` probado en el portátil de la exposición
- [ ] `python -m pytest -q` en verde (105 pruebas)
- [ ] Saber explicar de viva voz cómo se obtuvieron distancias y tiempos
- [ ] `streamlit run app.py` abre sin errores y con internet disponible (el mapa
      base descarga los tiles de OpenStreetMap)
- [ ] `docs/mapa_red.html` exportado, como plan B
- [ ] Manual de usuario y documento técnico convertidos a PDF
- [ ] Código fuente comprimido y subido a Teams → Assignments
- [ ] Ensayo cronometrado completo, con el reparto de arriba
