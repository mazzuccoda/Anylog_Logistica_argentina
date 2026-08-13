#!/usr/bin/env python3
"""Arma Resumen_cuentas.xlsx a partir de la auditoria de red del modelo (ADR-064/071).

Uso:
    python3 armar_resumen_cuentas.py <carpeta_resultados> <plantilla.xlsx> <salida.xlsx>

<carpeta_resultados> es la carpeta descomprimida del zip de salida del modelo
(debe tener costos_eventos.csv y, si existe, asignaciones_elegidas.csv).
<plantilla.xlsx> es el Resumen_cuentas.xlsx con la hoja "Resumen (a_completar)"
vacia (fila 1 encabezado, filas 2-101 material/cuenta/unidad ya armadas).

Compatibilidad: si costos_eventos.csv todavia no trae la columna "material"
(corridas anteriores a ADR-071), cae a "producto" y solo completa 3 de las
5 filas de material por cuenta (ACEITE/CASCARA/JUGO en vez de AEL/CDL/JCCL/
JCL/PCL) -- vuelve a andar completo apenas se recorra con el modelo parchado.
"""
import csv
import sys
from collections import defaultdict

import openpyxl

BUCKETS = [(0, 31), (31, 59), (59, 90), (90, 120), (120, 151), (151, 181),
           (181, 212), (212, 243), (243, 273), (273, 304), (304, 334), (334, 999)]

# Cuenta (Resumen) <- categoria (costos_eventos.csv). FLETE DEPOSITO = FLETE_PRODUCTO,
# confirmado por el usuario. OPORTUNIDAD_FRIO/PENALIDAD_SOBRECARGA no tienen cuenta en
# el Resumen (son ECONOMICO, no CAJA) y se excluyen a proposito.
CATEGORIA_A_CUENTA = {
    "IN_DEPOSITO": "ALMACENAJE (IN)",
    "ALMACENAMIENTO": "ALMACENAJE (STORAGE)",
    "OUT_DEPOSITO": "ALMACENAJE (OUT)",
    "ROUND_TRIP": "ROUND TRIP",
    "FLETE_PRODUCTO": "FLETE DEPOSITO",
    "CONSOLIDACION": "CONSOLIDADO",
    "COSTO_TERMINAL": "TERMINAL",
    "CROSS_DOCK": "CROSS DOCKING",
    "THC": "GASTOS THC",
    "DESPACHANTE": "DESPACHANTE",
}

# cantidad ya viene en toneladas solo para estas 3 categorias.
CANTIDAD_ES_TN = {"IN_DEPOSITO", "ALMACENAMIENTO", "OUT_DEPOSITO"}

# El resto se completa con un join contra asignaciones_elegidas.csv, PERO solo funciona
# para las categorias por contenedor: cada evento ya trae id_asignacion (verificado contra
# el zip de ejemplo: CONSOLIDACION/COSTO_TERMINAL/CROSS_DOCK/DESPACHANTE/ROUND_TRIP/THC
# tienen id_asignacion siempre poblado). FLETE_PRODUCTO NO entra aca: sus cargos se
# registran contra el pedido, no contra un contenedor/asignacion (id_asignacion vacio
# siempre), asi que "FLETE DEPOSITO" queda sin Tn hasta que se resuelva ese join aparte.
CATEGORIAS_TN_POR_JOIN = {
    "CONSOLIDACION", "COSTO_TERMINAL", "CROSS_DOCK", "DESPACHANTE", "ROUND_TRIP", "THC",
}


def bucket_idx(dia_campania):
    dia = float(dia_campania)
    for i, (lo, hi) in enumerate(BUCKETS):
        if dia <= hi:
            return i
    return len(BUCKETS) - 1


