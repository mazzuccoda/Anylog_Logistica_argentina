# 1. Lógica de almacenamiento — cómo decide el modelo dónde y cuánto guardar

> Funciones fuente: `java/funciones_anylogic.java` (agentes `Deposito` y `Main`).
> Estructura de bloques: `MODELO_LOGISTICA_JUGO.md` §1.1–1.3.

## 1.1 Idea general

El jugo pasa por **dos "cajas" de almacenamiento** antes de llegar a destino
final, y las dos funcionan con la misma pregunta de fondo:

> *"¿Entra esto que quiero guardar? Y si entra, ¿cuánto me cuesta tenerlo
> guardado?"*

| Etapa | Dónde vive en el modelo | Capacidad | Quién la controla |
|---|---|---|---|
| **1. Cámara propia** | `Queue` en `Main`, parámetro `capacidadCamara` | 5.000 tn (fija, de la planta) | El bloque `Queue` mismo — si está llena, el `Source` no puede empujar más lotes |
| **2. Depósitos** | Población de 5 agentes `Deposito` (3 en Tucumán, 2 en Buenos Aires) | `capacidadMaxima` por depósito (cada uno distinto, viene del Excel) | Las funciones `puedeRecibir()` / `recibirLote()` del propio agente `Deposito` |

La cámara propia es un **colchón**: absorbe la producción diaria mientras se
decide a qué depósito mandar cada lote. Los depósitos son el **destino
final**, y cada uno lleva su propia contabilidad de nivel y de costo.

## 1.2 El agente `Deposito`, función por función

Cada uno de los 5 depósitos es una instancia del mismo agente, con sus propios
datos (tarifa, capacidad, costo de transporte desde la planta) cargados desde
`parametros_jugo.xlsx`.

### Parámetros (fijos durante toda la corrida, vienen del Excel)

| Parámetro | Tipo | Significado |
|---|---|---|
| `region` | String | `"Tucuman"` o `"BuenosAires"` — determina qué tiempo/costo de viaje aplica |
| `tarifaAlmacenamiento` | double | $ por tonelada por día que cobra **tener** jugo ahí guardado |
| `capacidadMaxima` | double | tn que entran como máximo en ese depósito |
| `costoTransporteUnitario` | double | $ por tonelada para **llegar** a ese depósito desde la planta (= X si es Tucumán, = Y si es Buenos Aires) |

### Variables (cambian con la simulación)

| Variable | Arranca en | Qué acumula |
|---|---|---|
| `nivelActual` | 0 | tn que hay guardadas *ahora mismo* en ese depósito |
| `costoAlmacenAcum` | 0 | $ acumulados de "alquiler" (tarifa × nivel × días) |
| `costoTransporteAcum` | 0 | $ acumulados de flete recibido |

### Las funciones, una por una

**`capacidadDisponible()` → double**
```java
double capacidadDisponible() {
    return capacidadMaxima - nivelActual;
}
```
Es la resta simple: "cuánto lugar libre me queda ahora". La usan otras
funciones (o vos, para graficar) para saber qué tan cerca está un depósito de
llenarse.

**`puedeRecibir(tn)` → boolean** — el semáforo de entrada
```java
boolean puedeRecibir(double tn) {
    return (nivelActual + tn) <= capacidadMaxima + 1e-9;
}
```
Es el **criterio de capacidad**: antes de mandar un lote a este depósito,
el modelo pregunta "si le sumo estas `tn`, ¿me paso del máximo?". El `1e-9`
es solo para no rechazar por errores de redondeo de coma flotante (ej. que
`999.9999999999` no cuente como mayor a `1000`).

> **Este es el único criterio "duro" de almacenamiento**: no hay negociación,
> no hay excepción. Si no entra, no entra — y el lote se queda esperando en la
> cámara propia (ver §1.4).

**`recibirLote(tn)` → void** — lo que pasa cuando el camión llega
```java
void recibirLote(double tn) {
    nivelActual += tn;
    costoTransporteAcum += tn * costoTransporteUnitario;
}
```
Se dispara al final del viaje (bloque `transporte`, *On exit*). Dos cosas
pasan a la vez: el nivel sube, y se carga el costo de flete de **esas** `tn`
(no se cobra por adelantado — se cobra cuando el lote efectivamente llega).

**`consumirDemanda(tn)` → void** — salida opcional
```java
void consumirDemanda(double tn) {
    nivelActual = max(0, nivelActual - tn);
}
```
Si en algún momento se agrega demanda/ventas desde el depósito (hoy el
modelo base no lo dispara todavía, queda como gancho), esta función baja el
nivel sin dejarlo nunca negativo.

**`acumularAlmacenamientoDia()` → void** — el "alquiler" de cada día
```java
void acumularAlmacenamientoDia() {
    costoAlmacenAcum += nivelActual * tarifaAlmacenamiento;
}
```
Se llama **una vez por día** desde `Main.eventCostoDiario` (evento cíclico,
cada 1 DAY), para **cada** depósito. La lógica es la de un alquiler: paga
tarifa por tonelada por cada día que el jugo estuvo ahí — no importa si entró
a la mañana o a la noche, ese día cuenta entero. Por eso el nivel que importa
es el nivel **al momento del corte diario**, no un promedio continuo.

