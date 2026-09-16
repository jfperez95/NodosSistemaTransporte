# Manual de usuario

**Calculador de Rutas Óptimas para el Metro de Medellín**
Práctica entregable #2 — Teoría de Grafos · Equipo 2

---

## 1. Cómo iniciar la aplicación

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abre en el navegador en `http://localhost:8501`. La primera consulta tarda un
par de segundos mientras se construye el grafo; las siguientes son inmediatas.

---

## 2. Planear un viaje

Todo se controla desde la **barra lateral izquierda**:

| Control | Qué hace |
|---|---|
| **Origen** / **Destino** | Estación de salida y de llegada. La lista está en orden alfabético e indica el modo y las líneas de cada estación. |
| **Optimizar por** | *Más rápida*, *más económica*, *menos transbordos* o *más confiable*. Cambia qué ruta se considera la mejor. |
| **Momento del viaje** | Franja horaria. El sistema recalcula los tiempos: en hora pico el mismo viaje tarda más. |
| **Clima** | Despejado, lluvia ligera o lluvia intensa. La lluvia alarga todos los trayectos. |

El resultado aparece de inmediato en la pestaña **Ruta**:

- **Cuatro indicadores arriba**: tiempo, costo en pesos, número de transbordos y
  número de estaciones.
- **Mapa** con la red completa y tu ruta resaltada. Cada tramo conserva el color
  de su modo de transporte, así que ves de un vistazo dónde vas en metro, en
  cable, en tranvía o en bus. Haz clic en cualquier estación para ver su
  dirección, su nivel de accesibilidad y sus servicios.
- **Itinerario** a la derecha, tramo por tramo, marcando dónde hay transbordo.
- **Rutas alternativas**: otras opciones ordenadas de mejor a peor.
- **Gráfico del viaje a lo largo del día**: cuánto tarda el mismo trayecto en
  cada franja horaria.

> **Leyenda.** Al final de la barra lateral está la leyenda de modos. Cada modo
> tiene su propio color *y* su propio patrón de línea, de modo que el mapa se
> entiende también impreso en blanco y negro o con daltonismo.

---

## 3. Filtros de preferencia

Dentro de **Filtros de preferencia** (barra lateral):

- **Evitar estos modos** — por ejemplo, excluir el Metrocable si el usuario tiene
  vértigo, o el bus si prefiere no ir en vía compartida. La ruta se recalcula
  usando solo los modos restantes.
- **Rutas alternativas a mostrar** — de 1 a 5 opciones.

Si los filtros dejan el viaje sin solución, la aplicación lo dice claramente y
sugiere qué quitar. No se queda en blanco ni muestra un error técnico.

---

## 4. Simular una interrupción

En **Simular interrupciones** puedes **cerrar estaciones** o **suspender líneas
completas**. A partir de ese momento *todos* los cálculos usan la red
interrumpida, y un aviso amarillo te recuerda que la simulación está activa.

En la pestaña **Resiliencia** verás:

- Cuánto se alarga el viaje promedio de la ciudad.
- Cuántos trayectos dejan de existir.
- Si tu viaje concreto se ve afectado y, en ese caso, **el desvío propuesto en el
  mapa** con los minutos extra que cuesta. Si no hay desvío posible, también te
  lo dice.

---

## 5. Las otras pestañas

- **La red** — el sistema visto como grafo: número de estaciones y conexiones,
  grado promedio y densidad. Incluye un botón para ejecutar el *benchmark* que
  compara Dijkstra con A\*.
- **Predicción** — en vez de un tiempo exacto, un rango: *"59 minutos esperados,
  entre 49 y 68 nueve de cada diez veces"*. Se ajusta por día de la semana, clima
  y eventos especiales (un partido, una marcha).
- **Optimización** — qué conexiones nuevas convendría construir y cuánto
  mejoraría la red cada una. Las propuestas aparecen punteadas en el mapa.

---

## 6. Preguntas frecuentes

**¿Por qué solo me muestra una ruta alternativa?**
Porque en ese corredor la red no tiene malla: cualquier desvío repite casi las
mismas estaciones. La aplicación lo indica en vez de inventar opciones falsas.

**¿Por qué la ruta más económica tarda tanto?**
Porque cambia de sistema tarifario. En el SITVA los transbordos dentro del riel
son gratuitos, pero pasar de bus a metro cobra un recargo: a veces evitarlo sale
barato en pesos y caro en minutos.

**¿Los tiempos y tarifas son oficiales?**
No. Las líneas, estaciones y coordenadas siguen la red real, pero los tiempos,
tarifas y niveles de ocupación son parámetros de simulación verosímiles.
