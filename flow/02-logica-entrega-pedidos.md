# 2. Lógica de entrega — cómo elige el destino de cada lote según costo y capacidad operativa

> Funciones fuente: `java/funciones_anylogic.java` (agente `Main`, sección
> "ASIGNACIÓN GREEDY" y "ASIGNACIÓN POR PESOS").
> Bloques PML involucrados: `prepararDespacho` (Delay) → `ruteoDeposito`
> (SelectOutput5) → `transporte` (Delay) — ver `MODELO_LOGISTICA_JUGO.md` §1.3.

## 2.1 El momento de la decisión

Cada vez que un lote sale de la cámara propia, pasa por el bloque
`prepararDespacho`, y ahí — en su *On enter* — se ejecuta:

```java
asignarDestino(agent, usarOptimizacion);
```

Esta es **la** decisión de entrega del modelo: elegir, de los 5 depósitos
posibles (3 en Tucumán, 2 en Buenos Aires), cuál recibe este lote en
particular. Todo lo que viene después (ruteo, viaje, llegada) es mecánico —
una vez que `destino` quedó fijado en el lote, el resto es "seguir el cable".

```
prepararDespacho                 ruteoDeposito (SelectOutput5)
┌──────────────────────┐         ┌───────────────────────────┐
│ asignarDestino(lote,  │         │ salida i: agent.destino    │
│   usarOptimizacion)   │ ──────▶ │   == depositos.get(i) ?    │──▶ transporte ──▶ recibirLote()
│ → fija lote.destino   │         │ (5 ramas, una por depósito)│
└──────────────────────┘         └───────────────────────────┘
```

`asignarDestino` no inventa la lógica de elección — **delega** en una de dos
funciones, según el modo activo:

```java
boolean asignarDestino(Lote lote, boolean usarOptimizacion) {
    Deposito d = usarOptimizacion
               ? depositoPorPesos(lote.tn)
               : mejorDepositoGreedy(lote.tn);
    if (d == null) return false;   // sin capacidad -> el lote permanece en cámara
    lote.destino = d;
    return true;
}
```

| Modo | Función | Cuándo se usa | Qué mira |
|---|---|---|---|
| **Greedy** (por defecto, `usarOptimizacion = false`) | `mejorDepositoGreedy(tn)` | Simulación normal, sin correr el optimizador | **Costo estimado** de cada depósito, en el instante de la decisión |
| **Por pesos** (`usarOptimizacion = true`) | `depositoPorPesos(tn)` | Dentro del *Optimization Experiment* (OptQuest) | Un **peso** por depósito que el optimizador va ajustando entre corrida y corrida |

## 2.2 Modo Greedy — decisión por costo, lote por lote

```java
Deposito mejorDepositoGreedy(double tnLote) {
    Deposito mejor = null;
    double mejorCosto = Double.POSITIVE_INFINITY;
    double diasRes = diasHastaFinAnio();
    for (Deposito d : depositos) {
        if (!d.puedeRecibir(tnLote)) continue;          // 1) filtro de capacidad
        double c = d.costoMarginalUnitario(diasRes);    // 2) costo estimado
        if (c < mejorCosto) {                            // 3) me quedo con el más barato
            mejorCosto = c;
            mejor = d;
        }
    }
    return mejor;   // null si NINGÚN depósito tiene capacidad
}
```

Traducido a criollo, para cada lote hace tres pasos:

1. **Descarta** los depósitos que no tienen lugar (`puedeRecibir` — la
   capacidad operativa "dura" del documento 01).
2. De los que **sí** tienen lugar, le pregunta a cada uno "¿cuánto me costaría
   mandarte este lote?" — usando `costoMarginalUnitario(diasRes)` =
   `costoTransporteUnitario + tarifaAlmacenamiento × diasRes`.
3. Elige el que respondió el número **más bajo**.

El dato clave es `diasRes = diasHastaFinAnio()`: el modelo **no sabe** cuánto
tiempo real va a quedar guardado ese lote (depende de demanda futura, que hoy
no está modelada), así que usa como estimador conservador *"los días que
quedan hasta que se cierra el año"* — cuanto antes en el año, más días de
alquiler se proyectan; cuanto más cerca de fin de año, menos.

### Ejemplo numérico completo

Datos ilustrativos de los 5 depósitos (reemplazar por los reales del Excel):

| Depósito | Región | Tarifa almacén ($/tn/día) | Capacidad máx (tn) | Costo transporte ($/tn) |
|---|---|---|---|---|
| Tucuman_A | Tucumán | 0,80 | 2.000 | 120 (=X) |
| Tucuman_B | Tucumán | 0,90 | 1.500 | 120 (=X) |
| Tucuman_C | Tucumán | 0,70 | 1.000 | 120 (=X) |
| BsAs_A | Buenos Aires | 1,50 | 2.500 | 60 (=Y) |
| BsAs_B | Buenos Aires | 1,30 | 2.000 | 60 (=Y) |

**Caso A — día 100 del año** (`diasHastaFinAnio() = 365 − 100 = 265`,
todos los depósitos con lugar de sobra):

