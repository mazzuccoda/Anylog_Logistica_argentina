/* =============================================================================
 *  MODELO LOGÍSTICA DE JUGO - FUNCIONES JAVA PARA ANYLOGIC 8.x PLE
 * =============================================================================
 *  Cada bloque indica EN QUÉ AGENTE se define la función y su firma exacta.
 *  Copiá el CUERPO (lo que está entre llaves) dentro de una "Function" creada
 *  en el editor de AnyLogic con esa firma (nombre, retorno y argumentos).
 *  No pegues estos comentarios de encabezado dentro del IDE.
 * ============================================================================= */


/* -----------------------------------------------------------------------------
 * AGENTE: Deposito
 * Parámetros (Parameters) que debe tener el agente Deposito:
 *   - region                 : String   ("Tucuman" | "BuenosAires")
 *   - tarifaAlmacenamiento    : double   ($/tn/día)
 *   - capacidadMaxima         : double   (tn)
 *   - costoTransporteUnitario : double   ($/tn)  -> = X para Tucuman, Y para BsAs
 * Variables (Variables) del agente Deposito:
 *   - nivelActual             : double = 0   (tn almacenadas ahora)
 *   - costoAlmacenAcum        : double = 0   ($ acumulados por almacenamiento)
 *   - costoTransporteAcum     : double = 0   ($ acumulados por transporte recibido)
 * -----------------------------------------------------------------------------*/

// Function: capacidadDisponible()  -> return double
double capacidadDisponible() {
    return capacidadMaxima - nivelActual;
}

// Function: puedeRecibir(double tn)  -> return boolean
boolean puedeRecibir(double tn) {
    return (nivelActual + tn) <= capacidadMaxima + 1e-9;
}

// Function: recibirLote(double tn)  -> return void
//   Se llama cuando llega un lote al depósito (tras el transporte).
void recibirLote(double tn) {
    nivelActual += tn;
    costoTransporteAcum += tn * costoTransporteUnitario;
}

// Function: consumirDemanda(double tn)  -> return void
//   Opcional: si modelás salida/consumo desde el depósito.
void consumirDemanda(double tn) {
    nivelActual = max(0, nivelActual - tn);
}

// Function: acumularAlmacenamientoDia()  -> return void
//   Llamada 1 vez por día por un Event cíclico (ver Main.eventCostoDiario).
void acumularAlmacenamientoDia() {
    costoAlmacenAcum += nivelActual * tarifaAlmacenamiento;
}

// Function: costoMarginalUnitario(double diasResidenciaEstimados) -> return double
//   Costo estimado de mandar 1 tn a ESTE depósito: transporte + almacenamiento
//   proyectado sobre los días que se estima que quedará almacenada.
double costoMarginalUnitario(double diasResidenciaEstimados) {
    return costoTransporteUnitario + tarifaAlmacenamiento * diasResidenciaEstimados;
}


/* -----------------------------------------------------------------------------
 * AGENTE: Main
 * Colecciones / objetos que Main debe tener:
 *   - depositos : population del agente Deposito (5 instancias)  [o] AgentList<Deposito>
 *   - camaraPropia : Queue (bloque PML)  capacity = 5000
 *   - Parameters de Main:
 *       capacidadCamara      : double = 5000
 *       capacidadCamion      : double        (tn por viaje)
 *       diasHastaFinAnio()   : ver función abajo
 *   - Variables de Main:
 *       costoTransporteTotal : double = 0
 *       costoAlmacenTotal    : double = 0
 * -----------------------------------------------------------------------------*/

// Function: diasHastaFinAnio()  -> return double
//   Días restantes del horizonte anual desde el instante actual (para estimar
//   la residencia de un lote que entra hoy y se queda hasta fin de año).
double diasHastaFinAnio() {
    double horizonteDias = 365.0;
    return max(1.0, horizonteDias - time(DAY));
}

// Function: costoTotalActual()  -> return double
//   Objetivo a minimizar. Suma transporte + almacenamiento de todos los depósitos.
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

/* -----------------------------------------------------------------------------
 * ASIGNACIÓN GREEDY (heurística de mínimo costo) - AGENTE Main
 * Elige, para un lote de 'tnLote' toneladas, el depósito con menor costo
 * marginal unitario ENTRE los que tienen capacidad disponible suficiente.
 * Devuelve null si ningún depósito puede recibir (el lote queda en cámara).
 * -----------------------------------------------------------------------------*/

// Function: mejorDepositoGreedy(double tnLote)  -> return Deposito
Deposito mejorDepositoGreedy(double tnLote) {
    Deposito mejor = null;
    double mejorCosto = Double.POSITIVE_INFINITY;
    double diasRes = diasHastaFinAnio();
    for (Deposito d : depositos) {
        if (!d.puedeRecibir(tnLote)) continue;
        double c = d.costoMarginalUnitario(diasRes);
        if (c < mejorCosto) {
            mejorCosto = c;
            mejor = d;
        }
    }
    return mejor;
}

/* -----------------------------------------------------------------------------
 * ASIGNACIÓN POR PESOS (para el Optimization Experiment / OptQuest) - Main
 * Las variables de decisión son pesos w[i] >= 0 (uno por depósito). El lote se
 * dirige al depósito de MAYOR peso que aún tenga capacidad. Así OptQuest, al
 * variar los pesos, explora distintas políticas de asignación.
 *   - Parameter de Main: double[] pesoDeposito   (tamaño 5)  <- lo setea OptQuest
 * -----------------------------------------------------------------------------*/

// Function: depositoPorPesos(double tnLote)  -> return Deposito
Deposito depositoPorPesos(double tnLote) {
    Deposito elegido = null;
    double mejorPeso = Double.NEGATIVE_INFINITY;
    for (int i = 0; i < depositos.size(); i++) {
        Deposito d = depositos.get(i);
        if (!d.puedeRecibir(tnLote)) continue;
        if (pesoDeposito[i] > mejorPeso) {
            mejorPeso = pesoDeposito[i];
            elegido = d;
        }
    }
    // Fallback: si el de mayor peso no entra, ya se filtró por capacidad arriba.
    return elegido;
}

/* -----------------------------------------------------------------------------
 * DISPATCH: se ejecuta al despachar un lote desde la cámara propia.
 * Uso típico: en la acción "On enter" de un bloque, o disparado por un Event
 * de despacho diario. Marca el destino en el agente lote y devuelve si pudo.
 *   - El agente "Lote" debe tener: Parameter tn (double) y Variable Deposito destino
 * -----------------------------------------------------------------------------*/

// Function: asignarDestino(Lote lote, boolean usarOptimizacion) -> return boolean
boolean asignarDestino(Lote lote, boolean usarOptimizacion) {
    Deposito d = usarOptimizacion
               ? depositoPorPesos(lote.tn)
               : mejorDepositoGreedy(lote.tn);
    if (d == null) return false;   // sin capacidad -> el lote permanece en cámara
    lote.destino = d;
    return true;
}

// Function: tiempoViaje(Deposito d)  -> return double   [en HORAS o usar unidad del bloque Delay]
//   Devolvé el tiempo de transporte según la región del depósito.
double tiempoViaje(Deposito d) {
    if (d.region.equals("Tucuman"))    return tiempoViajeTucuman;    // Parameter Main
    else                                return tiempoViajeBsAs;       // Parameter Main
}
