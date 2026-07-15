# Anylog_Logistica_argentina

Modelo de simulación en **AnyLogic 8.x Personal Learning Edition (PLE)** de la
cadena de **producción y distribución de jugo** de una planta durante un año
(365 días), con optimización de costo total (transporte + almacenamiento).

## Flujo

```
Planta (Source)
   └─> Cámara propia (Queue, cap. 5.000 tn)
          └─> Preparar despacho (asigna destino de mínimo costo)
                 └─> Ruteo por depósito (SelectOutput5)
                        ├─ Tucumán: 3 depósitos   (costo transporte X)
                        └─ Buenos Aires: 2 depósitos (costo transporte Y)
                              └─> Transporte (Delay por ruta)
                                     └─> Llegada al depósito (nivel + costo)

Costo total anual = Σ transporte + Σ almacenamiento  →  MINIMIZAR
```

## Contenido del repo

| Archivo | Descripción |
|---|---|
| `MODELO_LOGISTICA_JUGO.md` | Documento maestro: estructura de bloques PML, código Java, Optimization Experiment, Excel, outputs y notas del .alp |
| `java/funciones_anylogic.java` | Código Java listo para copiar/pegar en el IDE (indica agente y firma de cada función) |
| `parametros_jugo.xlsx` | Plantilla de parámetros (hojas: Depositos, ProduccionMensual, Globales) para importar con el Excel connector |
| `gen_excel.py` | Script que regenera `parametros_jugo.xlsx` (requiere `openpyxl`) |
| `model/LogisticaJugo.alp` | Esqueleto XML del modelo (best-effort, ver disclaimer en el .md) |

## Cómo usar

1. Completar los valores `[COMPLETAR]` en `parametros_jugo.xlsx`.
2. Construir el modelo en el IDE de AnyLogic siguiendo la sección 1 del documento maestro.
3. Pegar las funciones de `java/funciones_anylogic.java` en los agentes indicados.
4. Importar el Excel y correr el experimento `Simulation` u `Optimization`.

> **Nota:** el `.alp` escrito a mano no es un modelo ejecutable garantizado
> (AnyLogic genera IDs/coordenadas al guardar). Es un mapa de referencia; la
> ruta confiable es armarlo en el IDE. Ver detalle en `MODELO_LOGISTICA_JUGO.md`.
