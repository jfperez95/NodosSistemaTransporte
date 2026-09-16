"""
Paso 3 - Demostracion de los algoritmos de busqueda de rutas.

Muestra, sobre pares reales de la red:
  1. La misma ruta bajo los cuatro criterios de optimizacion.
  2. El efecto del perfil horario (grafo dinamico).
  3. Rutas alternativas con el algoritmo de Yen.
  4. Minimo de transbordos por BFS sobre el grafo de lineas.
  5. Benchmark Dijkstra vs A* y contraste contra networkx.

Uso:  python scripts/02_demo_rutas.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.algoritmos.benchmark import comparar_lote, contrastar_con_networkx  # noqa: E402
from src.algoritmos.bfs_transbordos import (  # noqa: E402
    camino_de_lineas,
    minimos_transbordos,
)
from src.algoritmos.dijkstra import dijkstra  # noqa: E402
from src.algoritmos.k_rutas import k_rutas_alternativas  # noqa: E402
from src.modelo.grafo import construir_grafo  # noqa: E402
from src.modelo.pesos import CondicionesRed  # noqa: E402

# Pares de prueba escogidos para cubrir casos distintos de la red.
PARES = [
    ("A01", "A21"),   # Niquia -> La Estrella: todo el eje norte-sur, sin transbordo
    ("K03", "J03"),   # Santo Domingo -> La Aurora: cable a cable, cruza la ciudad
    ("H02", "A06"),   # Villa Sierra -> Caribe: cable + tranvia + metro
    ("O01", "L01"),   # U. de Medellin -> Arvi: bus + metro + cable turistico
    ("B06", "T08"),   # San Javier -> Oriente: occidente a oriente
]


def titulo(texto: str) -> None:
    print()
    print("=" * 78)
    print(texto)
    print("=" * 78)


def main() -> int:
    G = construir_grafo()
    nombre = lambda n: G.nodes[n]["nombre"]  # noqa: E731

    titulo("1. Una misma consulta bajo los cuatro criterios")
    # Par elegido a proposito: el metro es directo y rapido pero cobra tarifa de
    # riel, mientras que caminar hasta el corredor de bus sale mas barato y mucho
    # mas lento. Es el caso donde los criterios NO coinciden.
    origen, destino = "A12", "A14"
    print(f"Consulta: {nombre(origen)} -> {nombre(destino)}\n")
    for criterio in config.CRITERIOS:
        cond = CondicionesRed(criterio=criterio, perfil_horario="pico_manana")
        ruta = dijkstra(G, origen, destino, cond)
        etiqueta = config.CRITERIOS[criterio]["etiqueta"]
        print(f"  {etiqueta:<24} {ruta.minutos_totales:6.1f} min | "
              f"${ruta.costo_total_cop:>6,} | {ruta.num_transbordos} transb. | "
              f"lineas {'>'.join(ruta.lineas_usadas)}")

    titulo("2. Grafo dinamico: la misma ruta a distintas horas")
    origen, destino = "A01", "A21"
    print(f"Consulta: {nombre(origen)} -> {nombre(destino)}\n")
    for perfil, datos in config.PERFILES_HORARIOS.items():
        cond = CondicionesRed(perfil_horario=perfil, criterio="tiempo")
        ruta = dijkstra(G, origen, destino, cond)
        print(f"  {datos['etiqueta']:<28} {ruta.minutos_totales:6.1f} min "
              f"(factor {datos['factor_tiempo']:.2f}, ocupacion "
              f"{datos['ocupacion']:.0%})")

    print("\n  Con lluvia intensa (factor_clima = 1.30) en pico tarde:")
    cond = CondicionesRed(perfil_horario="pico_tarde", criterio="tiempo",
                          factor_clima=1.30)
    print(f"    {dijkstra(G, origen, destino, cond).minutos_totales:.1f} min")

    titulo("3. Itinerario detallado")
    cond = CondicionesRed(perfil_horario="valle_manana", criterio="tiempo")
    ruta = dijkstra(G, "O01", "L01", cond)
    print(ruta.imprimir())

    titulo("4. Rutas alternativas (algoritmo de Yen)")
    origen, destino = "A09", "O08"
    print(f"Consulta: {nombre(origen)} -> {nombre(destino)}\n")
    alternativas = k_rutas_alternativas(G, origen, destino, k=3, condiciones=cond)
    for i, alt in enumerate(alternativas, 1):
        print(f"  Opcion {i}: {alt.minutos_totales:6.1f} min | "
              f"${alt.costo_total_cop:>6,} | {alt.num_transbordos} transb. | "
              f"{alt.num_estaciones} estaciones | lineas "
              f"{'>'.join(alt.lineas_usadas)}")

    titulo("5. Minimo de transbordos por BFS sobre el grafo de lineas")
    for o, d in PARES:
        cota = minimos_transbordos(G, o, d)
        camino = camino_de_lineas(G, o, d)
        real = dijkstra(G, o, d, CondicionesRed(criterio="transbordos"))
        marca = "OK" if real.num_transbordos <= (cota or 0) + 1 else "REVISAR"
        print(f"  {nombre(o):<22} -> {nombre(d):<22} BFS={cota} "
              f"({'>'.join(camino or [])}) Dijkstra={real.num_transbordos} [{marca}]")

    titulo("6. Benchmark: Dijkstra vs A*")
    resultado = comparar_lote(G, PARES, CondicionesRed(criterio="tiempo"))
    encabezado = (f"  {'origen':<8}{'destino':<8}{'Dij.exp':>9}{'A*.exp':>9}"
                  f"{'ahorro':>9}{'Dij.ms':>9}{'A*.ms':>9}{'mismo opt.':>12}")
    print(encabezado)
    print("  " + "-" * (len(encabezado) - 2))
    for f in resultado["detalle"]:
        print(f"  {f['origen']:<8}{f['destino']:<8}{f['dijkstra_expandidos']:>9}"
              f"{f['a_estrella_expandidos']:>9}{f['reduccion_expansion_%']:>8.1f}%"
              f"{f['dijkstra_ms']:>9.3f}{f['a_estrella_ms']:>9.3f}"
              f"{str(f['mismo_optimo']):>12}")
    print("\n  Resumen:")
    for clave, valor in resultado["resumen"].items():
        print(f"    {clave}: {valor}")

    titulo("7. Contraste contra networkx (validacion externa)")
    for o, d in PARES[:3]:
        c = contrastar_con_networkx(G, o, d)
        print(f"  {o}->{d}: networkx={c['minutos_networkx']:.2f} min | "
              f"propio={c['minutos_implementacion_propia']:.2f} min | "
              f"cota respetada={c['propio_no_mejora_la_cota']}")

    correcto = resultado["resumen"]["todos_coinciden_en_el_optimo"]
    print()
    print("[OK] Dijkstra y A* coinciden en el optimo en todos los pares"
          if correcto else
          "[FALLA] A* no coincide con Dijkstra: revisar la heuristica")
    return 0 if correcto else 1


if __name__ == "__main__":
    sys.exit(main())
