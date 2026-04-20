# Risk Inference Fallback Strategy

## Context

O produto nao pode depender exclusivamente do wearable para calcular risco consolidado. Usuarios sem relogio, com sincronizacao atrasada ou com baixa qualidade de sinal ainda precisam receber um resultado consistente.

O wearable deve enriquecer a inferencia, nao bloquear a jornada.

### Status de runtime (atual)

- Estrategia oficial de stress em producao: `heuristic`.
- Controle por env var: `STRESS_RUNTIME_STRATEGY` (padrao `heuristic`).
- Qualquer valor diferente de `heuristic` e tratado como nao suportado e cai em fallback controlado para heuristica.
- Campos de rastreabilidade em `feature_summary`:
  - `runtime_strategy` (efetivo)
  - `requested_runtime_strategy` (solicitado por env)
  - `fallback_reason` (ex.: `unsupported_runtime_strategy:model`)

## Objetivo

Definir uma estrategia de fallback para `POST /api/ml/risk/inference/` sem quebrar compatibilidade com o app atual.

## Modos de inferencia

### `hybrid`

Quando existem `stress_score` e `burnout_score`.

- Formula inicial: `0.35 * stress_score + 0.65 * burnout_score`
- Confianca: `high`
- Uso: caminho preferencial

### `assessment_only`

Quando existe apenas `burnout_score`.

- Formula inicial: `final_score = burnout_score`
- Confianca: `moderate`
- Uso: fallback padrao para usuarios sem wearable

### `wearable_only`

Quando existe apenas `stress_score`.

- Formula inicial: `final_score = stress_score`
- Confianca: `low`
- Uso: fallback transitorio e trigger operacional

## Regras de selecao

1. Se os dois scores existirem: `hybrid`
2. Se apenas `burnout_score` existir: `assessment_only`
3. Se apenas `stress_score` existir: `wearable_only`
4. Se nenhum existir: erro `400`

## Fontes dos scores

`stress_score`:

- payload do endpoint
- ultimo `StressInferenceSnapshot`

`burnout_score`:

- payload do endpoint
- ultimo `BurnoutAssessment`

## Persistencia

`RiskTriageDecision` deve registrar:

- `inference_mode`
- `confidence_level`
- `details.input_availability`
- `details.context`

## Compatibilidade

O contrato atual continua valido. Campos adicionais opcionais:

- `inference_mode`
- `confidence_level`
