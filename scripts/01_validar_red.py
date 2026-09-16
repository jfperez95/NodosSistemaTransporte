"""
Paso 1-2 - Verificacion del dataset y del grafo construido.

Ejecuta las validaciones de carga, imprime las metricas del grafo en el
vocabulario de la teoria de grafos y comprueba la propiedad que hace viable el
calculador de rutas: que el grafo sea FUERTEMENTE CONEXO.

Uso:  python scripts/01_validar_red.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.modelo.carga_datos import cargar_conexiones, cargar_estaciones  # noqa: E402
from src.modelo.grafo import (  # noqa: E402
    construir_grafo,
    lista_adyacencia,
    matriz_adyacencia,
    resumen_grafo,
)


def titulo(texto: str) -> None:
    print()
    print(texto)
    print("-" * len(texto))


def main() -> int:
    titulo("1. Carga y validacion de los datos")
    estaciones = cargar_estaciones()
    conexiones = cargar_conexiones(estaciones)
    print(f"Estaciones cargadas: {len(estaciones)}")
    print(f"Conexiones cargadas: {len(conexiones)}")

    por_modo = {}
    for est in estaciones.values():
        por_modo[est.modo] = por_modo.get(est.modo, 0) + 1
    print("Estaciones por modo:", dict(sorted(por_modo.items())))

    titulo("2. Construccion del grafo G = (V, E, w)")
    G = construir_grafo(estaciones, conexiones)
    resumen = resumen_grafo(G)
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")

    titulo("3. Estaciones de intercambio (grado alto / varias lineas)")
    intercambios = [
        (d["nombre"], d["lineas"], G.degree(n))
        for n, d in G.nodes(data=True)
        if d["es_intercambio"]
    ]
    for nombre, lineas, grado in sorted(intercambios, key=lambda x: -x[2]):
        print(f"  {nombre:<24} lineas={','.join(lineas):<10} grado={grado}")

    titulo("4. Representaciones clasicas del grafo")
    nodos, A = matriz_adyacencia(G)
    unos = sum(sum(fila) for fila in A)
    celdas = len(nodos) ** 2
    print(f"  Matriz de adyacencia: {len(nodos)}x{len(nodos)} = {celdas} celdas, "
          f"{unos} en 1 ({100 * unos / celdas:.2f}% de ocupacion)")
    print("  -> el grafo es DISPERSO: se usa lista de adyacencia, no matriz")

    adyacencia = lista_adyacencia(G)
    ejemplo = "A11"
    print(f"  Lista de adyacencia de {ejemplo} ({G.nodes[ejemplo]['nombre']}):")
    for vecino, linea in adyacencia[ejemplo]:
        print(f"      -> {G.nodes[vecino]['nombre']} (linea {linea})")

    titulo("5. Verificacion final")
    ok = True
    if resumen["fuertemente_conexo"]:
        print("  [OK] El grafo es fuertemente conexo: existe ruta entre todo par "
              "ordenado de estaciones")
    else:
        ok = False
        print(f"  [FALLA] El grafo tiene {resumen['componentes_fuertes']} "
              "componentes fuertemente conexas")
        for i, comp in enumerate(
            sorted(__import__("networkx").strongly_connected_components(G), key=len),
            start=1,
        ):
            nombres = sorted(G.nodes[n]["nombre"] for n in comp)
            print(f"      Componente {i} ({len(comp)}): {', '.join(nombres[:8])}")

    aislados = [n for n in G.nodes if G.degree(n) == 0]
    if aislados:
        ok = False
        print(f"  [FALLA] Estaciones aisladas: {aislados}")
    else:
        print("  [OK] No hay estaciones aisladas (grado minimo >= 1)")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
