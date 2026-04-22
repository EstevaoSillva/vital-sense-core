# Auditoria ML - burnout-core

## Resumo
Esta auditoria cobre `burnout/employee/ml` e o acoplamento com runtime (`views`, `services`, `predictor`).
Foram encontrados desalinhamentos entre treino, documentacao e inferencia em producao, alem de riscos operacionais.

## Status de Execucao das Fases
- Fase 0: **Concluida**
  - Comandos/caminhos corrigidos em `TRAINING.md` e `README` WESAD.
  - Burnout predictor agora retorna `prediction_source` e `fallback_reason`.
- Fase 1: **Concluida**
  - Decisao aplicada: estrategia oficial de stress em producao = `heuristic`.
  - Governanca ativa por `STRESS_RUNTIME_STRATEGY`:
    - `heuristic`: modo suportado.
    - qualquer outro valor: fallback explicito para heuristica com motivo auditavel.
  - Fluxo WESAD marcado explicitamente como experimental/offline.
  - Teste automatizado cobrindo fallback de estrategia nao suportada.

## Estado Atual
- Burnout prediction tem pipeline de treino/export (`train_and_export.py`) e runtime (`predictor.py`) com fallback heuristico.
- Stress (WESAD) possui scripts de treino/export (`train_wesad_ml.py`, `export_tflite.py`), mas o runtime da API usa heuristica (`stress-heuristic-v1`).
- Existem ativos de pesquisa no repositorio (notebooks, PDFs, CSV de treino).

## Inconsistencias e Melhorias

| ID | Severidade | Arquivo(s) | Inconsistencia | Impacto | Melhoria recomendada |
|---|---|---|---|---|---|
| ML-01 | Critica | `employee/ml/burnout/TRAINING.md` | Comando de treino aponta para caminho incorreto (`python burnout/employee/ml/train_and_export.py`) em vez de `.../ml/burnout/train_and_export.py`. | Execucao falha/guia enganoso. | Corrigir comandos e validar copy/paste no README com comando real. |
| ML-02 | Critica | `employee/ml/stress/wesad/README.md` | Documentacao usa caminhos `ml/stress/...` que nao batem com estrutura atual (`employee/ml/stress/wesad/...`). | Onboarding quebrado para treino stress. | Padronizar exemplos de execucao com caminhos absolutos ao projeto. |
| ML-03 | Critica | `employee/services/risk_pipeline.py` vs `employee/ml/stress/wesad/*` | Stress em runtime esta heuristico (`stress-heuristic-v1`) e nao consome modelo treinado WESAD/TFLite. | Falsa percepcao de modelo em producao; risco de expectativa incorreta. | Definir uma unica verdade: integrar modelo real no runtime ou declarar explicitamente heuristica como estrategia oficial. |
| ML-04 | Alta | `employee/ml/stress/wesad/export_tflite.py` | Arquitetura fixa `input_dim=85`; features de treino podem divergir (PSD/HRV/EDA). | Incompatibilidade de checkpoint e export falhando em runtime de conversao. | Derivar `input_dim` do metadata de treino e validar dimensao antes de exportar. |
| ML-05 | Alta | `employee/ml/burnout/predictor.py` e `TRAINING.md` | Inconsistencia de diretorio de artefato (`employee/artifacts/...` vs `burnout/artifacts/...`). | Modelo pode cair em fallback sem visibilidade. | Unificar base path de artefatos e versionamento em variavel unica (`BURN_RATE_ARTIFACTS_BASE_DIR`). |
| ML-06 | Alta | `employee/ml/stress/wesad/train_wesad_ml.py` | Resolucao de dataset e comentarios citam estruturas diferentes, gerando ambiguidade. | Setup fragil e erros de caminho. | Simplificar estrategia de path discovery e documentar 1 fluxo oficial. |
| ML-07 | Media | `employee/ml/**` + `requirements*.txt` | Dependencias de runtime e treino fortemente acopladas (stack pesada com torch/tensorflow no runtime web). | Ambiente pesado, maior superficie de falha e deploy lento. | Separar `requirements-runtime.txt` e `requirements-ml.txt`. |
| ML-08 | Media | `employee/ml/burnout/predictor.py` | Fallback heuristico acontece silenciosamente em caso de artefato ausente. | Diagnostico dificil em producao. | Incluir log estruturado e flag de origem da predicao (`model` vs `heuristic`) em observabilidade. |
| ML-09 | Media | `employee/ml/burnout/*.ipynb`, `*.pdf`, CSV local | Material de pesquisa misturado com codigo de producao. | Ruido de repositorio e manutencao dificil. | Mover para `research/` ou `docs/ml/research/` e manter codigo operacional em pasta dedicada. |
| ML-10 | Media | `employee/ml/stress/dataset` (local) | Dataset local muito grande (ordem de dezenas de GB) para fluxo comum de dev. | Custos de armazenamento e replicacao; setup lento. | Politica de dados: armazenar dataset fora do repo (S3/LFS), manter somente instrucoes e checksums. |

## Steps de Resolucao (Roadmap)

### Fase 0 - Correcoes de confiabilidade (1-2 dias)
1. Corrigir caminhos e comandos em `TRAINING.md` (burnout) e `README.md` (WESAD).
2. Padronizar exemplos de execucao a partir da raiz do projeto.
3. Revisar variaveis de ambiente de artefatos e alinhar docs com runtime real.
4. Adicionar nota explicita no endpoint/metadata quando predicao estiver em fallback heuristico.

### Fase 1 - Alinhamento de arquitetura (3-5 dias)
1. Decidir oficialmente o modo de stress inference:
   - `A`: manter heuristica como producao.
   - `B`: integrar modelo treinado no runtime.
2. Se `B`, implementar carregamento de artefato stress com versionamento e contrato de input fixo.
3. Se `A`, arquivar scripts WESAD como experimental e remover ambiguidades de producao.
4. Corrigir `export_tflite.py` para validar e usar `input_dim`/schema via metadata.

### Fase 2 - Engenharia de ML operacional (3-5 dias)
1. Separar dependencias de runtime vs treino.
2. Criar smoke tests:
   - predictor burnout com artefato presente/ausente;
   - stress pipeline com contrato de feature.
3. Adicionar validacao automatica de consistencia:
   - `feature_order` treino == runtime;
   - dimensao de entrada do modelo == payload vetorizado.
4. Versionar metadata de treino com assinatura de schema.

### Fase 3 - Governanca e manutencao continua
1. Definir estrutura final:
   - `employee/ml/production` (codigo usado por API),
   - `employee/ml/research` (notebooks, papers).
2. Politica de artefatos e datasets grandes (S3/LFS + checksums + script de download).
3. Checklist de release de modelo (treino, metricas, aprovacao, rollout, rollback).

## Criterios de Aceite
- Documentacao executavel sem ajustes manuais de caminho.
- Runtime informa claramente se usou modelo treinado ou fallback.
- Contrato de features/dimensao validado automaticamente.
- Dependencias de producao desacopladas de stack de treino pesado.
- Pipeline de stress com status claro: heuristica oficial ou modelo integrado.

## Evidencias tecnicas (referencias)
- `burnout/employee/ml/burnout/TRAINING.md`
- `burnout/employee/ml/stress/wesad/README.md`
- `burnout/employee/services/risk_pipeline.py`
- `burnout/employee/ml/stress/wesad/export_tflite.py`
- `burnout/employee/ml/burnout/predictor.py`
- `burnout/employee/ml/stress/wesad/train_wesad_ml.py`

## Documento complementar
- Roadmap detalhado das proximas fases:
  - `burnout/docs/ml-proximas-fases.md`
