# Modelo AnyLogic 8.x PLE — Logística de Jugo (producción + distribución anual)

> Simulación de eventos discretos (Process Modeling Library) + Optimization
> Experiment (OptQuest), sin librerías pagas. Horizonte: 365 días.
>
> **Placeholders `[COMPLETAR]` / `[X]` / `[Y]`**: valores que completás vos en la
> plantilla Excel (`parametros_jugo.xlsx`) antes de correr.

Flujo modelado:

```
Planta (Source)
   └─> Cámara propia (Queue, cap. 5.000 tn)
          └─> Preparar despacho (asigna destino de mínimo costo)
                 └─> Ruteo por depósito (SelectOutput5)
                        ├─ Tucumán: dep. A / B / C   (costo transporte X)
                        └─ Buenos Aires: dep. A / B   (costo transporte Y)
                              └─> Transporte (Delay por ruta)
                                     └─> Llegada al depósito (recibirLote → nivel + costo)

Costo total anual = Σ transporte (por ruta) + Σ almacenamiento (tarifa · nivel · tiempo)  →  MINIMIZAR
```

---

## 1. Estructura de agentes, parámetros y bloques a crear en el IDE

### 1.1 Agente `Deposito` (New → Agent Type: `Deposito`, population de 5)
**Parameters**
| Nombre | Tipo | Origen |
|---|---|---|
| `region` | String | "Tucuman" / "BuenosAires" |
| `tarifaAlmacenamiento` | double | Excel hoja `Depositos` ($/tn/día) |
| `capacidadMaxima` | double | Excel hoja `Depositos` (tn) |
| `costoTransporteUnitario` | double | X (Tucumán) / Y (BsAs) |

**Variables**: `nivelActual` (double=0), `costoAlmacenAcum` (double=0), `costoTransporteAcum` (double=0)
**Functions**: `capacidadDisponible`, `puedeRecibir(tn)`, `recibirLote(tn)`, `consumirDemanda(tn)`, `acumularAlmacenamientoDia`, `costoMarginalUnitario(dias)` — cuerpos en el Entregable 2.

### 1.2 Agente `Lote` (entidad que fluye por el proceso)
**Parameters**: `tn` (double, default = tamaño de lote, p.ej. 1 tn o = `capacidadCamion`).
**Variables**: `destino` (tipo `Deposito`, init null).

### 1.3 Agente `Main` — objetos embebidos y bloques PML
**Population**: `depositos` (agente `Deposito`, tamaño 5). Inicializá cada instancia desde Excel (ver Entregable 4).

**Parameters de Main**: `capacidadCamara`=5000, `capacidadCamion`, `tiempoViajeTucuman`, `tiempoViajeBsAs`, `pesoDeposito` (double[5], lo mueve OptQuest), `usarOptimizacion` (boolean).
**Variables de Main**: `costoTransporteTotal`=0, `costoAlmacenTotal`=0.
**Functions de Main**: `diasHastaFinAnio`, `costoTotalActual`, `mejorDepositoGreedy(tn)`, `depositoPorPesos(tn)`, `asignarDestino(lote, usarOpt)`, `tiempoViaje(dep)`, `produccionActual()` (rate estacional).

**Bloques Process Modeling Library (en el diagrama de `Main`)**
| # | Bloque | Nombre | Configuración clave |
|---|---|---|---|
| 1 | `Source` | `source` | Arrivals = **Rate**, rate = `produccionActual()`; New agent = `Lote`; en *On exit* setear `agent.tn` |
| 2 | `Queue` | `camaraPropia` | Capacity = `capacidadCamara` (5000). Representa la cámara propia |
| 3 | `Delay` | `prepararDespacho` | *On enter*: `asignarDestino(agent, usarOptimizacion);` — delay ~0. Si `asignarDestino` devuelve false, no hay capacidad: mandarlo de vuelta a `camaraPropia` (ver nota) |
| 4 | `SelectOutput5` | `ruteoDeposito` | 5 salidas; condición i: `agent.destino == depositos.get(i)` |
| 5 | `Delay` | `transporte` | Delay time = `tiempoViaje(agent.destino)`; *On exit*: `agent.destino.recibirLote(agent.tn);` |
| 6 | `Sink` | `llegadaDeposito` | fin del flujo (el jugo ya quedó contabilizado en el depósito) |

