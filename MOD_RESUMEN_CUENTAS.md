# MOD — Resumen de cuentas por material (aging 0-999 días)

> Análisis de factibilidad: ¿el output del modelo (`Ejemplo_11.zip`, esquema
> `ADR-064.1`) permite armar el `Resumen_cuentas.xlsx` requerido? Qué falta y
> qué hay que confirmar antes de tocar el modelo.

## 0. Punto crítico: el zip NO sale de este repositorio

`Ejemplo_11.zip` es la salida de un modelo AnyLogic con:
- 3 productos (`ACEITE`, `CASCARA`, `JUGO`)
- reservas, alternativas de asignación, consolidación en terminal, cross-dock,
  portacontenedores, múltiples sitios reales (ZARATE, T4, DODERO, BOREAS,
  FRINOA, NORRY, GRUPO_PAZ, CONTROL_UNION, RUTA9, PLANTA)
- 6 tablas de auditoría (`decisiones_alternativas`, `asignaciones_elegidas`,
  `ejecucion_arcos`, `costos_eventos`, `snapshot_inventario`,
  `capacidad_por_dia`) versionadas con manifiesto/esquema JSON.

Este repo (`mazzuccoda/anylog_logistica_argentina`, rama actual) contiene un
modelo **distinto y mucho más simple**: un único producto "jugo", cámara
propia + 5 depósitos (3 Tucumán / 2 Buenos Aires), sin terminales, sin
consolidación, sin contenedores. No hay ningún archivo en el repo (`.alp`,
`.java`, `.md`) que genere las columnas `categoria`, `id_contenedor`,
`circuito`, etc. que aparecen en el zip.

**Conclusión:** el modelo real que hay que modificar para producir el
Resumen no vive en este repositorio. Las propuestas de MOD de este
documento están escritas para poder aplicarse sobre ese modelo (el que
generó `Ejemplo_11.zip`), pero yo no tengo ese código para editarlo acá.
Ver pregunta 1 más abajo.

## 1. ¿Es posible armar el resumen? — Sí, parcialmente, con `costos_eventos.csv`

La hoja pedida es una tabla `material × Cuenta × Unidad` con 12 columnas de
antigüedad (`0-31 … 334-999`, días de campaña acumulados ≈ 12 "meses").

`costos_eventos.csv` (105.461 filas) ya trae, por evento de costo:
`categoria`, `producto`, `dia_campania`, `unidad`, `cantidad`, `importe_usd`.
Mapeo directo `categoria → Cuenta`:

| categoria (zip)      | Cuenta (Resumen)      | Unidad del evento |
|---|---|---|
| `IN_DEPOSITO`         | ALMACENAJE (IN)        | `USD_TN` (cantidad = Tn reales) |
| `ALMACENAMIENTO`      | ALMACENAJE (STORAGE)   | `USD_TN_DIA` (cantidad = Tn en depósito ese día) |
| `OUT_DEPOSITO`        | ALMACENAJE (OUT)       | `USD_TN` (cantidad = Tn reales) |
| `ROUND_TRIP`          | ROUND TRIP              | `USD_CONTENEDOR` (cantidad = 1 contenedor) |
| `FLETE_PRODUCTO`      | FLETE DEPOSITO *(?)*    | `USD_VIAJE` (cantidad = 1 viaje) |
| `CONSOLIDACION`       | CONSOLIDADO             | `USD_CONTENEDOR` |
| `COSTO_TERMINAL`      | TERMINAL                | `USD_CONTENEDOR` |
| `CROSS_DOCK`          | CROSS DOCKING           | `USD_CONTENEDOR` |
| `THC`                 | GASTOS THC              | `USD_CONTENEDOR` |
| `DESPACHANTE`         | DESPACHANTE             | `USD_CONTENEDOR` |
| `OPORTUNIDAD_FRIO`    | *(sin fila en el Resumen)* | siempre $0 en esta corrida (cuenta económica/sombra) |
| `PENALIDAD_SOBRECARGA`| *(sin fila en el Resumen)* | siempre $0 en esta corrida |

Con esto armé un prototipo (pivot en Python sobre `costos_eventos.csv`,
bucketizando por `dia_campania` en los 12 rangos del Resumen). **La columna
USD se completa sin problema para las 9 cuentas mapeadas.** Ejemplo real de
la corrida (`JUGO → FLETE DEPOSITO`, USD por bucket):

```
[33600, 38700, 35800, 27300, 123300, 276400, 225000, 287900, 190400, 164900, 137600, 109600]
```