| Depósito | Cálculo `costoMarginalUnitario` | Resultado |
|---|---|---|
| Tucuman_A | `120 + 0,80 × 265` | **332,0** |
| Tucuman_B | `120 + 0,90 × 265` | 358,5 |
| Tucuman_C | `120 + 0,70 × 265` | **305,5** ← mínimo |
| BsAs_A | `60 + 1,50 × 265` | 457,5 |
| BsAs_B | `60 + 1,30 × 265` | 404,5 |

→ **Gana Tucuman_C.** Con 265 días por delante, lo que más pesa es la
**tarifa de almacenamiento**, y aunque Buenos Aires tiene el flete más barato
(60 vs 120), su tarifa de guarda es tan alta que, proyectada casi un año
entero, termina siendo la opción más cara.

**Caso B — día 300 del año** (`diasHastaFinAnio() = 365 − 300 = 65`, mismos
depósitos, todavía con lugar):

| Depósito | Cálculo | Resultado |
|---|---|---|
| Tucuman_A | `120 + 0,80 × 65` | 172,0 |
| Tucuman_B | `120 + 0,90 × 65` | 178,5 |
| Tucuman_C | `120 + 0,70 × 65` | 165,5 |
| BsAs_A | `60 + 1,50 × 65` | **157,5** |
| BsAs_B | `60 + 1,30 × 65` | **144,5** ← mínimo |

→ **Gana BsAs_B.** Con solo 65 días por delante, el peso de la tarifa de
almacenamiento se reduce mucho, y ahí el flete más barato de Buenos Aires
(60 vs 120) inclina la balanza.

**Esto es exactamente el comportamiento que se busca**: el modelo no tiene
una regla fija tipo "siempre mandar a Tucumán" — recalcula la cuenta **lote
por lote**, y la mezcla óptima de destinos cambia sola a lo largo del año
según cuánto tiempo de almacenamiento le queda por delante a cada envío.

**Caso C — capacidad manda por encima del costo.** Supongamos que en el
Caso B, BsAs_B ya tiene `nivelActual = 1.985` tn de las 2.000 de capacidad, y
llega un lote de 30 tn (`capacidadCamion`):

- `BsAs_B.puedeRecibir(30)` → `1985 + 30 = 2015 > 2000` → **false**, se
  descarta *aunque sea el más barato*.
- El bucle sigue con el resto: entre los que quedan, `BsAs_A` (157,5) es el
  siguiente más barato con lugar → **gana BsAs_A**.

Esto muestra el orden de prioridades real del algoritmo: **primero
capacidad, después costo** — nunca al revés. Un depósito lleno queda
afuera de la comparación sin importar cuán barato sea.

**Caso D — nadie tiene lugar.** Si los 5 depósitos devuelven
`puedeRecibir(tn) == false`, el bucle termina sin haber actualizado `mejor`,
y `mejorDepositoGreedy` devuelve `null`. `asignarDestino` propaga ese `null`
como `return false`, y el lote **se queda en la cámara propia** esperando a
que se libere lugar en algún depósito.

## 2.3 Modo por pesos — la política que ajusta OptQuest

```java
Deposito depositoPorPesos(double tnLote) {
    Deposito elegido = null;
    double mejorPeso = Double.NEGATIVE_INFINITY;
    for (int i = 0; i < depositos.size(); i++) {
        Deposito d = depositos.get(i);
        if (!d.puedeRecibir(tnLote)) continue;      // 1) mismo filtro de capacidad
        if (pesoDeposito[i] > mejorPeso) {           // 2) me quedo con el de mayor peso
            mejorPeso = pesoDeposito[i];
            elegido = d;
        }
    }
    return elegido;
}
```

Estructuralmente es igual al greedy (filtra por capacidad, después
compara), pero **no mira el costo directamente** — compara un arreglo
`pesoDeposito[0..4]`, uno por depósito, que **no lo fija el código**: lo va
probando el *Optimization Experiment* (OptQuest), corrida tras corrida.

### Por qué esto puede ganarle al greedy

El greedy es **miope**: en cada decisión mira sólo el costo de *ese* lote,
sin pensar en lo que va a pasar después. Puede, por ejemplo, llenar el
depósito más barato (Tucuman_C) durante los primeros meses del año porque
siempre gana la comparación — y dejarlo sin lugar para cuando en temporada
alta de producción realmente lo necesitaría.

OptQuest, en cambio, corre la simulación **completa** (365 días) muchas
veces, cada vez con una combinación distinta de pesos, y se queda con la
combinación que minimizó `costoTotalActual()` al final del año — es decir,
encuentra una **política global**, no una serie de decisiones miopes.

**Ejemplo:** supongamos que, tras varias iteraciones, OptQuest converge a:

| Índice `i` | Depósito | `pesoDeposito[i]` |
|---|---|---|
| 0 | Tucuman_A | 0,20 |
| 1 | Tucuman_B | 0,10 |
| 2 | Tucuman_C | 0,30 |
| 3 | BsAs_A | 0,90 |
| 4 | BsAs_B | 0,40 |

