# Vital Sense Core

Backend Django/DRF para gestao de usuarios, colaboradores e empresas, com endpoints para autenticacao, acompanhamento de bem-estar e inferencia de risco relacionada a stress e burnout.

O repositorio combina duas frentes:

- API operacional em Django para mobile, administrativo e enterprise.
- Codigo e artefatos de ML usados no fluxo legado de `burn-rate` e nos experimentos de stress com dados de wearable.

## Visao Geral

Hoje o projeto esta organizado em quatro apps principais:

- `accounts`: usuario customizado, grupos e recuperacao de senha.
- `employee`: cadastro do colaborador, perfil mobile, coletas de wearable, snapshots de stress, assessments de burnout, recomendacoes e endpoints do app mobile.
- `enterprise`: cadastro e operacao da visao B2B, com empresa, dashboard corporativo, usuarios e grupos terapeuticos.
- `core`: classes base compartilhadas.

O projeto Django fica em `burnout/`, com configuracao central, settings e roteamento.

## Estrutura Atual

```text
.
├── burnout/                # Projeto Django (settings, urls, asgi, wsgi)
├── accounts/               # Usuario customizado e autenticacao geral
├── employee/               # Dominio principal de colaborador e APIs mobile/ML
│   ├── management/commands/
│   └── services/
├── enterprise/             # APIs corporativas
├── core/                   # ModelBase e utilitarios basicos
├── ml/
│   ├── burnout/            # Treino e inferencia do modelo legado/tabular
│   └── stress/wesad/       # Estudos e exportacao para stress com wearable
├── artifacts/              # Modelos exportados e metadados versionados
├── compose/                # Docker Compose para Postgres e MinIO
├── docs/                   # Documentacao tecnica complementar
├── manage.py
├── requirements.txt
└── burnout.conf            # Variaveis de ambiente
```

## Componentes Relevantes

### API Django

- `burnout/settings.py`: configuracao de banco, JWT, DRF, throttle e carregamento de `.env`.
- `burnout/urls.py`: roteador principal da API.
- `manage.py`: entrypoint padrao do Django.

### Dominio e regras

- `accounts/models.py`: modelo `User` customizado (`AUTH_USER_MODEL = accounts.User`).
- `employee/models.py`: entidades de colaborador, perfil, dispositivo, amostras de wearable, stress, burnout, recomendacoes, artigos e notificacoes.
- `enterprise/models.py`: empresa, perfil comercial e grupos terapeuticos.
- `employee/services/risk_pipeline.py`: heuristicas atuais para score de stress, score composto de burnout e consolidacao do risco final.

### Machine Learning

- `ml/burnout/predictor.py`: inferencia do fluxo legado de `burn-rate`.
- `ml/burnout/train_and_export.py`: treino/export do modelo tabular de burnout.
- `ml/stress/wesad/train_wesad_ml.py`: treino experimental com dataset WESAD.
- `ml/stress/wesad/export_tflite.py`: exportacao para TFLite do pipeline de stress.
- `artifacts/burn_rate/`: modelos versionados em `joblib` com `metadata.json`.

### Operacao e suporte

- `compose/docker-compose-postgres.yml`: banco local PostgreSQL na porta `5434`.
- `compose/docker-compose-minio.yml`: MinIO opcional para armazenamento S3-compat.
- `employee/management/commands/import_employees.py`: importa colaboradores a partir de CSV.

## Stack

- Python 3.11+
- Django 4.2
- Django REST Framework
- Simple JWT
- PostgreSQL
- django-filter
- boto3 / django-storages
- scikit-learn, XGBoost
- PyTorch e TensorFlow para experimentos de ML

## Configuracao do Ambiente

### 1. Criar ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -U pip
pip install -r requirements.txt
```

### 3. Configurar variaveis de ambiente

O projeto tenta carregar variaveis a partir destes caminhos, nesta ordem:

- arquivo definido em `BURNOUT_ENV_FILE`
- `./burnout.conf`
- `../burnout.conf`

Exemplo minimo:

```env
DB_ENGINE=django.db.backends.postgresql
DB_HOST=localhost
DB_PORT=5434
DB_NAME=burnout
DB_USER=postgres
DB_PASS=123456

ACCESS_TOKEN_LIFETIME_IN_MINUTES=360
REFRESH_TOKEN_LIFETIME_IN_DAYS=7

REQUEST_PER_MINUTES=60
STRESS_RUNTIME_STRATEGY=heuristic

AWS_S3_ACCESS_KEY_ID=minioadmin
AWS_S3_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=burnout
AWS_S3_ENDPOINT_URL=http://localhost:9000
```

Observacoes:

- `DEBUG` esta fixado como `True` em `burnout/settings.py`.
- O banco depende integralmente das variaveis `DB_*`; nao ha fallback para SQLite.
- O runtime atual de stress usa estrategia heuristica; qualquer valor diferente em `STRESS_RUNTIME_STRATEGY` cai em fallback para `heuristic`.

## Subindo a Infra Local

### PostgreSQL

```bash
docker compose -f compose/docker-compose-postgres.yml up -d
```

### MinIO opcional

```bash
docker compose -f compose/docker-compose-minio.yml up -d
```

## Executando o Projeto

### 1. Aplicar migracoes

```bash
python manage.py migrate
```

### 2. Criar superusuario opcional

```bash
python manage.py createsuperuser
```

### 3. Validar configuracao

```bash
python manage.py check
```

### 4. Subir servidor

```bash
python manage.py runserver 0.0.0.0:8000
```

Base local da API: `http://localhost:8000/api/`

