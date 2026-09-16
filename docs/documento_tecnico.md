# Documento técnico

**Calculador de Rutas Óptimas para el Metro de Medellín usando Grafos Dinámicos**
Práctica entregable #2 — Teoría de Grafos · Equipo 2

---

## 1. Modelado del problema

El SITVA se modela como un **grafo dirigido, ponderado y múltiple**

$$G = (V,\ E,\ w), \qquad w: E \rightarrow \mathbb{R}^{+}$$

- **V** (|V| = 61): estaciones y paradas, con atributos de nombre, coordenadas,
  dirección, tipo, accesibilidad y servicios.
- **E** (|E| = 124): tramos dirigidos entre estaciones. Los 62 tramos
  bidireccionales del dataset se expanden en dos aristas opuestas cada uno.
- **w**: función de peso dinámica (sección 3).

**Métricas del grafo.** Grado promedio 4.07 (máximo 8: Acevedo y San Antonio),
densidad 0.034 y **fuertemente conexo**: existe camino dirigido entre todo par
ordenado de estaciones, de modo que el calculador nunca falla por ausencia de
recorrido. Solo el 3.3 % de la matriz de adyacencia contiene un 1, es decir, el
grafo es **disperso** y se representa con **listas de adyacencia**: la matriz
ocuparía |V|² = 3 721 celdas para almacenar 124 datos.

**Tres decisiones de modelado y su porqué:**

1. **Dirigido.** Aunque hoy los tramos son simétricos, la dirección permite
   representar cierres o demoras que afectan un solo sentido.
2. **Multigrafo con la línea como clave de arista.** Dos estaciones pueden estar
   unidas por más de un servicio, y el algoritmo necesita saber *por cuál línea*
   viaja para poder contar transbordos.
3. **Las estaciones de intercambio son un solo vértice.** El costo de cambiar de
   línea no se modela duplicando nodos, sino ejecutando la búsqueda sobre el
   **espacio de estados (estación, línea)**.

Esta tercera decisión es la central del proyecto. El peso de una arista depende
de *cómo se llega* al nodo: tomar San Antonio → Cisneros cuesta 2 minutos si el
pasajero ya venía en la línea B, y 2 + 4 minutos si venía en la A y debe cambiar
de andén. Un Dijkstra clásico sobre nodos no puede representarlo. El grafo de
estados es a lo sumo |L| veces mayor, pero como cada estación sirve a 1–3 líneas,
en la práctica |S| ≈ 1.2 |V|: el costo es despreciable y el conteo es exacto.

---

## 2. Qué lo hace un grafo *dinámico*

El peso no está almacenado: se evalúa en cada consulta.

$$w(e) = \alpha\,t(e,h) \;+\; \beta\,\frac{c(e,s)}{300} \;+\; \gamma\,\tau(\ell,e) \;+\; \delta\,r(e,h)$$

donde *t* es el tiempo bajo la franja horaria *h*, *c* el costo dado el sistema
tarifario previo *s*, *τ* la penalización por cambiar desde la línea *ℓ*, y *r* el
riesgo de retraso. Los coeficientes (α, β, γ, δ) los fija el **criterio** elegido
por el usuario: más rápida, más económica, menos transbordos o más confiable.

Componentes dinámicos: seis **perfiles horarios** que multiplican el tiempo base y
fijan la ocupación; un **factor de clima**; una **sensibilidad a la congestión por
modo** (el bus se degrada tres veces más que el metro a igual ocupación); y la
**tarifa integrada** del SITVA (se paga al entrar, riel→riel es gratis, riel↔bus
cobra recargo, la Línea L a Arví tiene tarifa turística aparte).

Efecto medible: Niquía → La Estrella pasa de **52 min** un domingo a **87 min** en
pico de la tarde, y a **113 min** con lluvia intensa.

> **Propiedad clave: w(e) > 0 para toda arista.** Todos los términos son no
> negativos y el de tiempo tiene cota inferior estrictamente positiva. Esta es
> exactamente la condición de validez de Dijkstra.

---

## 3. Algoritmos implementados

| Algoritmo | Papel | Justificación |
|---|---|---|
| **Dijkstra** (implementación propia) | Ruta óptima bajo cualquier criterio | Todos los pesos son positivos. No se necesita **Bellman-Ford** (que existe para pesos negativos) ni se justifica **Floyd-Warshall** (todos contra todos, O(\|V\|³)) cuando hay un solo origen |
| **A\*** con heurística Haversine | La misma ruta, con menos exploración | h(n) = distancia en línea recta ÷ velocidad máxima. Nunca sobreestima ⇒ **admisible**; cumple la desigualdad triangular ⇒ **consistente**. Por tanto A\* conserva la optimalidad |
| **BFS** sobre el grafo de líneas | Mínimo exacto de transbordos | Si toda arista vale 1, el camino mínimo se obtiene por niveles con una cola FIFO en O(\|V\|+\|E\|), sin el factor logarítmico |
| **Yen** (k caminos más cortos) | Rutas alternativas | La segunda mejor ruta es el mejor camino que *no* sea el primero; se obtiene reutilizando Dijkstra con aristas y nodos prohibidos |