Con estos pesos, **mientras haya capacidad**, todos los lotes del año van a
`BsAs_A` (peso 0,90, el más alto) — sin importar si es día 10 o día 360, y
sin recalcular ningún costo lote por lote. Sólo cuando `BsAs_A` se llena,
`puedeRecibir` lo excluye y el algoritmo pasa al segundo peso más alto
disponible (`BsAs_B`, 0,40). Así, **la variación de la mezcla de destinos a
lo largo del año no viene de recalcular costos, sino de que se van llenando
los depósitos de mayor peso** y el tráfico se derrama hacia los siguientes.

Para activar este modo hay que setear en el experimento
`root.usarOptimizacion = true` (ver `MODELO_LOGISTICA_JUGO.md` §3).

## 2.4 Capacidad operativa: más allá de "¿entra o no entra?"

El filtro `puedeRecibir(tn)` es el límite de capacidad **de depósito**, pero
el modelo contempla (o deja preparado) otros tres límites operativos que
también condicionan la entrega:

| Restricción operativa | Dónde vive | Efecto sobre la entrega |
|---|---|---|
| **Tamaño de lote / camión** (`capacidadCamion`) | Parámetro de `Main`, usado para setear `Lote.tn` en el `Source` | Define **de a cuánto** se despacha por vez — un valor alto agrupa producción en menos decisiones (menos comparaciones de costo, pero cada una "pesa" más contra la capacidad restante del depósito elegido) |
| **Tiempo de viaje por ruta** (`tiempoViaje(d)`) | Función de `Main`, usada como *Delay time* del bloque `transporte` | No cambia a **qué** depósito va el lote, pero sí **cuándo llega** — Tucumán y Buenos Aires tienen tiempos distintos (`tiempoViajeTucuman` / `tiempoViajeBsAs`), lo que afecta cuánto tiempo el lote "vive" en tránsito antes de empezar a generar costo de almacenamiento |
| **Flota de camiones concurrente** (opcional, no activado por defecto) | `ResourcePool camiones` + bloques `Seize`/`Release` sugeridos entre `ruteoDeposito` y `transporte` | Si se agrega, limita **cuántos lotes pueden viajar al mismo tiempo** — un lote elegido por costo puede quedar esperando un camión libre aunque el depósito destino tenga lugar de sobra |
| **Capacidad de la cámara propia** | `Queue capacidadCamara` (ver doc 01 §1.1) | Si está llena, no hay lotes nuevos para despachar — la entrega se frena "río arriba", no en el despacho mismo |

```java
double tiempoViaje(Deposito d) {
    if (d.region.equals("Tucuman"))    return tiempoViajeTucuman;
    else                                 return tiempoViajeBsAs;
}
```

Esta función es simple a propósito: la variable que de verdad decide costo y
destino es `costoMarginalUnitario` / `pesoDeposito`; el tiempo de viaje sólo
determina **cuándo** ese lote empieza a sumar costo de almacenamiento una vez
llega (a través de `recibirLote` → `acumularAlmacenamientoDia`).

## 2.5 El ruteo físico — SelectOutput5

Una vez que `lote.destino` ya está fijado por `asignarDestino`, el bloque
`ruteoDeposito` (`SelectOutput5`) sólo necesita **5 condiciones**, una por
salida:

```
salida 0: agent.destino == depositos.get(0)   // Tucuman_A
salida 1: agent.destino == depositos.get(1)   // Tucuman_B
salida 2: agent.destino == depositos.get(2)   // Tucuman_C
salida 3: agent.destino == depositos.get(3)   // BsAs_A
salida 4: agent.destino == depositos.get(4)   // BsAs_B
```

No hay lógica de negocio acá — es pura mecánica de enrutamiento. Toda la
inteligencia ya se ejecutó un paso antes, en `asignarDestino`.

## 2.6 Resumen — árbol de decisión de la entrega

```
¿Hay lote para despachar?
        │
        ▼
¿usarOptimizacion == true?
   │                  │
   NO                 SÍ
   │                  │
   ▼                  ▼
mejorDepositoGreedy   depositoPorPesos
   │                  │
   ├─ filtra por puedeRecibir(tn) en ambos modos
   │
   ├─ greedy: compara costoMarginalUnitario(diasHastaFinAnio())
   │          → gana el MENOR costo
   │
   └─ pesos:  compara pesoDeposito[i] (ajustado por OptQuest)
              → gana el MAYOR peso
        │
        ▼
¿Encontró un depósito con lugar?
   │                  │
   SÍ                 NO
   │                  │
   ▼                  ▼
lote.destino = d      lote se queda en cámara propia
   │                  (reintenta más adelante)
   ▼
ruteoDeposito (SelectOutput5) → transporte (delay según región) → recibirLote()
```

**En una frase:** la entrega elige, entre los depósitos *con lugar*, el que
resulte más barato en el modo greedy (recalculando en cada lote según cuánto
tiempo de almacenamiento le queda al año), o el de mayor peso en el modo
optimizado (donde el "aprendizaje" de qué conviene ya viene precalculado por
OptQuest tras simular el año completo muchas veces) — y la capacidad
(depósito, cámara, y opcionalmente flota de camiones) siempre actúa como
filtro previo, nunca como criterio de desempate por costo.