> **Camiones (opcional):** insertá `Seize`/`Release` con un `ResourcePool` `camiones` entre 3 y 4 para limitar transporte concurrente; capacidad de carga = `capacidadCamion` (podés usar `Batch` de N=capacidadCamion tn antes del Seize).

> **Nota de rebote por capacidad llena:** si querés que un lote sin depósito disponible espere en cámara, agregá un `SelectOutputOut` booleano tras `prepararDespacho` con condición `agent.destino != null`; la rama false vuelve a `camaraPropia`.

**Event de costos**: `eventCostoDiario` (Cyclic, cada 1 DAY):
```java
for (Deposito d : depositos) d.acumularAlmacenamientoDia();
costoTotalActual();
```

### 1.4 `produccionActual()` — perfil estacional
```java
// Function Main: produccionActual() -> double   (tn/día del mes actual)
double produccionActual() {
    int mesIdx = (int)(time(DAY) / (365.0/12.0));   // 0..11 aprox
    mesIdx = min(11, max(0, mesIdx));
    return produccionMensual[mesIdx];   // double[12] cargado desde Excel hoja ProduccionMensual
}
```

---

## 2. Código Java completo

Ver archivo adjunto **`funciones_anylogic.java`** (todas las funciones, con firma exacta y agente donde va cada una). Resumen de las clave:

- **Costo por ruta / marginal:** `Deposito.costoMarginalUnitario(dias)` = `costoTransporteUnitario + tarifaAlmacenamiento * dias`.
- **Costo total (objetivo):** `Main.costoTotalActual()` = Σ transporte + Σ almacenamiento sobre `depositos`.
- **Asignación greedy (mínimo costo):** `Main.mejorDepositoGreedy(tn)` — recorre depósitos con capacidad y elige el menor costo marginal.
- **Asignación por pesos (OptQuest):** `Main.depositoPorPesos(tn)` — elige el depósito de mayor `pesoDeposito[i]` con capacidad.
- **Actualización de niveles:** `Deposito.recibirLote(tn)` (suma nivel + costo transporte), `acumularAlmacenamientoDia()` (costo diario), `consumirDemanda(tn)` (opcional).

---

## 3. Optimization Experiment (OptQuest)

> En AnyLogic PLE el **Optimization experiment está disponible** (con límite de
> tamaño de modelo). Si tu build lo restringe, usá el **fallback greedy**
> (`usarOptimizacion=false`) que ya minimiza costo por decisión local.

**Crear:** botón derecho sobre el modelo → New → Experiment → **Optimization**. Top-level agent = `Main`.

- **Objetivo:** `minimize` → `root.costoTotalActual()`
- **Variables de decisión (continuas):**
  | Variable | Min | Max | Step |
  |---|---|---|---|
  | `root.pesoDeposito[0]` | 0 | 1 | 0.01 |
  | `root.pesoDeposito[1]` | 0 | 1 | 0.01 |
  | `root.pesoDeposito[2]` | 0 | 1 | 0.01 |
  | `root.pesoDeposito[3]` | 0 | 1 | 0.01 |
  | `root.pesoDeposito[4]` | 0 | 1 | 0.01 |

  (Poné `root.usarOptimizacion = true` en *Initial experiment setup* para que el dispatch use `depositoPorPesos`.)

- **Restricciones (Constraints):** las capacidades ya se respetan dentro del modelo (`puedeRecibir`). Además, para exigir que **todo se despache** (no quede jugo atrapado en cámara al fin del año), agregá una restricción tipo *requirement*:
  - `camaraPropia.size() <= toleranciaTn` (feasible si la cámara queda casi vacía) — o penalizá en el objetivo:
    ```java
    // variante penalizada del objetivo:
    return costoTransporteTotal + costoAlmacenTotal + 1e6 * camaraPropia.size();
    ```
