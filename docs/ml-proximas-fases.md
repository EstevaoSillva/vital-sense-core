# Proximas Fases - Roadmap ML

## Contexto
Fase 0 e Fase 1 foram concluídas:
- docs e caminhos operacionais corrigidos;
- runtime de stress definido oficialmente como heurístico em produção;
- fallback e rastreabilidade implementados.

Este documento define as próximas fases para elevar maturidade de ML no projeto.

## Fase 2 - Engenharia ML operacional

### Objetivo
Reduzir risco de execução e garantir consistência entre treino e inferência.

### Entregáveis
- Separação de dependências:
  - `requirements-runtime.txt` (API)
  - `requirements-ml.txt` (treino/export)
- Smoke tests automatizados:
  - burnout predictor com artefato presente/ausente;
  - stress pipeline validando estratégia efetiva e fallback.
- Validação de contrato:
  - `feature_order` de treino compatível com runtime;
  - validação de dimensões/schemas antes da inferência.

### Steps
1. Extrair do `requirements.txt` atual os pacotes necessários para runtime.
2. Criar arquivo de dependências específico para pipelines de treino.
3. Adicionar testes de smoke no app `employee` para burnout/stress.
4. Adicionar checagem de consistência de metadata (`feature_order`, ranges, versão).
5. Atualizar docs de setup para dois perfis: runtime e ML.

### Critérios de aceite
- API sobe sem stack de treino pesado.
- Testes de smoke passam no CI.
- Fallback de burnout e stress está coberto por testes.

## Fase 3 - Governança de artefatos e dados

### Objetivo
Padronizar ciclo de vida de datasets e modelos, evitando acoplamento com repositório.

### Entregáveis
- Política de armazenamento de dataset e artefatos grandes (fora do repo).
- Script de bootstrap para baixar dados/artefatos por checksum.
- Estrutura de versionamento de modelo e metadata de release.

### Steps
1. Definir backend para dados/artefatos (S3, MinIO ou LFS).
2. Remover dependência de datasets locais para execução padrão.
3. Criar script `download_ml_assets` com validação de hash.
4. Definir formato mínimo de metadata de release:
   - versão, data, features, métricas, origem do treino.
5. Documentar processo de publicação e rollback de modelo.

### Critérios de aceite
- Ambiente novo consegue preparar assets via script único.
- Repositório não depende de arquivos grandes para uso de API.
- Cada release de modelo possui metadata rastreável.

## Fase 4 - Integração opcional de stress model (se houver decisão de produto)

### Objetivo
Integrar modelo de stress no runtime sem quebrar o comportamento atual.

### Entregáveis
- Camada de inferência de stress por modelo com fallback para heurística.
- Contrato de input versionado para inferência de stress.
- Métricas operacionais de qualidade (uso de modelo vs fallback).

### Steps
1. Definir contrato de features do modelo de stress em produção.
2. Implementar loader de artefato com versionamento e validações.
3. Integrar no `risk_pipeline` sob feature flag.
4. Adicionar observabilidade:
   - estratégia efetiva;
   - motivo de fallback;
   - versão do modelo usada.
5. Executar rollout gradual com critério de rollback.

### Critérios de aceite
- Modo `model` funciona ponta a ponta com paridade de contrato.
- Fallback para heurística permanece estável e testado.
- Logs/telemetria permitem auditoria da origem da inferência.

## Sequenciamento recomendado
1. Fase 2 (obrigatória)
2. Fase 3 (obrigatória)
3. Fase 4 (somente se produto decidir integrar modelo de stress em runtime)
