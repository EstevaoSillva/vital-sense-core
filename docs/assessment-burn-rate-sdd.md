# SDD - Assessment v2 para Burn Rate sem Autoatribuicao Direta

## 1) Contexto

Hoje o risco de burnout pode carregar vies de auto-percepcao quando a pessoa tenta traduzir "como se sente" para um valor global.

Este SDD define um questionario com itens observaveis e um calculo objetivo de `burn_rate` por media ponderada de dominios relevantes.

## 2) Objetivo

- Remover autoatribuicao direta de burnout.
- Calcular `burn_rate` a partir de respostas comportamentais com escala padronizada.
- Manter compatibilidade com o fluxo atual de backend (`BurnoutAssessment`, `RiskInference`).

## 3) Criterios de Sucesso

- Nao existe pergunta do tipo "qual seu nivel de burnout?".
- Todo item usa janela temporal fixa: "nos ultimos 7 dias".
- Todo item usa escala 1..5 com ancora de frequencia.
- `composite_score` e calculado por formula deterministica.
- Resultado segue para inferencia de risco sem quebrar contratos existentes.

## 4) Especificacao do Questionario (Assessment v2)

### 4.1 Escala de resposta (todos os itens)

- `1 = Nunca`
- `2 = Raramente`
- `3 = As vezes`
- `4 = Frequentemente`
- `5 = Quase sempre`

### 4.2 Dominios, itens e mapeamento tecnico

1. Exaustao (`exhaustion_score`, peso dominio `0.30`)
- "Nos ultimos 7 dias, terminei o dia de trabalho mentalmente esgotado(a)."

2. Cinismo/distanciamento (`cynicism_score`, peso dominio `0.20`)
- "Nos ultimos 7 dias, senti distanciamento emocional do trabalho."

3. Eficacia percebida (`efficacy_score`, peso dominio `0.15`, inversao)
- "Nos ultimos 7 dias, consegui concluir minhas atividades com senso de eficacia."

4. Pressao por prazos/carga (`deadline_pressure_score`, peso dominio `0.15`)
- "Nos ultimos 7 dias, trabalhei sob pressao intensa de prazo."

5. Suporte da lideranca (`manager_support_score`, peso dominio `0.10`, inversao)
- "Nos ultimos 7 dias, recebi suporte util da minha lideranca quando precisei."

6. Equilibrio vida-trabalho (`work_life_balance_score`, peso dominio `0.10`, inversao)
- "Nos ultimos 7 dias, consegui manter equilibrio saudavel entre trabalho e vida pessoal."

### 4.3 Regras de consistencia de preenchimento

- Todos os campos acima sao obrigatorios.
- Cada valor deve estar em `1..5`.
- Payload fora da escala retorna `400`.

## 5) Regra de Calculo do Burn Rate

### 5.1 Normalizacao base

Para cada item `x` em escala `1..5`:

`norm(x) = (x - 1) / 4`

### 5.2 Fatores invertidos (itens protetivos)

- `efficacy_inverse = 1 - norm(efficacy_score)`
- `manager_support_penalty = 1 - norm(manager_support_score)`
- `work_life_penalty = 1 - norm(work_life_balance_score)`

### 5.3 Formula final v2

`burn_rate_v2 = clamp01(`  
`  0.30 * norm(exhaustion_score)`  
`+ 0.20 * norm(cynicism_score)`  
`+ 0.15 * efficacy_inverse`  
`+ 0.15 * norm(deadline_pressure_score)`  
`+ 0.10 * manager_support_penalty`  
`+ 0.10 * work_life_penalty`  
`)`

### 5.4 Classificacao inicial de risco

- `low`: `< 0.45`
- `moderate`: `>= 0.45` e `< 0.70`
- `high`: `>= 0.70`

## 6) Contrato Tecnico (API e Persistencia)

### 6.1 Endpoint

- `POST /api/ml/burnout/assessment/`

### 6.1.1 Mudancas de interface publica (v2)

- `sleep_hours` e `work_hours_per_week` deixam de ser obrigatorios no assessment v2.
- Para compatibilidade de transicao, backend pode aceitar os campos legados, mas eles nao entram no calculo do `burn_rate_v2`.
- O identificador de regra passa a ser obrigatorio no retorno: `method_version = burnout-composite-v2`.

### 6.2 Request esperado (v2)

```json
{
  "source": "manual",
  "exhaustion_score": 4,
  "cynicism_score": 3,
  "efficacy_score": 2,
  "work_life_balance_score": 2,
  "manager_support_score": 3,
  "deadline_pressure_score": 4,
  "notes": "optional"
}
```

### 6.3 Response esperado

```json
{
  "employee_record_id": 123,
  "composite_score": 0.6625,
  "risk_level": "moderate",
  "method_version": "burnout-composite-v2",
  "factors": {
    "exhaustion": 0.75,
    "cynicism": 0.5,
    "efficacy_inverse": 0.75,
    "deadline_pressure": 0.75,
    "support_penalty": 0.5,
    "work_life_penalty": 0.75
  }
}
```

### 6.4 Persistencia em `BurnoutAssessment`

- `answers`: manter respostas brutas 1..5.
- `composite_score`: armazenar `burn_rate_v2`.
- `risk_level`: baixo/moderado/alto conforme thresholds.
- `method_version`: gravar `burnout-composite-v2`.
- `notes`: opcional.

## 7) Compatibilidade e Rollout

- Manter endpoint e estrutura principal para evitar quebra no app cliente.
- Conviver com historico `v1` e novo `v2` via `method_version`.
- Em `risk inference`, continuar usando o ultimo `BurnoutAssessment.composite_score`.
- Monitorar distribuicao de score de `v1` vs `v2` por 2 ciclos de avaliacao antes de recalibrar thresholds.

## 8) Test Plan (aceitacao)

1. Validacao de input
- Rejeitar valores fora de `1..5`.
- Rejeitar ausencia de campos obrigatorios.

2. Formula
- Caso minimo (todos = 1): score esperado `0.0`.
- Caso maximo em risco (exaustao/cinismo/pressao altos e protetivos baixos): score proximo de `1.0`.
- Confirmar inversao correta de `efficacy`, `manager_support`, `work_life_balance`.

3. Contrato e persistencia
- `method_version` deve retornar e persistir como `burnout-composite-v2`.
- `answers` deve guardar respostas originais sem normalizacao.

4. Integracao de risco
- `RiskInference` com `assessment_only` deve operar sem mudanca de contrato.
- `hybrid` continua usando regra de fusao atual entre stress e burnout.

## 9) Assumptions e Defaults

- Idioma do produto: portugues.
- Escala padrao do assessment: frequencia comportamental 1..5.
- Pesos definidos neste documento sao o baseline inicial de producao.
- Sem criacao de novo endpoint nesta fase; foco em evolucao da versao de metodo.
