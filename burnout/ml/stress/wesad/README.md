# WESAD ML (LOSO)

Treino de baseline para classificação de estado afetivo usando WESAD com ML clássico e validação **LOSO** (Leave-One-Subject-Out).

## Status no produto

Este fluxo é **experimental/offline**.
No runtime atual da API, a inferência de stress em produção usa estratégia heurística (`stress-heuristic-v1`) e não consome diretamente os artefatos WESAD deste diretório.

## Melhorias implementadas

- Balanceamento de classes
- `class_weight` configurável
- `oversampling` opcional por fold LOSO
- Normalização por sujeito
- `z-score` por sujeito (`--subject-zscore`, padrão ligado)
- Features fisiológicas
- estatísticas robustas por janela
- PSD/bandpower (`--enable-psd`, padrão ligado)
- HRV aproximada do BVP (`--enable-hrv`, padrão ligado)
- Modelos mais robustos
- `RandomForest` (`rf`)
- `SVM RBF` (`svm_rbf`)
- `XGBoost` (`xgb`)
- `ensemble` soft voting (`rf + svm [+xgb se instalado]`)

## Labels WESAD

- `1`: baseline
- `2`: stress (TSST)
- `3`: amusement
- `4`: meditation
- `0`, `5`, `6`, `7`: transição/leitura (normalmente excluídos)

## Setup

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 -m venv .venv
source .venv/bin/activate
pip install -r employee/ml/stress/wesad/requirements.txt
```

## Execução

Inspeção sem treino:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 employee/ml/stress/wesad/train_wesad_ml.py --data-dir employee/ml/stress/dataset --mode triad --dry-run
```

Também funciona a partir da pasta `employee/ml/stress/wesad`:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/ml/stress/wesad
python3 train_wesad_ml.py --data-dir ../dataset --dry-run
```

Treino triad com oversampling:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 employee/ml/stress/wesad/train_wesad_ml.py --data-dir employee/ml/stress/dataset --mode triad --model rf --oversample
```

Treino binário com SVM:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 employee/ml/stress/wesad/train_wesad_ml.py --data-dir employee/ml/stress/dataset --mode binary --model svm_rbf --class-weight balanced
```

Treino triad com XGBoost:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 employee/ml/stress/wesad/train_wesad_ml.py --data-dir employee/ml/stress/dataset --mode triad --model xgb --oversample
```

Ensemble:

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core/burnout
python3 employee/ml/stress/wesad/train_wesad_ml.py --data-dir employee/ml/stress/dataset --mode triad --model ensemble --oversample
```

## Dicas práticas

- Para generalização entre sujeitos, mantenha `--subject-zscore` ligado.
- Comece com `rf` + `--oversample` e compare com `svm_rbf`.
- Se `xgboost` não estiver instalado, use `rf`/`svm_rbf`.