def cargar_tn_por_contenedor_por_asignacion(ruta_asignaciones):
    """id_asignacion -> toneladas promedio por contenedor de esa asignacion.

    toneladas_despachadas es el total de la asignacion, no de un contenedor puntual;
    dividir por contenedores_creados evita contar el total de la asignacion una vez por
    cada evento de costo (THC/TERMINAL/DESPACHANTE/... se cobran por contenedor, asi que
    una asignacion de N contenedores genera N eventos en la misma cuenta).
    """
    tn = {}
    try:
        with open(ruta_asignaciones, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                contenedores = int(float(fila["contenedores_creados"]))
                if contenedores <= 0:
                    continue
                tn[fila["id_asignacion"]] = float(fila["toneladas_despachadas"]) / contenedores
    except FileNotFoundError:
        print(f"AVISO: no encontre {ruta_asignaciones}; Tn de las cuentas por contenedor "
              "(ROUND TRIP, CONSOLIDADO, TERMINAL, CROSS DOCKING, GASTOS THC, DESPACHANTE) "
              "queda en 0.", file=sys.stderr)
    return tn


def armar(carpeta, plantilla, salida):
    ruta_costos = f"{carpeta}/costos_eventos.csv"
    ruta_asignaciones = f"{carpeta}/asignaciones_elegidas.csv"

    tn_por_contenedor = cargar_tn_por_contenedor_por_asignacion(ruta_asignaciones)

    usd = defaultdict(lambda: [0.0] * 12)
    tn = defaultdict(lambda: [0.0] * 12)
    materiales_vistos = set()
    usando_producto_como_material = False
    flete_sin_tn = 0.0
    # Nunca se descarta plata en silencio: todo cargo mapeable a una Cuenta pero sin
    # material resuelto se acumula aca en vez de desaparecer del total.
    usd_sin_material = defaultdict(float)

    with open(ruta_costos, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        tiene_material = "material" in (lector.fieldnames or [])
        usando_producto_como_material = not tiene_material

        for fila in lector:
            categoria = fila["categoria"]
            cuenta = CATEGORIA_A_CUENTA.get(categoria)
            if cuenta is None:
                continue

            material = (fila["material"] if tiene_material else fila["producto"]).strip()
            if not material:
                usd_sin_material[cuenta] += float(fila["importe_usd"])
                continue
            materiales_vistos.add(material)

            b = bucket_idx(fila["dia_campania"])
            clave = (material, cuenta)

            usd[clave][b] += float(fila["importe_usd"])

            if categoria in CANTIDAD_ES_TN:
                tn[clave][b] += float(fila["cantidad"])
            elif categoria in CATEGORIAS_TN_POR_JOIN:
                id_asig = fila["id_asignacion"]
                if id_asig:
                    tn[clave][b] += tn_por_contenedor.get(id_asig, 0.0)
            elif categoria == "FLETE_PRODUCTO":
                # id_asignacion siempre vacio en estos cargos (se registran contra el
                # pedido, no contra un contenedor): no hay join confiable todavia.
                flete_sin_tn += float(fila["importe_usd"])

    wb = openpyxl.load_workbook(plantilla)
    ws = wb["Resumen (a_completar)"]

    filas_sin_dato = []
    for fila_idx in range(2, ws.max_row + 1):
        material = ws.cell(row=fila_idx, column=1).value
        cuenta = ws.cell(row=fila_idx, column=2).value
        unidad = ws.cell(row=fila_idx, column=3).value
        if material is None or cuenta is None:
            continue

        clave = (material, cuenta)
        valores = usd[clave] if unidad == "USD" else tn[clave]

        if all(v == 0 for v in valores):
            filas_sin_dato.append((material, cuenta, unidad))

        for j, v in enumerate(valores):
            ws.cell(row=fila_idx, column=4 + j, value=round(v, 2) if v else None)

    wb.save(salida)

    print(f"Guardado {salida}")
    print(f"Materiales encontrados en costos_eventos.csv: {sorted(materiales_vistos)}")
    if usando_producto_como_material:
        print("AVISO: costos_eventos.csv no tiene columna 'material' (ADR-071 no aplicado "
              "todavia a esta corrida) -- se uso 'producto' como aproximacion. Volver a "
              "correr esta rutina con una corrida posterior al MOD para las 5 filas de "
              "material completas (AEL/CDL/JCCL/JCL/PCL).")
    if filas_sin_dato:
        print(f"{len(filas_sin_dato)} filas de la plantilla quedaron en 0 "
              "(combinacion material/cuenta sin cargos en la corrida).")
    if usd_sin_material:
        total = sum(usd_sin_material.values())
        print(f"AVISO IMPORTANTE: USD {total:,.0f} de cargos con Cuenta mapeada pero SIN "
              "material resuelto no entraron a ninguna fila del Resumen (para no "
              "inventar a que material pertenecen). Por cuenta:")
        for cuenta, monto in sorted(usd_sin_material.items(), key=lambda kv: -kv[1]):
            print(f"  - {cuenta}: USD {monto:,.0f}")
        print("  Si este numero es alto, revisar si el modelo tiene la resolucion de "
              "material por pedido de ADR-071 (fallback agregado tras Ejemplo_12).")
    if flete_sin_tn:
        print(f"AVISO: FLETE DEPOSITO quedó con Tn en 0 a proposito -- USD "
              f"{flete_sin_tn:,.0f} de FLETE_PRODUCTO no tienen id_asignacion en "
              "costos_eventos.csv (se cobran contra el pedido, no contra un contenedor), "
              "asi que no hay join confiable con asignaciones_elegidas.csv todavia. "
              "USD de esa cuenta SI esta completo.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    armar(*sys.argv[1:])
