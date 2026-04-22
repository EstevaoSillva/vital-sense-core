# Execucao Fase 1 - Alinhamento de Arquitetura ML

## Objetivo da fase
Definir e aplicar uma unica verdade para inferencia de stress em producao, reduzindo ambiguidades entre codigo de pesquisa e runtime da API.

## Decisao aplicada
- Estrategia oficial em producao: **heuristic**.
- Treino WESAD permanece **experimental/offline**.

## Implementacoes realizadas
1. Governanca de estrategia de stress no runtime:
   - Nova env var: `STRESS_RUNTIME_STRATEGY`.
   - Valor padrao: `heuristic`.
   - Qualquer valor diferente de `heuristic` cai em fallback documentado (`unsupported_runtime_strategy:<valor>`), mantendo estabilidade.

2. Transparencia no resultado de stress:
   - `feature_summary` agora inclui:
     - `runtime_strategy`
     - `requested_runtime_strategy`
     - `fallback_reason`
   - Permite auditoria de qual estrategia foi usada.

3. Documentacao de status:
   - `README` WESAD atualizado com aviso de que nao esta integrado ao runtime de producao.
   - `ml-auditoria.md` atualizado com status das fases.

## Arquivos alterados
- `burnout/employee/services/risk_pipeline.py`
- `burnout/employee/ml/stress/wesad/README.md`
- `burnout/docs/ml-auditoria.md`
- `burnout/employee/tests.py`

## Resultado da fase
- Ambiguidade de runtime resolvida: producao usa apenas heuristica.
- Modo `model` deixou de ser interpretado como parcialmente suportado; agora e explicitamente nao suportado e auditavel.
