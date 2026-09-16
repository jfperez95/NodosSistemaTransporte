"""
Paso 5 - Exporta el mapa de la red a un HTML independiente.

Sirve para dos cosas: revisar la visualizacion sin levantar la aplicacion, y
tener una copia del mapa que se pueda abrir en la sustentacion aunque falle el
entorno de Streamlit.

Uso:  python scripts/03_exportar_mapa.py [origen] [destino]
      python scripts/03_exportar_mapa.py A01 L01
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.algoritmos.dijkstra import dijkstra  # noqa: E402
from src.modelo.grafo import construir_grafo  # noqa: E402
from src.modelo.pesos import CondicionesRed  # noqa: E402
from src.visual.mapa import mapa_de_la_red  # noqa: E402

SALIDA = RAIZ / "docs" / "mapa_red.html"


def main() -> int:
    origen = sys.argv[1] if len(sys.argv) > 1 else "A01"
    destino = sys.argv[2] if len(sys.argv) > 2 else "L01"

    G = construir_grafo()
    for nodo in (origen, destino):
        if nodo not in G:
            print(f"La estacion {nodo} no existe en la red")
            return 1

    ruta = dijkstra(G, origen, destino, CondicionesRed(criterio="tiempo"))
    mapa = mapa_de_la_red(G, ruta, origen, destino)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(str(SALIDA))

    print(f"Mapa exportado a {SALIDA}")
    print(f"Ruta {G.nodes[origen]['nombre']} -> {G.nodes[destino]['nombre']}: "
          f"{ruta.minutos_totales:.1f} min, {ruta.num_estaciones} estaciones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
