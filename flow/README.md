# `flow/` — Cómo piensa el modelo

Esta carpeta explica, en criollo y con ejemplos numéricos, las **dos decisiones
inteligentes** que toma la simulación. No repite la estructura de bloques (eso
está en `MODELO_LOGISTICA_JUGO.md`) — se enfoca en la **lógica de decisión**:
qué pregunta el modelo, en qué orden, y por qué elige lo que elige.

| Documento | Pregunta que responde |
|---|---|
| [`01-logica-almacenamiento.md`](./01-logica-almacenamiento.md) | ¿Dónde y cuánto se guarda? ¿Cuándo un depósito "dice que no"? ¿Cómo se calcula el costo de tener jugo guardado? |
| [`02-logica-entrega-pedidos.md`](./02-logica-entrega-pedidos.md) | De todos los depósitos posibles, ¿a cuál se despacha cada lote? ¿Cómo entran el costo de transporte y la capacidad operativa (camiones, depósitos, cámara) en esa elección? |

## Mapa mental rápido

```
                     ┌─────────────────────┐
                     │   PLANTA (Source)   │  produce jugo según estación
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │  CÁMARA PROPIA      │  buffer temporal, cap. 5.000 tn
                     │  (Queue)            │  → doc 01 (almacenamiento, etapa 1)
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │  PREPARAR DESPACHO  │  decide destino (greedy u OptQuest)
                     │  asignarDestino()   │  → doc 02 (entrega / dispatch)
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │  RUTEO + TRANSPORTE │  camino a Tucumán o Buenos Aires
                     └──────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │  DEPÓSITO DESTINO   │  buffer final, cap. propia por depósito
                     │  recibirLote()      │  → doc 01 (almacenamiento, etapa 2)
                     └─────────────────────┘
```

La **cámara propia** y los **5 depósitos** son, en el fondo, el mismo tipo de
decisión de almacenamiento (¿hay lugar?, ¿cuánto cuesta tenerlo ahí?) aplicada
en dos puntos distintos de la cadena. El **despacho** es la bisagra entre
ambos: decide, para cada lote que sale de la cámara, cuál de los 5 depósitos
"se lo gana" — y esa es la lógica de costo/capacidad operativa que pide el
segundo documento.
