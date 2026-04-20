# Burnout Core - Arquitetura e Fluxo de Funcionamento

Esta documentação descreve a arquitetura geral do projeto `burnout-core`, a estrutura de seus módulos (Django apps), o pipeline de Machine Learning (ML) incorporado e o fluxo principal de inferência de risco.

## 1. Visão Geral Arquitetural

O projeto é construído sobre o framework web **Django** com **Django REST Framework (DRF)**, e implementa um sistema de monitoramento de risco envolvendo estresse medido por wearables e burnouts calculados por meio de testes e questionários (assessments).

### 1.1 Stack Tecnológico Principal

- **Backend Web**: Django v4.2, DRF (REST APIs), SimpleJWT (Autenticação baseada em JWT).
- **Banco de Dados Relacional**: Postgres (definido em configuração genérica no arquivo `.env`), gerenciado via ORM do Django.
- **Armazenamento de Arquivos/Objetos**: AWS S3 ou MinIO compatível, configurado via `django-storages` + `boto3` para persistência (`AWS_S3_ENDPOINT_URL`).
- **Machine Learning**: TensorFlow (arquivos modelo originais usam TensorFlow Lite [stress_model.tflite](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/stress_model.tflite)), Numpy, Scikit-learn, XGBoost. 
- **Auditoria de Dados**: Rastreamento do histórico completo de todas as tabelas por meio do pacote `django-simple-history`.

---

## 2. Estrutura de Módulos (Apps)

A aplicação segue uma arquitetura modular dividida pelos seguintes apps principais:

### [core](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/services/risk_pipeline.py#38-44) (Fundação)
Fornece modelos base abstratos e utilitários que são compartilhados por outros serviços.
- Inclui o `ModelBase` responsável por campos comuns (IDS, UUIDs, carimbos de data/hora).

### `accounts` (Controle de Acesso)
Responsável pelo gerenciamento de usuários Customizados ([User](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/accounts/models.py#33-201) extensivo de `AbstractBaseUser`), Autenticação, Grupos e Permissões.
- **Modelos Principais**: [User](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/accounts/models.py#33-201), [AccountUserGroup](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/accounts/models.py#203-231), [RecoveryPassword](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/accounts/models.py#233-268).

### `organizations` (Gestão Organizacional)
Controla os metadados das corporações em nível organizacional.
- **Modelos Principais**: [Enterprise](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/organizations/models.py#7-38).

### `employee` (Domínio Central de Saúde e ML)
É o aplicativo onde a lógica core do negócio reside, cobrindo o tracking do funcionário até a modelagem de Machine Learning e processamento de risco.
- **[models.py](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/core/models.py)**:
  - [EmployeeRecord](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#8-30): Metadados demográficos e estado laboral da conta do usuário.
  - [WearableSample](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#32-101): Telemetria bruta (HR, EDA, TEMP, ACC, BVP, HRV) ingerida de ponta-a-ponta, salvando detalhes e confiabilidade do sinal.
  - [StressInferenceSnapshot](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#103-170): Registra a análise processada e o stress score ao longo de uma janela temporal, utilizando o engine ML.
  - [BurnoutAssessment](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#172-234): Armazena avaliações de formulários englobando fatores como exaustão, cinismo, e distúrbios de sono, resultando em um score quantitativo de Burnout.
  - [RiskTriageDecision](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#236-313): Tabela que unifica e cruza o *Stress* com o *Burnout* de modo a calcular o Risco Final.

---

## 3. Pipeline e APIs (Módulo de ML)

A infraestrutura possui *pipelines* em [employee/services/risk_pipeline.py](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/services/risk_pipeline.py) e se expõe via rotas na API em [employee/urls.py](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/urls.py):

- `POST /api/ml/stress/wearable/events/`: End-point resposável por ingerir *WearableSamples*.
- `POST /api/ml/burnout/assessment/`: End-point responsável por registrar novas submissões de questionários com score cognitivo.
- `POST /api/ml/burn-rate/predict/`: End-point para predições diretas usando o modelo AI.
- `POST /api/ml/risk/inference/`: Rota matriz de unificação do Risco Final. Calcula ativamente qual política matemática seguir.

---

## 4. Fluxo de Decisão e "Risk Inference Fallback"

O sistema possui uma lógica robusta (Strategy/Fallback) designada para extrair previsibilidade sólida mesmo na ausência de parâmetros.

A principal orquestração é disparada na chamada de cálculo de [RiskTriageDecision](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#236-313):

### 4.1 Processadores de Contextos Individuais

1. **Janelas de Stress (Wearables)**
   - O modo de runtime primário lê a variável ambiente `STRESS_RUNTIME_STRATEGY` (Padrão: `heuristic`).
   - Sinais são classificados em 0.0 a 1.0 utilizando métricas normalizadas de HR, EDA, TEMP e Inverso de HRV ponderados pelo `employee.services.risk_pipeline`.
   - Um limiar de qualidade de captura (`signal_quality`) penaliza avaliações não confiáveis.

2. **Avaliações Compostas (Burnout Composite)**
   - Transforma métricas psicosociais (exaustão, pressão de delivery, horas trabalhadas) em scores unificados `0..1`.

### 4.2 Triagem Híbrida (Fallback Flow)

Quando o endpoint principal `POST /api/ml/risk/inference/` é acionado para um usuário, as seguintes prioridades definem o *Final Score*:

1. **Modo `hybrid`** *(Preferencial)*
   - **Condição**: Existem os dados mais recentes tanto do Relógio/Wearable (`stress_score`) quanto de um Questionário válido (`burnout_score`).
   - **Cálculo**: `0.35 * stress_score + 0.65 * burnout_score`
   - **Confiança**: `high`
2. **Modo `assessment_only`** *(Fallback Estável)*
   - **Condição**: O sistema encontra apenas dados de questionário (`burnout_score`). Isso previne bloqueio com usuários cuja bateria acabou, tiraram o smartwatch ou seu dispositivo está desabilitado.
   - **Cálculo**: `burnout_score` puro.
   - **Confiança**: `moderate`
3. **Modo `wearable_only`** *(Fallback Crítico)*
   - **Condição**: Só há telemetria do relógio (`stress_score`), o funcionário está em tempo real mas nunca concluiu a avaliação ou o dado expirou.
   - **Cálculo**: `stress_score` puro.
   - **Confiança**: `low`
4. **Error State**
   - Na mais absoluta ausência de ambos os sinais (Apenas criação de conta virgem sem sincronizar dados), retorna-se erro `400` impossibilitando a tomada arbitrária de uma métrica falsa.

---

### Resumo Operacional

O `burnout-core` é um hub preditivo reativo. Ele coleta métricas passivamente ([WearableSample](file:///home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/models.py#32-101)s) e as processa no backend usando lógicas em python para entregar scores ponderados. Sua resiliência fundamental consiste em mesclar biometria transacional com avaliações laborais cadenciadas, adaptando suas recomendações baseadas inteiramente na confiança do sinal atual (via Estratégia de Fallback).