**La columna Tn NO se completa igual para todas las cuentas.** Sólo
`ALMACENAJE (IN/STORAGE/OUT)` traen la tonelada real en `cantidad`. Para
`ROUND TRIP`, `FLETE DEPOSITO`, `CONSOLIDADO`, `TERMINAL`, `CROSS DOCKING`,
`GASTOS THC`, `DESPACHANTE`, el evento está expresado **por contenedor o por
viaje** (`cantidad = 1`), no en toneladas. Para esas filas el Resumen en Tn
requiere un **join** con `asignaciones_elegidas.csv` (toneladas por
`id_asignacion`/`id_contenedor`) o `ejecucion_arcos.csv` (toneladas por arco
de carga), usando `id_contenedor` / `codigo_pedido` como clave — el join es
viable (las claves están disponibles) pero no viene resuelto en el CSV.

## 2. Gaps que requieren decisión/MOD antes de generar el Resumen

1. **Materiales (dimensión "material" del Resumen):** el Resumen pide 5
   códigos (`AEL`, `CDL`, `JCCL`, `JCL`, `PCL` — parecen productos de la
   industria del limón: aceite esencial, cáscara deshidratada, jugo
   concentrado clarificado, jugo concentrado, cáscara/pellets). El modelo
   sólo emite 3 (`ACEITE`, `CASCARA`, `JUGO`). Falta el mapeo 1 a 1 (o el
   modelo tiene que desdoblar sus 3 productos en 5).
2. **`AEL` (aceite) no tiene ningún movimiento de IN/STORAGE/OUT** en esta
   corrida — sólo aparece en DESPACHANTE/FLETE/THC/TERMINAL/ROUND TRIP. ¿Es
   así en la operación real (el aceite no pasa por depósito propio) o falta
   emitir esos eventos para `ACEITE` en el modelo?
3. **`FLETE_PRODUCTO` vs "FLETE DEPOSITO":** el nombre de la cuenta del
   Resumen sugiere flete *entre depósitos*, mientras que `FLETE_PRODUCTO` en
   el zip es el flete de *producto por viaje* (planta→terminal, etc.). Hay
   que confirmar que son la misma cuenta contable o si falta otra categoría
   de costo específica de "flete inter-depósito".
4. **Tn para cuentas por contenedor/viaje** (todas menos ALMACENAJE): requiere
   el join descripto arriba. Alternativa más limpia: pedir que el modelo
   agregue una columna `toneladas_asociadas` directamente en
   `costos_eventos.csv` para esos eventos (evita el join en el reporte).
5. **`OPORTUNIDAD_FRIO` y `PENALIDAD_SOBRECARGA`** no tienen cuenta en el
   Resumen. En esta corrida su importe es siempre 0, así que no afectan el
   resultado, pero si en otras corridas toman valor > 0, ¿se deben mostrar
   en alguna fila del Resumen o quedan fuera de esta vista contable?
6. **Definición de "Tn" en ALMACENAJE (STORAGE):** al sumar `cantidad` día a
   día se obtiene toneladas-día acumuladas (no un promedio ni un stock
   puntual). ¿Es esa la métrica esperada en esa columna, o el Resumen quiere
   otra cosa (ej. promedio de stock del período, o Tn ingresadas)?
7. **Buckets de antigüedad:** `0-31…304-334, 334-999` calzan bien con
   `dia_campania` (1 a 365) tomando el último bucket como cola/cierre de
   campaña. Asumí que el eje correcto es `dia_campania` (no `dia` de
   simulación corrida, ni fecha de vencimiento del pedido). A confirmar.
8. **Escenario/réplica:** el zip trae un solo run (`E-00`, réplica 0). El
   Resumen no tiene columnas de escenario/réplica — ¿el reporte es por
   corrida (un Excel por escenario) o hay que consolidar/promediar réplicas?

## 3. Próximo paso si se confirman los mapeos

Con las respuestas a la sección 2, el reporte se arma con un script (Python
+ `openpyxl`, o una tabla dinámica) que:
1. Lee `costos_eventos.csv` (+ join con `asignaciones_elegidas.csv` para Tn
   de cuentas no-almacenaje).
2. Aplica el mapeo `categoria → Cuenta` y `producto → material`.
3. Bucketiza por `dia_campania` en los 12 rangos del Resumen.
4. Vuelca a la hoja `Resumen (a_completar)` respetando el orden de filas del
   template (`material` agrupado dentro de cada `Cuenta`/`Unidad`).

No hace falta re-simular nada para probar esto: alcanza con el
`Ejemplo_11.zip` ya generado. El único cambio de *modelo* (MOD real) sería
el punto 4 (agregar `toneladas_asociadas` al costo del evento) si se prefiere
esa vía en vez del join en el reporte.
