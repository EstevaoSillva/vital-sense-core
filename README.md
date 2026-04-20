# Burnout Core

API Django para cadastro de colaboradores e inferência de risco de burnout.

## O que existe hoje

O projeto está dividido em dois fluxos:

1. Fluxo legado de `burn_rate`:
   - treino offline de modelo tabular;
   - inferência online em `POST /api/ml/burn-rate/predict/`.
2. Novo pipeline de risco (MVP):
   - ingestão de sinais fisiológicos do wearable;
   - cálculo de score de stress;
   - assessment composto de burnout;
   - fusão final de risco com recomendação.

## Stack

- Python 3.11+
- Django 4.2
- Django REST Framework
- PostgreSQL
- Scikit-learn (modelo legado)
- PyTorch (treino de stress em `ml/stress`)

## Estrutura principal

- Projeto Django: `burnout/`
- App principal: `burnout/tech_employee/`
- Treino burnout legado: `burnout/tech_employee/ml/burnout/train_and_export.py`
- Inferência burnout legado: `burnout/tech_employee/ml/burnout/predictor.py`
- Pipeline de risco: `burnout/tech_employee/services/risk_pipeline.py`
- Treino stress/WESAD: `burnout/tech_employee/ml/stress/wesad/`

## Configuração do ambiente

### 1. Criar ambiente virtual

```bash
cd burnout
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -U pip
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente (`burnout.conf`)

O projeto tenta carregar automaticamente:

- `burnout/burnout.conf`
- `../burnout.conf` (raiz do repositório)

Exemplo mínimo:

```env
DB_ENGINE=django.db.backends.postgresql
DB_HOST=localhost
DB_PORT=5434
DB_NAME=burnout
DB_USER=postgres
DB_PASS=123456

DEBUG=True

ACCESS_TOKEN_LIFETIME_IN_MINUTES=360
REFRESH_TOKEN_LIFETIME_IN_DAYS=7

# Modelo legado de burn rate
BURN_RATE_MODEL_VERSION=gb-eval-v5
```

Exemplo opcional (MinIO/S3):

```env
AWS_S3_ACCESS_KEY_ID=minioadmin
AWS_S3_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=burnout
AWS_S3_ENDPOINT_URL=http://localhost:9000
```

## Como executar a API

### 1. Criar/aplicar migrações

```bash
cd burnout
python manage.py makemigrations
python manage.py migrate
```

### 2. (Opcional) Criar usuário admin

```bash
python manage.py createsuperuser
```

### 3. Validar o projeto

```bash
python manage.py check
```

### 4. Subir o servidor

```bash
python manage.py runserver 0.0.0.0:8000
```

Base local: `http://localhost:8000/api/`

## Endpoints

### Autenticação de usuários (base em `accounts.User`)

#### 1) `POST /api/users/register/`

Cria um usuário geral na plataforma (independente de employee).

Payload:

```json
{
  "username": "user.demo",
  "password": "SenhaSegura123",
  "email": "user.demo@acme.com",
  "name": "User Demo"
}
```

#### 2) `POST /api/users/login/`

Login geral por `username + password`.

Payload:

```json
{
  "username": "user.demo",
  "password": "SenhaSegura123"
}
```

### Autenticação de employee

#### 1) `POST /api/employees/register/`

Vincula credencial de login ao `employee_id` existente e cria o `User` correspondente.

Payload:

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "password": "SenhaSegura123"
}
```

#### 2) `POST /api/employees/login/`

Login de employee por `employee_id + password` com retorno de `access` e `refresh`.

Payload:

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "password": "SenhaSegura123"
}
```

### Fluxo legado: Burn Rate

#### `POST /api/ml/burn-rate/predict/`

Payload:

```json
{
  "gender": "0",
  "company_type": "0",
  "wfh_setup_available": false,
  "designation": 1,
  "resource_allocation": 6,
  "work_hours_per_week": 42,
  "sleep_hours": 7.0,
  "work_life_balance_score": 2,
  "manager_support_score": 2,
  "deadline_pressure_score": 5,
  "team_size": 8,
  "recognition_frequency": 1
}
```

`curl`:

```bash
curl -X POST "http://localhost:8000/api/ml/burn-rate/predict/" \
  -H "Content-Type: application/json" \
  -d '{"gender":"0","company_type":"0","wfh_setup_available":false,"designation":1,"resource_allocation":6,"work_hours_per_week":42,"sleep_hours":7.0,"work_life_balance_score":2,"manager_support_score":2,"deadline_pressure_score":5,"team_size":8,"recognition_frequency":1}'
```

