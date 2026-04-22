# Burn Rate Training and Export

Run training offline (outside API runtime):

```bash
cd /home/estevaosilva/PycharmProjects/burnout-core
python3 burnout/employee/ml/burnout/train_and_export.py \
  --data burnout/employee/ml/burnout/employeedataset.csv \
  --out-dir artifacts/burn_rate/v1 \
  --version 2026-02-12-v1
```

Artifacts generated:
- `model_mid.joblib`
- `model_q10.joblib`
- `model_q90.joblib`
- `metadata.json`

Configure the app (`burnout.conf`):

```env
# Prefer this unified base-dir + version approach:
BURN_RATE_ARTIFACTS_BASE_DIR=/home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/artifacts/burn_rate
BURN_RATE_MODEL_VERSION=2026-02-12-v1

# Optional explicit override paths (only if needed):
BURN_RATE_MODEL_PATH=/home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/artifacts/burn_rate/2026-02-12-v1/model_mid.joblib
BURN_RATE_Q10_MODEL_PATH=/home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/artifacts/burn_rate/2026-02-12-v1/model_q10.joblib
BURN_RATE_Q90_MODEL_PATH=/home/estevaosilva/PycharmProjects/burnout-core/burnout/employee/artifacts/burn_rate/2026-02-12-v1/model_q90.joblib
BURN_RATE_RMSE=0.12
```

Then restart the Django process.
