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

## 6. Estado: implementado — pendiente de correr en AnyLogic

Confirmado por el usuario: `FLETE DEPOSITO` = `FLETE_PRODUCTO`, y usar el join
por `id_asignacion` para las toneladas de las cuentas por contenedor está
bien si llega al mismo resultado.

**MOD aplicado** en `mazzuccoda/Anylogic_log_arg_2026`, rama
[`claude/adr-071-material-auditoria`](https://github.com/mazzuccoda/Anylogic_log_arg_2026/pull/new/claude/adr-071-material-auditoria)
(ADR-071, esquema `ADR-064.2`): `costos_eventos.csv` y `asignaciones_elegidas.csv`
ahora exportan `material`. `model_src/` y `MANIFIESTO.md` regenerados con
`tools/exportar_modelo.py`; XML validado. **Falta el único paso que este
entorno no puede hacer:** compilar y correr `E-00` en el IDE de AnyLogic
PLE con `datos/Maestro_Simulacion.xlsx` y confirmar que reconcilia igual
que ADR-070 (8 453 167 USD de caja, 29 439 tn exportadas) — no debería
cambiar ningún número, es sólo plumbing de exportación.

**Un límite que apareció al construir el join de Tn:** `FLETE_PRODUCTO`
(→ `FLETE DEPOSITO`) se cobra contra el **pedido**, no contra un contenedor
— su `id_asignacion` en `costos_eventos.csv` está **siempre vacío**, así que
no hay join posible contra `asignaciones_elegidas.csv` para esa cuenta. La
columna **USD** de `FLETE DEPOSITO` sale completa igual; la columna **Tn**
de esa única cuenta queda pendiente (0) hasta resolver un join distinto (por
`codigo_pedido`, más ambiguo porque un pedido puede tener varias
asignaciones). Para las otras 6 cuentas por contenedor (`ROUND TRIP`,
`CONSOLIDADO`, `TERMINAL`, `CROSS DOCKING`, `GASTOS THC`, `DESPACHANTE`) el
join sí funciona limpio, dividiendo `toneladas_despachadas` de la asignación
por `contenedores_creados` para no contar el total de la asignación una vez
por cada contenedor/evento.

## 7. Script del reporte, ya armado y probado

`armar_resumen_cuentas.py` (en este repo) lee `costos_eventos.csv` +
`asignaciones_elegidas.csv` de la carpeta de resultados y completa
`Resumen_cuentas.xlsx`. Verificado con el `Ejemplo_11.zip` original: los
totales de USD por material/cuenta/tramo coinciden exactamente con el
pivot manual de la sección 1 (ej. `JUGO → FLETE DEPOSITO`:
`[33600, 38700, 35800, 27300, 123300, 276400, 225000, 287900, 190400,
164900, 137600, 109600]`), y el join de Tn por contenedor da valores
plausibles para `ROUND TRIP` (antes en 0).

**No lo corrí contra el zip original como entrega final** porque ese zip
no tiene columna `material` (es anterior al MOD) — el script cae a
`producto` como aproximación, que no calza con los 5 códigos de la
plantilla (`AEL`/`CDL`/`JCCL`/`PCL` no existen todavía sin el material real
de `JCCL`/`PCL` separado de `JCL`) y el Excel sale vacío a propósito, en vez
de inventar un reparto entre materiales que nadie pidió. Corré:

```
python3 armar_resumen_cuentas.py <carpeta_resultados_nueva_corrida> Resumen_cuentas.xlsx salida.xlsx
```

apenas tengas una corrida de `E-00` hecha con el modelo parchado, y va a
salir completo (salvo el Tn de `FLETE DEPOSITO`, con el aviso explícito de
por qué).

## 8. Corrida real (`Ejemplo_12.zip`, esquema `ADR-064.2`) — confirma y corrige

El usuario compiló y corrió el modelo con el MOD aplicado. Resultado clave:
**los 5 materiales del `costos_eventos.csv`/`asignaciones_elegidas.csv` de
esta corrida son exactamente `AEL`, `CDL`, `JCCL`, `JCL`, `PCL`** — calzan
1 a 1 con los códigos de la plantilla `Resumen_cuentas.xlsx`, sin necesidad
de ningún mapeo manual (a diferencia de lo que había que asumir con
`Ejemplo_11.zip`, que sólo tenía `ACEITE`/`CASCARA`/`JUGO`).

Corriendo `armar_resumen_cuentas.py` contra esta carpeta encontré un gap
real: **706 900 USD de `FLETE_PRODUCTO` (10 % del total de la corrida)
tenían `material` vacío** y el script los excluía del Excel — en vez de
dejarlos pasar en silencio, ahora los reporta con nombre y monto por
cuenta (`AVISO IMPORTANTE`). La causa: el flete por viaje del circuito
`CONSOLIDACION_TERMINAL` se cobra **antes de que exista el contenedor y
sin lote asociado**, así que ni `materialDeContenedor` ni `materialDeLote`
podían resolverlo — pero el cargo sí sabe de qué `codigo_pedido` es, y un
pedido nunca mezcla materiales entre sus asignaciones (0 casos en la
corrida). Agregué un tercer nivel de resolución en el modelo
(`materialDePedido`, mismo commit `claude/adr-071-material-auditoria`) que
cierra el 100 % del importe: `6 472 344 + 706 900 = 7 179 244 USD`, exacto
contra el total de cargos `CAJA` de la corrida.

**Con los datos de `Ejemplo_12.zip` tal cual** (sin el fallback por pedido,
que es posterior a esa corrida) generé `Resumen_cuentas_E-00.xlsx`: sale
completo salvo `AEL → FLETE DEPOSITO (USD)` — que cae justo dentro de esos
706 900 USD sin resolver — y el Tn de `FLETE DEPOSITO` para los 5
materiales (limitación de la sección 6, sigue abierta). El resto de ceros
de la plantilla son de negocio, no del reporte: `AEL` no pasa por depósito
propio (sin `ALMACENAJE IN/STORAGE/OUT`) y `AEL`/`CDL` no tienen
`CONSOLIDADO` ni `CROSS DOCKING` en esta corrida.

**Para el reporte 100 % completo:** volver a correr `E-00` con el último
commit de la rama (`claude/adr-071-material-auditoria`) y correr
`armar_resumen_cuentas.py` sobre esa carpeta nueva.

## 9. `toneladas` explícito en `costos_eventos` (ADR-072) — cierra el Tn de FLETE DEPOSITO

El usuario preguntó específicamente por el Tn en 0 de `FLETE DEPOSITO` y pidió
alternativas antes de tocar nada. Se evaluaron 3 (documentadas en el chat):
resolver por lote (descartada — `LoteProducto.toneladas` es un balance de
stock que cambia día a día, no la tonelada de un envío puntual; y el call
site que genera el grueso del gap ni pasa `idLote`), aproximar en el reporte
vía join (la que había, no aplica a `FLETE_PRODUCTO` porque nunca tiene
`id_asignacion`), y capturar `toneladas` en el momento del cargo (elegida).

**Implementado** en `mazzuccoda/Anylogic_log_arg_2026`, mismo branch
`claude/adr-071-material-auditoria` (esquema `ADR-064.3`):
`RegistroCostos.Cargo` gana el campo `toneladas`, capturado en el momento
del devengo. `registro.registrar(...)` se overloadeó: la firma vieja
(17 args) sigue igual para los 9 sitios que ya facturan por tonelada; sólo
6 sitios (los que facturan por contenedor o viaje: `FLETE_PRODUCTO` rama
`USD_VIAJE`, `ROUND_TRIP`, `CONSOLIDACION`/`CROSS_DOCK`, `THC`,
`COSTO_TERMINAL`, `DESPACHANTE`) pasan a la firma nueva con la tonelada
real, que ya estaba en scope en cada uno (`toneladas`/`envio.toneladas`).
Verificación de aridad de los 15 sitios con un script ad hoc (cuenta
argumentos de nivel superior, ignora comentarios `//`): 17 en los que no
cambian, 18 en los 6 nuevos, sin errores.

**Qué se pudo validar sin AnyLogic (no hay motor de simulación acá) y qué
no:** actualicé `armar_resumen_cuentas.py` para usar la columna `toneladas`
directo cuando existe (sin joins) y lo corrí con una columna `toneladas`
sintética armada a partir de `asignaciones_elegidas.csv` — confirma que la
plomería del reporte funciona y que el camino con `toneladas` deja de emitir
el aviso de "FLETE DEPOSITO en 0". **Lo que no pude ejercitar con los CSV ya
exportados** es el sub-caso de flete de *transferencia entre depósitos*
(`movidas`, sin `codigo_pedido`): esas filas no llevan ninguna referencia
exportada a la tonelada transferida más que el propio código nuevo, así que
no hay forma de reconstruir un valor "de verdad" para probarlo offline. Lo
verifiqué leyendo el código a mano: `movidas` es una variable ya calculada
en los dos call sites de transferencia y se pasa tal cual al parámetro
`toneladas` de `registrarFleteProducto(...)`, sin ambigüedad — pero la
prueba definitiva es correr el modelo.

**Para tener USD y Tn 100 % exactos, sin joins ni aproximaciones, en las 10
cuentas:** volver a correr `E-00` con el commit más reciente de la rama
(incluye ADR-071 completo + ADR-072) y correr `armar_resumen_cuentas.py` de
nuevo — el script detecta solo la columna `toneladas` y deja de usar el
join aproximado.

## 10. Cierre — MOD verificado con una corrida real completa

Las dos corridas intermedias (`Ejemplo_14`, `Ejemplo_15`) resultaron ser el
mismo dataset re-empaquetado, byte a byte igual a `Ejemplo_12` — el `.alp`
abierto en el IDE (hash `8ab11e09…`) coincidía con el commit `2eba613`, dos
commits atrás de la punta de la rama. Se le pasó al usuario el `.alp` de la
punta (`c4802af`, hash `35794447…`) para reemplazar en el IDE.

`Ejemplo_16.zip` es la corrida con el `.alp` correcto: `version_esquema:
ADR-064.3`, columna `toneladas` sin vacíos ni negativos, `material` vacío
sólo en `OPORTUNIDAD_FRIO`/`PENALIDAD_SOBRECARGA` (correcto, son cargos de
red). `armar_resumen_cuentas.py` contra esta corrida da:

- **USD total del Resumen: 7 179 244,34**, exacto contra el total de cargos
  `CAJA` de la corrida — cero USD sin atribuir.
- **`FLETE DEPOSITO (Tn)` ya no está en cero** para ningún material: tonelada
  exacta por tramo, capturada en el cargo (ADR-072), sin join.
- Quedan 12 celdas en 0, todas de negocio: `AEL` no pasa por depósito propio
  (`ALMACENAJE IN/STORAGE/OUT`) y `AEL`/`CDL` no tienen `CONSOLIDADO` ni
  `CROSS DOCKING` en este escenario.

**El MOD queda cerrado**: no hay más limitaciones conocidas pendientes en
`armar_resumen_cuentas.py` para este escenario (`E-00`). Falta compilar y
correr en el IDE de AnyLogic para cualquier corrida nueva (otro escenario,
otra réplica), pero el camino ya está probado de punta a punta.