**`costoMarginalUnitario(diasResidenciaEstimados)` → double** — la proyección de costo
```java
double costoMarginalUnitario(double diasResidenciaEstimados) {
    return costoTransporteUnitario + tarifaAlmacenamiento * diasResidenciaEstimados;
}
```
Esta es la función bisagra con el documento de entrega: **no mide un costo ya
ocurrido**, mide un costo *estimado* — "si mando 1 tn a este depósito hoy, y
se queda ahí `diasResidenciaEstimados` días, ¿cuánto me sale en total (flete +
alquiler)?". El modelo usa como estimador de `diasResidenciaEstimados` los
días que faltan hasta fin de año (`Main.diasHastaFinAnio()`), asumiendo en el
peor caso que el lote no se retira hasta el cierre del horizonte.

## 1.3 El costo total, agregado en `Main`

```java
double costoTotalActual() {
    double cTrans = 0, cAlm = 0;
    for (Deposito d : depositos) {
        cTrans += d.costoTransporteAcum;
        cAlm   += d.costoAlmacenAcum;
    }
    costoTransporteTotal = cTrans;
    costoAlmacenTotal    = cAlm;
    return cTrans + cAlm;
}
```
Es la función **objetivo** de todo el modelo: recorre los 5 depósitos, suma lo
que ya se gastó en flete más lo que ya se gastó en alquiler, y devuelve el
total. Es la que el Optimization Experiment intenta minimizar (§3 de
`MODELO_LOGISTICA_JUGO.md`).

## 1.4 Ejemplo numérico — un día en la vida de un depósito

Supongamos estos valores (ilustrativos — en tu Excel real reemplazá por los
que completes en `[COMPLETAR]`):

| Depósito | Región | Tarifa ($/tn/día) | Capacidad máx (tn) | Nivel al día 100 |
|---|---|---|---|---|
| Tucuman_C | Tucumán | 0,70 | 1.000 | 985 |

**Día 100, llega un camión con 30 tn (`capacidadCamion`):**

1. `puedeRecibir(30)` → `985 + 30 = 1015 > 1000` → **false**. No entra.
   El lote **no** se descarga en Tucuman_C — la asignación de destino (doc 02)
   ya lo habría filtrado antes de mandarlo, pero si por algún motivo llegara,
   este es el semáforo que lo frena.
2. Supongamos que sí entra un lote más chico, de 10 tn:
   `puedeRecibir(10)` → `985 + 10 = 995 ≤ 1000` → **true**.
   `recibirLote(10)` → `nivelActual = 995`, y si `costoTransporteUnitario =
   120`, se suma `10 × 120 = $1.200` a `costoTransporteAcum`.
3. Al cierre del día (`eventCostoDiario`), `acumularAlmacenamientoDia()` suma
   `995 × 0,70 = $696,5` a `costoAlmacenAcum` — el "alquiler" de tener esas
   995 tn guardadas ese día en particular.
4. Al día siguiente, si no entra ni sale nada, se vuelve a cobrar
   `995 × 0,70 = $696,5` — por eso tener stock parado **todos los días**
   suma, y es la razón por la que el modelo prefiere depósitos con tarifa
   baja cuando sabe que el jugo se va a quedar muchos días.

## 1.5 Qué pasa si **ningún** depósito tiene lugar

El documento maestro (§1.3, nota de "rebote por capacidad llena") contempla
este caso: si `asignarDestino()` no encuentra ningún depósito con
`puedeRecibir(tn) == true`, el lote **no sale de la cámara propia** — se queda
esperando ahí hasta que algún depósito libere espacio (por ejemplo, vía
`consumirDemanda`) y una corrida posterior de reintento lo pueda ubicar.

Esto convierte a la cámara propia en el **verdadero cuello de botella**: si se
llena (5.000 tn) mientras todos los depósitos también están llenos, la planta
no tiene dónde seguir apilando producción — el `Source` queda bloqueado. Es la
señal de que, en la vida real, faltaría capacidad de depósito o haría falta
bajar el ritmo de producción.

## 1.6 Resumen de criterios de almacenamiento

| # | Criterio | Función que lo aplica | ¿Duro o blando? |
|---|---|---|---|
| 1 | Capacidad física del depósito | `puedeRecibir(tn)` | **Duro** — si no entra, no entra |
| 2 | Costo de tener stock guardado (tarifa × días) | `acumularAlmacenamientoDia()` / `costoMarginalUnitario()` | Blando — no bloquea, pero encarece la decisión de destino (doc 02) |
| 3 | Costo de flete ya incurrido | `recibirLote()` → `costoTransporteAcum` | Se registra al llegar, no se puede "devolver" |
| 4 | Capacidad de la cámara propia (buffer previo) | `Queue capacidadCamara` | **Duro** — sin espacio en cámara, la planta no puede seguir produciendo hacia el proceso |

En síntesis: el almacenamiento **no elige** activamente nada — solo abre o
cierra la puerta (capacidad) y lleva la cuenta ($). La decisión activa de
**a qué depósito conviene mandar cada lote** es responsabilidad del
despacho, que se explica en el siguiente documento.
