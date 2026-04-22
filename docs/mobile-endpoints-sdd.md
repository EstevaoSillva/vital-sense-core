# SDD - Endpoints Mobile sem Dados Mocados

## 1) Contexto

O app mobile em `/home/estevaosilva/StudioProjects/vital-sense-app/app` usa `MindSenseApi` para consumir dados reais quando `USE_FAKE_DATA=false`.

Parte dos contratos ja existia no backend, mas algumas telas ainda dependiam de `FakeMindSenseLocalDataSource` por falta de endpoints reais.

## 2) Objetivo

- Expor no backend todos os endpoints que o app mobile ja chama.
- Persistir dados editoriais, recomendacoes, notificacoes, perfil complementar e status de dispositivo.
- Derivar historico e insights dos modelos de saude ja existentes.
- Manter o contrato JSON esperado pelos DTOs Kotlin.

## 3) Endpoints Cobertos

Ja existentes e mantidos:

- `POST /api/users/login/`
- `POST /api/users/register/`
- `GET /api/enterprises/`
- `GET /api/dashboard/summary`
- `GET /api/ml/burnout/assessment/questions/`
- `POST /api/ml/burnout/assessment/`

Novos endpoints mobile:

- `GET /api/profile`
- `GET /api/sync/status`
- `GET /api/history/collections`
- `GET /api/history/collections/{collectionId}`
- `GET /api/insights`
- `GET /api/recommendations`
- `GET /api/content/articles`
- `GET /api/content/articles/{articleId}`
- `GET /api/notifications`

## 4) Contratos Publicos

Todos os endpoints novos sao autenticados e usam o `EmployeeRecord` do usuario logado.

Os nomes de campos seguem o app:

- Perfil: `name`, `email`, `jobTitle`, `company`, `workSchedule`.
- Sync: `deviceName`, `isConnected`, `batteryPercent`, `lastSyncLabel`, `syncing`.
- Historico: `id`, `title`, `timestamp`, `durationLabel`, `score`, `label`, `quality`, `deviceName`.
- Detalhe de historico: `session`, `heartRatePoints`, `stressPoints`, `sensors`, `observation`, `recommendation`.
- Insights: `weeklyStress`, `monthlyStress`, `burnoutRiskTrend`, `criticalFactors`, `trendLabel`.
- Recomendacoes: `id`, `title`, `description`, `reason`, `priority`.
- Artigos: `id`, `title`, `category`, `readTimeMinutes`, `summary`, `author`, `sections`, `watchSummary`.
- Notificacoes: `id`, `category`, `title`, `description`, `timestamp`.

## 5) Persistencia

Foram adicionados modelos persistidos para dados que antes eram mockados:

- `EmployeeProfile`
- `WatchDeviceStatus`
- `Recommendation`
- `Article`
- `ArticleSection`
- `MobileNotification`

Historico e insights reaproveitam:

- `StressInferenceSnapshot`
- `WearableSample`
- `BurnoutAssessment`
- `RiskTriageDecision`

## 6) Regras de Comportamento

- Listas sem dados retornam `[]`.
- Perfil sem complemento retorna dados basicos de `User`, `Enterprise` e strings vazias.
- Sync sem dispositivo retorna `Sem dispositivo`, `isConnected=false`, `batteryPercent=0`.
- Detalhe de coleta inexistente ou pertencente a outro funcionario retorna `404`.
- Historico usa snapshots de stress do funcionario autenticado.
- Insights agregam os registros recentes em percentuais `0..100`.
- Conteudo editorial e recomendacoes globais podem ser compartilhados entre funcionarios.

## 7) Test Plan

- Validar autenticacao dos endpoints privados.
- Validar isolamento por `EmployeeRecord`.
- Validar contrato de perfil e status do relogio.
- Validar lista e detalhe de historico.
- Validar insights, recomendacoes, artigos e notificacoes com dados persistidos.
- Rodar `PYENV_VERSION=burnout pyenv exec python manage.py test employee`.

## 8) Assumptions

- O backend deve adaptar os retornos ao contrato atual do app para evitar mudancas no Kotlin.
- `USE_FAKE_DATA=false` deve ser o caminho principal de homologacao.
- Conteudo editorial, notificacoes e recomendacoes entram como leitura mobile nesta fase; CRUD administrativo pode ser evoluido depois.