---

### Novo pipeline: risco combinado

Todos os endpoints abaixo exigem `Authorization: Bearer <access_token>`.

#### 1) `POST /api/ml/stress/wearable/events/`

Ingestão de dados fisiológicos em lote curto.

Payload:

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_id": "watch-001",
  "samples": [
    {"sensor_type": "hr", "recorded_at": "2026-02-15T10:00:00Z", "value": 96, "unit": "bpm", "quality": 0.92},
    {"sensor_type": "eda", "recorded_at": "2026-02-15T10:00:02Z", "value": 2.8, "unit": "uS", "quality": 0.88},
    {"sensor_type": "temp", "recorded_at": "2026-02-15T10:00:03Z", "value": 34.2, "unit": "C", "quality": 0.90},
    {"sensor_type": "hrv", "recorded_at": "2026-02-15T10:00:04Z", "value": 35, "unit": "ms", "quality": 0.80}
  ]
}
```

Retorno principal: `stress_score`, `stress_risk`, `trigger_recommended`.

#### 2) `POST /api/ml/burnout/assessment/`

Assessment composto (evita depender apenas de `burn_rate` autodeclarado).

Payload:

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "triggered",
  "exhaustion_score": 4,
  "cynicism_score": 3,
  "efficacy_score": 2,
  "work_life_balance_score": 2,
  "manager_support_score": 2,
  "deadline_pressure_score": 4,
  "sleep_hours": 5.5,
  "work_hours_per_week": 52,
  "notes": "assessment apos trigger de stress"
}
```

Retorno principal: `composite_score`, `risk_level`, `factors`.

#### 3) `POST /api/ml/risk/inference/`

Fusão final de risco entre stress e burnout.

Payload mínimo (usa últimos registros salvos):

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {"channel": "mobile-app"}
}
```

Retorno principal: `final_score`, `risk_level`, `recommendation`.

## Melhorias implementadas nesta fase

1. Novos modelos de dados para pipeline clínico-operacional:
   - `WearableSample`
   - `StressInferenceSnapshot`
   - `BurnoutAssessment`
   - `RiskTriageDecision`
2. Novos endpoints REST para ingestão, avaliação e fusão de risco.
3. Novo serviço de pipeline em `risk_pipeline.py` com:
   - score heurístico inicial de stress;
   - score composto de burnout;
   - regra de fusão de risco final.
4. Admin Django atualizado para monitorar os dados novos.
5. Treino de burnout com estratégias de alvo:
   - `reported`
   - `composite`

## Documentacao adicional

- Estrategia de fallback do pipeline de risco: `burnout/docs/risk-inference-fallback.md`
   - `hybrid` (padrão)

## Treino offline do modelo legado de Burn Rate

Script: `burnout/tech_employee/ml/burnout/train_and_export.py`

### Treino base

```bash
cd burnout
python employee/ml/burnout/train_and_export.py \
  --data employee/ml/burnout/employeedataset.csv \
  --out-dir artifacts/burn_rate/gb-eval-v6 \
  --version gb-eval-v6 \
  --target-strategy hybrid
```

### Treino com tuning

```bash
python employee/ml/burnout/train_and_export.py \
  --out-dir artifacts/burn_rate/gb-eval-v6-tuned \
  --version gb-eval-v6-tuned \
  --target-strategy hybrid \
  --tune-mid \
  --n-iter 25
```

### Artefatos gerados

- `model_mid.joblib`
- `model_q10.joblib`
- `model_q90.joblib`
- `metadata.json`
- `feature_importance.csv`
- `feature_importance.png` (se `matplotlib` estiver disponível)

## Observações

- A inferência online de stress no backend está em modo heurístico inicial.
- O material de PyTorch/WESAD já está no repositório e é a base para a próxima etapa de integração real-time.
- A API não treina modelos em runtime.

## Troubleshooting rápido

- `ModuleNotFoundError: django`:
  - ative o ambiente virtual e reinstale dependências.
- erro de conexão com banco:
  - valide `DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`.
- resposta com `model_version = heuristic-v1` no endpoint legado:
  - artefatos `.joblib` não foram encontrados/carregados.
