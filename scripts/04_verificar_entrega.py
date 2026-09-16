"""
Paso 10 - Verificacion previa a la entrega.

Comprueba de una sola pasada que el proyecto esta completo y funcionando:
dependencias, datos, grafo, algoritmos, retos avanzados, documentacion y pruebas.
Pensado para ejecutarlo en el portatil con que se va a sustentar, antes del 30 de
septiembre.

Uso:  python scripts/04_verificar_entrega.py
Devuelve codigo 0 si todo esta listo, 1 si falta algo.
"""

import importlib
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DEPENDENCIAS = ["networkx", "pandas", "numpy", "streamlit", "folium", "streamlit_folium"]

ENTREGABLES = [
    ("README.md", "Descripcion del proyecto"),
    ("requirements.txt", "Dependencias"),
    ("app.py", "Aplicacion"),
    ("datos/estaciones.csv", "Vertices del grafo"),
    ("datos/conexiones.csv", "Aristas del grafo"),
    ("docs/manual_usuario.md", "Manual de usuario (1 pagina)"),
    ("docs/documento_tecnico.md", "Documento tecnico (1 pagina)"),
    ("docs/guion_sustentacion.md", "Guion de la sustentacion"),
]

fallos = []


def verificar(descripcion: str, condicion: bool, detalle: str = "") -> None:
    marca = "OK  " if condicion else "FALLA"
    print(f"  [{marca}] {descripcion}" + (f"  -> {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


def titulo(texto: str) -> None:
    print()
    print(texto)
    print("-" * len(texto))


def main() -> int:
    titulo("1. Dependencias")
    for paquete in DEPENDENCIAS:
        try:
            importlib.import_module(paquete)
            verificar(paquete, True)
        except ImportError:
            verificar(paquete, False, "pip install -r requirements.txt")

    titulo("2. Entregables")
    for ruta, descripcion in ENTREGABLES:
        archivo = RAIZ / ruta
        verificar(f"{descripcion}: {ruta}", archivo.exists())

    titulo("3. El grafo")
    from src.modelo.grafo import construir_grafo, resumen_grafo

    G = construir_grafo()
    resumen = resumen_grafo(G)
    verificar("Estaciones cargadas", resumen["orden_|V|"] > 50, f"{resumen['orden_|V|']} vertices")
    verificar("Conexiones cargadas", resumen["tamano_|E|"] > 100, f"{resumen['tamano_|E|']} aristas")
    verificar("Fuertemente conexo", resumen["fuertemente_conexo"])

    titulo("4. Algoritmos")
    from src.algoritmos.a_estrella import a_estrella
    from src.algoritmos.bfs_transbordos import minimos_transbordos
    from src.algoritmos.dijkstra import dijkstra
    from src.algoritmos.k_rutas import k_rutas_alternativas
    from src.modelo.pesos import CondicionesRed

    cond = CondicionesRed(criterio="tiempo")
    ruta = dijkstra(G, "A01", "L01", cond)
    verificar("Dijkstra encuentra ruta", ruta.existe,
              f"{ruta.minutos_totales:.1f} min, {ruta.num_transbordos} transbordos")

    ruta_a = a_estrella(G, "A01", "L01", cond)
    verificar("A* coincide con Dijkstra en el optimo",
              abs(ruta_a.peso_total - ruta.peso_total) < 1e-9,
              f"{ruta_a.nodos_expandidos} vs {ruta.nodos_expandidos} estados")

    cota = minimos_transbordos(G, "A01", "L01")
    transb = dijkstra(G, "A01", "L01", CondicionesRed(criterio="transbordos"))
    verificar("BFS coincide con Dijkstra en transbordos",
              cota == transb.num_transbordos, f"ambos: {cota}")

    alternativas = k_rutas_alternativas(G, "A09", "O08", k=3, condiciones=cond)
    verificar("Yen devuelve rutas alternativas", len(alternativas) >= 2,
              f"{len(alternativas)} opciones")

    titulo("5. Retos avanzados")
    from src.analisis.optimizacion import proponer_conexiones
    from src.analisis.prediccion import ajustar_modelo, generar_historico, predecir_ruta
    from src.analisis.resiliencia import impacto_de_cierre

    impacto = impacto_de_cierre(G, ["A11"], condiciones=cond)
    verificar("Resiliencia: el cierre de San Antonio se mide",
              impacto["incremento_%"] > 0,
              f"+{impacto['incremento_%']}% y "
              f"{impacto['pares_incomunicados_adicionales']} trayectos perdidos")

    modelo = ajustar_modelo(generar_historico(G, 3000))
    p = predecir_ruta(dijkstra(G, "A01", "A21", cond), modelo)
    verificar("Prediccion: intervalo de confianza util",
              p is not None and p["minutos_max"] > p["minutos_min"],
              f"{p['minutos_esperados']:.0f} min, IC90 "
              f"[{p['minutos_min']:.0f}, {p['minutos_max']:.0f}]")

    propuestas = proponer_conexiones(G, cond, candidatos=5, devolver=2)
    verificar("Optimizacion: hay propuestas que mejoran la red",
              bool(propuestas),
              f"mejor: {propuestas[0]['mejora_red_%']}%" if propuestas else "ninguna")

    titulo("6. Visualizacion")
    from src.visual.mapa import mapa_de_la_red

    mapa = mapa_de_la_red(G, ruta, "A01", "L01")
    html = mapa.get_root().render()
    verificar("El mapa se genera", "polyline" in html.lower(),
              f"{len(html) // 1024} KB")

    titulo("7. Pruebas automatizadas")
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    ultima = [l for l in resultado.stdout.strip().splitlines() if l.strip()][-1:]
    verificar("Suite completa en verde", resultado.returncode == 0,
              ultima[0] if ultima else "")

    titulo("Resultado")
    if fallos:
        print(f"  Faltan {len(fallos)} elemento(s):")
        for f in fallos:
            print(f"    - {f}")
        return 1

    print("  Todo listo para la entrega del 30 de septiembre de 2026.")
    print("  Recuerda: convertir los .md de docs/ a PDF y subir a Teams.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