- **Balance de masa:** garantizado por construcción (todo lo que sale de Source va a cámara y de ahí a un depósito; nada se destruye salvo `consumirDemanda`).
- **Stop:** por iteraciones (p.ej. 500) o *automatic*. Stop time de cada corrida = 365 días.

---

## 4. Plantilla Excel de parámetros — `parametros_jugo.xlsx`

Adjunta. Tres hojas:
1. **`Depositos`** — 5 filas (3 Tucumán + 2 BsAs): `id, nombre, region, tarifa_almacenamiento_$tn_dia, capacidad_maxima_tn, costo_transporte_unitario_$tn, tiempo_viaje_horas`.
2. **`ProduccionMensual`** — 12 filas: `mes, nombre_mes, produccion_diaria_tn` (perfil estacional).
3. **`Globales`** — `capacidad_camara_propia=5000`, costos X/Y, `capacidad_camion`, tiempos de viaje, `horizonte_dias=365`.

**Importar en AnyLogic:** arrastrá el `.xlsx` al modelo (crea un objeto `ExcelFile`), o creá una **Database** y "Import from Excel". Luego, en *On startup* de `Main`, cargá los depósitos:
```java
// On startup de Main (usando el objeto ExcelFile 'excel' apuntando a la hoja Depositos)
for (Deposito d : depositos) {
    int fila = d.getIndex() + 2;               // +2: encabezado en fila 1
    d.region                  = excel.getCellStringValue("Depositos", fila, 3);
    d.tarifaAlmacenamiento    = excel.getCellNumericValue("Depositos", fila, 4);
    d.capacidadMaxima         = excel.getCellNumericValue("Depositos", fila, 5);
    d.costoTransporteUnitario = excel.getCellNumericValue("Depositos", fila, 6);
}
// Perfil mensual -> double[12] produccionMensual
for (int m = 0; m < 12; m++)
    produccionMensual[m] = excel.getCellNumericValue("ProduccionMensual", m + 2, 3);
```

---

## 5. Diseño de outputs (datasets y gráficos)

**Datasets (en Main, actualizados por `eventCostoDiario`):**
| Dataset | Contenido | update |
|---|---|---|
| `dsCostoAcumulado` | tiempo vs `costoTotalActual()` | `dsCostoAcumulado.add(time(DAY), costoTotalActual());` |
| `dsNivelCamara` | tiempo vs `camaraPropia.size()` | 1×/día |
| `dsCostoTransporte` / `dsCostoAlmacen` | series separadas | 1×/día |

**Por depósito:** en cada `Deposito`, un dataset `dsNivel` (tiempo vs `nivelActual`) y contadores `costoAlmacenAcum`, `costoTransporteAcum`.

**Gráficos (Analysis → Chart):**
- **Time Plot**: costo acumulado total + transporte + almacenamiento (3 series).
- **Time Plot**: nivel de cámara propia en el tiempo (con línea de referencia en 5000).
- **Bar Chart**: tn despachadas y costo por depósito al final del año (`for (Deposito d: depositos) barChart.addDataItem(...)`).
- **Pie/Bar** por región (Tucumán vs BsAs) del costo total.

---

## 6. Archivo `.alp` (mejor esfuerzo) — `model/LogisticaJugo.alp`

Adjunto un **esqueleto XML** con la jerarquía de agentes, parámetros, funciones,
diagrama y ambos experimentos.

**Aclaración honesta de viabilidad:** el formato `.alp` de AnyLogic 8.x usa IDs
internos, GUIDs, coordenadas de presentación y referencias que **el IDE genera y
valida al guardar**. Un `.alp` escrito a mano **no es confiable** — AnyLogic puede
rechazarlo o repararlo perdiendo partes. Tomalo como **mapa de referencia** de qué
crear, no como modelo ejecutable garantizado. La ruta segura es construir en el
IDE con el Entregable 1 y pegar el Java del Entregable 2 (toma ~15-20 min).