**Optimizaciones aplicadas a Dijkstra.** Cola de prioridad binaria (`heapq`):
**O((|S|+|E_S|)·log|S|)** frente a O(|S|²) de la versión con búsqueda lineal del
mínimo. *Lazy deletion* en lugar de actualizar prioridades dentro del montículo.
**Parada temprana** al extraer el estado meta —en ese momento su distancia ya es
definitiva—, no al relajarlo. Desempate determinista por contador.

**Pruebas de eficiencia** (5 pares origen–destino, criterio tiempo):

| | Dijkstra | A\* |
|---|---|---|
| Estados expandidos (promedio) | 59.8 | **47.2** (−21.5 %) |
| Milisegundos por consulta | 1.045 | **0.897** |
| Peso óptimo alcanzado | — | **idéntico en los 5 pares** |

**Tres validaciones cruzadas** garantizan la corrección: A\* coincide con Dijkstra
en el peso óptimo (si difiriera, la heurística no sería admisible); BFS coincide
con Dijkstra en el número de transbordos (verifica el conteo del modelo); y
`networkx` sirve de referencia externa sobre el grafo simplificado.

---

## 4. Retos avanzados

**Resiliencia.** Cada estación se cierra y se recalcula la red. Se reportan los
**vértices de corte** —aquellos cuya eliminación aumenta el número de componentes
fuertemente conexas— junto con la centralidad de intermediación. Cerrar **San
Antonio** alarga el viaje promedio un **11.2 %** y deja **443 trayectos sin
recorrido posible**, partiendo la red en 3 componentes. El sistema propone
automáticamente el desvío, o declara que no existe.

> Detalle metodológico: el promedio se mide **solo sobre los pares que sobreviven
> al cierre**. Promediarlo sobre todos los pares originales produce sesgo de
> supervivencia —al desaparecer los trayectos largos, que son justo los que el
> cierre rompe, el promedio baja y un cierre grave parece una mejora.

**Predicción con intervalos de confianza.** Sobre un histórico sintético
reproducible se ajusta un modelo multiplicativo en escala logarítmica por
*backfitting*. El modelo **no recibe** los factores con que se simularon los datos:
los estima, y los recupera con **menos de 1 % de error** (R² = 0.46).

La incertidumbre se descompone en dos componentes, y separarlos fue necesario:
sumar veinte tramos independientes encoge la dispersión relativa por √n y produce
un intervalo falsamente preciso de ±1 minuto sobre 80. El modelo estima por
separado la varianza **idiosincrática** de cada tramo (dentro de una misma
jornada) y la **sistémica** compartida por todo el viaje (entre jornadas: el día
en que el sistema entero va lento). El ajuste recupera σ_sistémica = 0.097 frente
al 0.10 real. En Niquía → La Estrella el componente sistémico aporta el 98 % de la
varianza y el intervalo al 90 % queda en **[49, 68] minutos** sobre 59 esperados.

**Optimización de la red.** Se busca el **factor de rodeo** = tiempo real ÷ tiempo
en línea recta. Cada candidata se construye en el grafo y se mide la mejora real.
La mejor propuesta une **San Javier con la Universidad de Medellín**: 3.2 km de
vía nueva bajan ese trayecto de 54 a 8 minutos y mejoran el tiempo promedio de
toda la red un **2.84 %**.

---

## 5. Limitaciones declaradas

Las líneas, estaciones y coordenadas siguen la red real del SITVA, con precisión
de orden de 100 m. El corredor de bus eléctrico es una versión simplificada y
representativa de Metroplús. Tiempos, tarifas, ocupaciones y probabilidades de
retraso son **parámetros de simulación verosímiles**, no datos oficiales de Metro
de Medellín. El modelo de predicción supone retrasos independientes entre tramos;
un incidente en cadena los correlacionaría y el intervalo real sería más ancho.

## 6. Referencias

- Rosen, K. *Discrete Mathematics and Its Applications*, cap. 10 (Graphs).
- Dijkstra, E. W. (1959). *A note on two problems in connexion with graphs.*
- Hart, Nilsson & Raphael (1968). *A formal basis for the heuristic determination
  of minimum cost paths* (A\*).
- Yen, J. Y. (1971). *Finding the k shortest loopless paths in a network.*
- Material del curso: Tema 02 — Teoría de Grafos.