## Mapa de Rotas

### Autenticacao e contas

- `POST /api/users/register/`
- `POST /api/users/login/`
- `GET|POST|PUT|PATCH|DELETE /api/users/`
- `GET|POST|PUT|PATCH|DELETE /api/user-groups/`
- `GET|POST|PUT|PATCH|DELETE /api/recovery-passwords/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `POST /api/auth/token/verify/`
- `GET /api/auth/login/` e afins via DRF browsable auth

### Employee e mobile

- `POST /api/employees/login/`
- `GET|POST|PUT|PATCH|DELETE /api/employees/`
- `GET /api/dashboard/summary`
- `GET /api/profile`
- `GET /api/sync/status`
- `GET /api/history/collections`
- `GET /api/history/collections/<collection_id>`
- `GET /api/insights`
- `GET /api/recommendations`
- `GET /api/content/articles`
- `GET /api/content/articles/<article_id>`
- `GET /api/notifications`

### ML e risco

- `POST /api/ml/burn-rate/predict/`
- `POST /api/ml/stress/wearable/events/`
- `GET /api/ml/burnout/assessment/questions/`
- `POST /api/ml/burnout/assessment/`
- `POST /api/ml/risk/inference/`

### Enterprise

- `POST /api/enterprise/signup/`
- `GET|POST|PATCH /api/enterprise/company/`
- `GET /api/enterprise/dashboard/`
- `GET|POST /api/enterprise/users/`
- `GET /api/enterprise/recommendations/`
- `GET|POST /api/enterprise/therapy-groups/`

## Fluxos de Negocio Atuais

### 1. Fluxo legado de burn-rate

Endpoint exposto em `POST /api/ml/burn-rate/predict/`.

Esse fluxo usa `ml/burnout/predictor.py` e carrega artefatos em `artifacts/burn_rate/`. A API devolve:

- predicao central
- faixa inferior e superior
- nivel de risco
- versao do modelo
- metadados de fallback e out-of-distribution quando aplicavel

### 2. Ingestao de wearable e stress

Endpoint exposto em `POST /api/ml/stress/wearable/events/`.

O payload recebe `device_id` e uma lista de amostras (`samples`) com:

- `sensor_type`
- `recorded_at`
- `value`
- `unit`
- `quality`
- `payload`

As leituras geram:

- persistencia em `WearableSample`
- agregacao heuristica via `compute_stress_window`
- criacao de `StressInferenceSnapshot`
- sinalizacao de `trigger_recommended` quando a janela ultrapassa limiares

### 3. Assessment de burnout

O questionario fica exposto em `GET /api/ml/burnout/assessment/questions/` e a submissao em `POST /api/ml/burnout/assessment/`.

O calculo atual considera principalmente:

- `exhaustion_score`
- `cynicism_score`
- `efficacy_score`
- `work_life_balance_score`
- `manager_support_score`
- `deadline_pressure_score`

O score composto e calculado em `employee/services/risk_pipeline.py`.

### 4. Inferencia final de risco

Endpoint exposto em `POST /api/ml/risk/inference/`.

O consolidado combina:

- stress de wearable, quando existir
- burnout assessment, quando existir

Modos de inferencia atuais:

- `hybrid`
- `assessment_only`
- `wearable_only`

## Comandos Uteis

### Importar colaboradores por CSV

```bash
python manage.py import_employees --csv /caminho/arquivo.csv
```

Opcoes relevantes:

- `--clear`
- `--default-password`
- `--username-prefix`

## Documentacao Complementar

Arquivos de apoio em `docs/`:

- `docs/mobile-endpoints-sdd.md`
- `docs/assessment-burn-rate-sdd.md`
- `docs/risk-inference-fallback.md`
- `docs/ml-auditoria.md`
- `docs/ml-fase1-execucao.md`
- `docs/ml-proximas-fases.md`

Tambem ha materiais auxiliares como:

- `architecture_workflow.md`
- `ml/stress/wesad/README.md`
- `ml/burnout/TRAINING.md`

## Observacoes Importantes

- O README anterior descrevia uma estrutura que nao corresponde mais ao layout atual do repositorio; este documento foi alinhado ao codigo presente na raiz do projeto.
- As rotas sob `employee` usam autenticacao JWT em boa parte dos endpoints; login e predicao legada de `burn-rate` sao publicos.
- Existem muitos artefatos e datasets grandes no repositorio e no `git status`; qualquer limpeza ou reorganizacao desses arquivos deve ser tratada separadamente da API.
