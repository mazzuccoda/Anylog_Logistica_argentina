# MOD — Resumen de cuentas por material (aging 0-999 días)

> Análisis de factibilidad: ¿el output del modelo (`Ejemplo_11.zip`, esquema
> `ADR-064.1`) permite armar el `Resumen_cuentas.xlsx` requerido? Qué falta y
> qué cambio concreto hay que aplicar.

## 0. El modelo real es otro repo — ya identificado

`Ejemplo_11.zip` no sale de este repositorio (acá vive un modelo simple de un
solo producto y 5 depósitos). Sale de
**[`mazzuccoda/Anylogic_log_arg_2026`](https://github.com/mazzuccoda/Anylogic_log_arg_2026)**
(confirmado: `AuditoriaRed.VERSION_ESQUEMA = "ADR-064.1"` en ese repo coincide
exacto con el `version_esquema` del manifiesto del zip). Es un proyecto
grande y maduro — 70 ADRs, contrato de datos, plan de validación, changelog
detallado — con un proceso propio para tocar el `.alp`: se parchea el XML a
mano con reemplazos de texto verificados como únicos, se valida el XML, se
regenera `model_src/`+`MANIFIESTO.md` con `tools/exportar_modelo.py`, y la
corrida real en AnyLogic PLE 8.9.9 la hace el usuario (esa parte no se puede
hacer desde este entorno). Todo lo que sigue está pensado para respetar ese
proceso, no para saltearlo.

Lectura de solo-lectura de ese repo (clonado en este entorno para el
análisis): commit `2660913` (2026-08-11).

## 1. Confirmado: el modelo YA tiene el concepto "material" (ADR-067/069)

`ADR-067 — Material como dimensión física del inventario` ya implementó
exactamente los 5 códigos que pide el Resumen. La tabla de validación
`V-MAESTRO-03` de ese repo lo dice literal:

> `JUGO/JCL` asigna 15.842 tn de 16.961 pedidas —su disponibilidad de
> campaña—, mientras `JCCL` (142) y `PCL` (133) asignan su demanda completa...
> `CASCARA/CDL` 12.261 y `ACEITE/AEL` 1.250, completos.

O sea, el mapeo `producto → material` es:

| producto (zip) | material(es) |
|---|---|
| `ACEITE` | `AEL` |
| `CASCARA` | `CDL` |
| `JUGO` | `JCL`, `JCCL`, `PCL` |

Esto cierra exactamente las 5 filas de "material" del Resumen. **No hace
falta inventar ni pedir un mapeo** — ya está resuelto en el modelo, sólo
falta que ese dato salga en los CSV de auditoría.

## 2. Confirmado: los buckets de días son el mismo "tramo" que ya usan las tarifas

Los encabezados `0-31, 31-59, 59-90, …, 334-999` del Resumen **no son un
invento del reporte** — son literalmente la grilla de tramos que
`Maestro_Simulacion.xlsx` ya usa para todas las tarifas (`Tarifa_almacenaje`,
`Consolidado`, `Cross_docking`, `Despachante`, `Gastos_terminal`,
`TarifaRoundTrip`, `Tipo_cambio`), descripta en ADR-068/070
(`Fila.columnasDeRango()` + `leerTramos()`), y el ADR-070 usa el bucket
`'334-999'` en un ejemplo numérico palabra por palabra. Conclusión: el
Resumen agrupa por el mismo eje de tramos que el modelo ya sabe leer y
escribir — no hay que definir un bucketing nuevo, alcanza con `dia_campania`
contra esa misma grilla.

## 3. El único gap real: el `material` no sale en los CSV de auditoría

`Pedido`, `LoteProducto` y `ContenedorExportacion` ya tienen el campo
`material` (ADR-067/069). Pero **ninguna de las 4 tablas de auditoría lo
exporta**: ni `costos_eventos.csv` (`RegistroCostos.Cargo`), ni
`asignaciones_elegidas.csv` (`AsignacionPedido`), ni
`decisiones_alternativas.csv`, ni `snapshot_inventario.csv`. Por eso
`Ejemplo_11.zip` sólo distingue por `producto` (3 valores) y no por
`material` (5 valores): la dimensión existe en el modelo, pero se pierde al
volcar a CSV.

### Propuesta de MOD — quirúrgica, sin tocar `RegistroCostos.Cargo`

En vez de agregar `material` a la clase `Cargo` y re-cablear sus 15 sitios
de `registro.registrar(...)`, alcanza con resolverlo en
`Main.exportarCostosEventos()` (`model_src/Main.java:3098`), que ya arma
lookups parecidos (`asignacionDeContenedor`, `decisionDeAsignacion`) a
partir de `pedido.contenedores` / `pedido.asignaciones`:

1. Agregar un lookup `materialDeContenedor` (`idContenedor → contenedor.material`),
   igual que el `asignacionDeContenedor` que ya existe ahí.
2. Agregar un lookup `materialDeLote` (`idLote → lote.material`), recorriendo
   `lotes` (o vía `buscarLote(...)`, ajustando el tipo — `Cargo.idLote` es
   `String` y `LoteProducto.idLote` es `int`).
3. Resolver por cargo: contenedor si `codigoContenedor` no es vacío → si no,
   lote si `idLote` no es vacío → si no, `""` (cargos de alcance `RED`, como
   `OPORTUNIDAD_FRIO`/`PENALIDAD_SOBRECARGA`, quedan sin material — no
   aplican al Resumen de todos modos, ver §4).
4. Agregar la columna `material` a `encabezadoCostosEventos()` y a la fila
   que arma `exportarCostosEventos()` (`Main.java:3092` y `3186-3202`).
5. Mismo patrón, más simple, en `AsignacionPedido.encabezadoCsv()`/`toCsv()`:
   pasar `pedido.material` como parámetro nuevo (la asignación ya vive
   colgada de un `Pedido` que ya tiene el dato).
6. Bump de `AuditoriaRed.VERSION_ESQUEMA` (`"ADR-064.1"` → `"ADR-064.2"` o
   similar) porque cambia una columna del contrato, siguiendo la convención
   que el propio repo documenta en `AuditoriaRed.java`.
7. Nuevo ADR corto (`ADR-071` sería el próximo número libre) documentando el
   cambio, más entrada en `Roadmap.md` y `CHANGELOG.md`, siguiendo el patrón
   que el resto del repo sigue estrictamente para cualquier cambio de
   contrato.

Esto es plumbing puro (no cambia ninguna decisión de negocio ni un número de
la campaña) y no toca la lógica de costeo ni las 15 llamadas a
`registro.registrar(...)`.

## 4. Columna Tn: directa para almacenaje, requiere join para el resto

Con `material` agregado a `costos_eventos.csv`, la columna **USD** del
Resumen queda 100% resuelta para las 9 cuentas mapeables (ver tabla de
`categoria → Cuenta` más abajo). La columna **Tn**:

- **ALMACENAJE (IN/STORAGE/OUT):** directa — `cargo.cantidad` ya está en
  toneladas para esas 3 categorías (`IN_DEPOSITO`, `ALMACENAMIENTO`,
  `OUT_DEPOSITO`).
- **ROUND TRIP, FLETE DEPOSITO, CONSOLIDADO, TERMINAL, CROSS DOCKING, GASTOS
  THC, DESPACHANTE:** el evento de costo está expresado por contenedor o por
  viaje (`cantidad = 1`), no en toneladas. Con `material` ya agregado a
  `asignaciones_elegidas.csv` (punto 3.5), el reporte puede hacer un join
  `costos_eventos.id_asignacion → asignaciones_elegidas.id_asignacion` y
  tomar de ahí `toneladas_despachadas`/`toneladas_entregadas` — no hace
  falta otro cambio de modelo, es join en el script del reporte.

| categoria (zip) | Cuenta (Resumen) |
|---|---|
| `IN_DEPOSITO` | ALMACENAJE (IN) |
| `ALMACENAMIENTO` | ALMACENAJE (STORAGE) |
| `OUT_DEPOSITO` | ALMACENAJE (OUT) |
| `ROUND_TRIP` | ROUND TRIP |
| `FLETE_PRODUCTO` | FLETE DEPOSITO *(a confirmar el nombre, ver preguntas)* |
| `CONSOLIDACION` | CONSOLIDADO |
| `COSTO_TERMINAL` | TERMINAL |
| `CROSS_DOCK` | CROSS DOCKING |
| `THC` | GASTOS THC |
| `DESPACHANTE` | DESPACHANTE |
| `OPORTUNIDAD_FRIO` | *(sin cuenta en el Resumen; $0 en esta corrida)* |
| `PENALIDAD_SOBRECARGA` | *(sin cuenta en el Resumen; $0 en esta corrida)* |

## 5. Ya validado con datos reales

Armé un pivot en Python sobre `costos_eventos.csv` del zip (105.461 filas)
bucketizando por `dia_campania` en los 12 tramos del Resumen: la columna USD
sale sin problema para las 9 cuentas mapeadas (ejemplo real, `JUGO → FLETE
DEPOSITO`, USD por tramo: `[33600, 38700, 35800, 27300, 123300, 276400,
225000, 287900, 190400, 164900, 137600, 109600]`). Falta únicamente que el
zip traiga `material` en vez de (o además de) `producto` para separar `JUGO`
en `JCL`/`JCCL`/`PCL`.

## 6. Preguntas abiertas (única parte que sigue bloqueada)

Ver preguntas en el chat.
