# Gateway Selector – Motor de Reglas

Este documento resume el diseño y uso del motor de reglas que define cómo se enrutan las operaciones de **Pay-out** hacia los distintos **Gateways**.

---

## 📐 Arquitectura General

- **Ruleset**: colección de reglas. Solo puede haber **un ruleset activo** a la vez.
- **Regla**: contiene:

  - `condition_type` / `condition_value` / `condition_json`: definición de la condición de la regla.
  - `priority`: entero único que define el orden de evaluación (ascendente).
  - `action`: instrucción a ejecutar si la regla matchea.
  - `enabled`: flag de habilitación.

- **Compilador**:

  - Normaliza y valida las reglas.
  - Convierte JSON → predicados (`Matcher`) optimizados con short-circuit.
  - Expande alias (`USER`, `PIX_KEY`, `PIX_KEY_TYPE`) a reglas completas basadas en `VALUE_IN`.
  - Precalcula acciones (ej. pesos normalizados en `WEIGHTED`).

- **Selector**:

  - Evalúa reglas en orden de prioridad.
  - Ejecuta la acción asociada.
  - Si ninguna regla aplica, usa `default_gateway` (si está configurado).
  - Retorna `(gateway, decision)`.

---

## 🧱 Matchers disponibles

Los matchers son piezas reutilizables que inspeccionan el **contexto (`ctx`)** de la request y devuelven `True`/`False`.

### Alias simples

- **USER** → equivale a `VALUE_IN` sobre `api_user_id`, tomando un único valor entero.
- **PIX_KEY** → equivale a `VALUE_IN` sobre `pix_key`, con un único string.
- **PIX_KEY_TYPE** → equivale a `VALUE_IN` sobre `pix_key_type`, con un único valor dentro del set permitido (`QRCODE_STATIC`, `QRCODE_DYNAMIC`, `EMAIL`, `PHONE`, `CPF`, `CNPJ`, `EVP`).

Ejemplo (regla simple en DB):

```
condition_type = "USER"
condition_value = "12345"
condition_json = NULL
```

Internamente se expande a:

```json
{
  "type": "VALUE_IN",
  "field": "api_user_id",
  "values": [12345],
  "coerce": "int"
}
```

### Compositores

- **ALL**

```json
{ "all": [ { ... }, { ... } ] }
```

Verdadero si todos los hijos lo son.

- **ANY**

```json
{ "any": [ { ... }, { ... } ] }
```

Verdadero si al menos un hijo lo es.

- **NONE**

```json
{ "none": [ { ... }, { ... } ] }
```

Verdadero si **ningún hijo** lo es.
(`none([])` = `True`)

---

### VALUE_IN

Valida que el valor de un campo esté en una lista de valores permitidos.

```json
{
  "type": "VALUE_IN",
  "impl": "v1",
  "field": "api_user_id",
  "values": [101, 102, 103],
  "coerce": "int"
}
```

- `field`: clave del `ctx` (soporta paths anidados "request.headers.x").
- `values`: lista blanca.
- `coerce`: "int" | "str" | "lower-str" | null.

---

### REGEX

Valida que el valor de un campo matchee un patrón regex.

```json
{
  "type": "REGEX",
  "impl": "v1",
  "field": "pix_key",
  "pattern": "@kamipay\\.io$",
  "mode": "search",
  "flags": ["IGNORECASE"],
  "coerce": "str",
  "max_len": 256
}
```

- `pattern`: expresión regular.
- `mode`: "search" | "match" | "fullmatch".
- `flags`: ej. IGNORECASE, MULTILINE.
- `coerce`: "str" | "lower-str".
- `max_len`: límite de longitud (protección ReDoS).

---

### AMOUNT_RANGE

Valida que el monto caiga dentro de un rango.

```json
{
  "type": "AMOUNT_RANGE",
  "impl": "v1",
  "field": "amount",
  "coerce": "int",
  "scale": 2,
  "min": "10.00",
  "max": "1000.00",
  "min_inclusive": true,
  "max_inclusive": false
}
```

- `field`: campo de monto.
- `coerce`: "int" (minor units) o "decimal".
- `scale`: factor para convertir minor units (ej. 12345 → 123.45 con scale=2).
- `min` / `max`: límites como string decimal.
- `min_inclusive` / `max_inclusive`: control de inclusividad.

---

### TIME_WINDOW

Valida que la hora actual (o `ctx.now`) caiga dentro de una ventana.

```json
{
  "type": "TIME_WINDOW",
  "impl": "v1",
  "tz": "America/Sao_Paulo",
  "start": "09:00",
  "end": "18:00",
  "days_of_week": ["mon", "tue", "wed", "thu", "fri"]
}
```

- `tz`: zona horaria IANA.
- `start` / `end`: límites horarios (HH\:MM o HH\:MM\:SS).
- `days_of_week`: opcional, restringe a ciertos días (mon..sun).
- Soporta cruces de medianoche (ej. 22:00–06:00).

---

## 🎬 Acciones

Cada regla define una `action`:

### FIXED

Siempre retorna un gateway específico.

```json
{
  "route": "FIXED",
  "gateway": "CELCOIN"
}
```

### WEIGHTED

Distribuye requests entre varios gateways, con opción de _sticky_.

```json
{
  "route": "WEIGHTED",
  "weights": {
    "CELCOIN": 60,
    "E2E": 40
  },
  "sticky_by": "api_user_id"
}
```

- `weights`: porcentajes enteros normalizados (100 total).
- `sticky_by`: campo del `ctx` que define stickiness (ej. api_user_id).

### DENY

Bloquea la request si la condición se cumple.

```json
{
  "route": "DENY",
  "reason_code": "blacklist"
}
```

---

## ⚙️ Ejemplo de Ruleset Completo

```json
{
  "id": 42,
  "version": 3,
  "default_gateway": "CELCOIN",
  "rules": [
    {
      "id": 1,
      "priority": 1,
      "enabled": true,
      "condition_type": "USER",
      "condition_value": "999",
      "action": {
        "route": "DENY",
        "reason_code": "blocked_user"
      }
    },
    {
      "id": 2,
      "priority": 2,
      "enabled": true,
      "condition_type": "PIX_KEY",
      "condition_value": "mati@kamipay.io",
      "action": {
        "route": "FIXED",
        "gateway": "E2E"
      }
    },
    {
      "id": 3,
      "priority": 3,
      "enabled": true,
      "condition_type": "ADVANCED",
      "condition_json": {
        "all": [
          { "type": "VALUE_IN", "field": "pix_key_type", "values": ["EVP"] },
          {
            "type": "AMOUNT_RANGE",
            "field": "amount",
            "coerce": "int",
            "scale": 2,
            "min": "0.00",
            "max": "1000.00",
            "min_inclusive": true,
            "max_inclusive": true
          }
        ]
      },
      "action": {
        "route": "WEIGHTED",
        "weights": { "CELCOIN": 70, "E2E": 30 },
        "sticky_by": "api_user_id"
      }
    }
  ]
}
```

---

## 🔍 Debug & Observabilidad

- El compilador soporta `debug=True`: envuelve los matchers con `DebugWrap` para loggear evaluaciones, tiempos y short-circuits.
- Hook `on_decision` en el selector: permite registrar métricas y logs sin exponer PII.

Ejemplo de log con debug:

```
[rules-debug] path=RULE[42].ALL matcher=ALL result=True time_ms=0.041 ctx_keys=['api_user_id','pix_key']
```
