#!/usr/bin/env python3
"""Treino ML para WESAD com validação LOSO (Leave-One-Subject-Out).

Uso rápido:
  python3 ml/stress/train_wesad_ml.py --data-dir WESAD --mode triad

Classes padrão:
  triad  -> labels 1,2,3 (baseline, stress, amusement)
  binary -> labels 1,2 (baseline, stress)
"""

from __future__ import annotations

import argparse
import glob
import os
import pickle
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

LABEL_MAP = {
    0: "transition",
    1: "baseline",
    2: "stress",
    3: "amusement",
    4: "meditation",
    5: "read_1",
    6: "read_2",
    7: "read_3",
}

TARGET_FS_LABEL = 700.0


@dataclass
class SubjectWindows:
    subject: str
    X: np.ndarray
    y: np.ndarray


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Treino ML para WESAD com LOSO")
    p.add_argument("--data-dir", default="../dataset", help="Pasta base do WESAD")
    p.add_argument("--mode", choices=["triad", "binary", "custom"], default="triad")
    p.add_argument(
        "--classes",
        default="",
        help='Quando --mode custom: lista CSV de labels (ex: "1,2,3")',
    )
    p.add_argument("--window-sec", type=float, default=60.0, help="Tamanho da janela")
    p.add_argument("--stride-sec", type=float, default=30.0, help="Passo entre janelas")
    p.add_argument(
        "--majority-threshold",
        type=float,
        default=0.8,
        help="Pureza mínima do label na janela (0..1)",
    )
    p.add_argument(
        "--min-samples-per-window",
        type=int,
        default=8,
        help="Mínimo de amostras por sinal dentro de cada janela",
    )
    p.add_argument(
        "--model",
        choices=["rf", "svm_rbf", "xgb", "ensemble"],
        default="rf",
        help="Modelo ML",
    )
    p.add_argument("--n-estimators", type=int, default=500)
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument(
        "--class-weight",
        choices=["none", "balanced", "balanced_subsample"],
        default="balanced_subsample",
        help="Peso de classe para modelos compatíveis",
    )
    p.add_argument(
        "--oversample",
        action="store_true",
        help="Ativa oversampling aleatório no treino de cada fold LOSO",
    )
    p.add_argument(
        "--subject-zscore",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Normaliza features por sujeito (z-score por coluna)",
    )
    p.add_argument(
        "--enable-psd",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Adiciona features espectrais (PSD) em BVP/EDA/TEMP/ACC|mag",
    )
    p.add_argument(
        "--enable-hrv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Adiciona features HRV aproximadas derivadas do BVP",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Só monta janelas e mostra estatísticas, sem treinar",
    )
    return p.parse_args()


def resolve_classes(args: argparse.Namespace) -> List[int]:
    if args.mode == "triad":
        return [1, 2, 3]
    if args.mode == "binary":
        return [1, 2]
    classes = [int(x.strip()) for x in args.classes.split(",") if x.strip()]
    if not classes:
        raise ValueError("--mode custom exige --classes")
    return sorted(set(classes))


def find_subject_pkls(data_dir: str) -> List[str]:
    # 1. Pega o diretório onde o arquivo train_wesad_ml.py está
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Define o caminho para a pasta 'dataset' que está no mesmo nível da 'stress'
    # Estrutura: ml/ -> stress/ (script) e dataset/ (dados)
    dataset_root = os.path.abspath(os.path.join(current_script_dir, "..", "dataset"))

    candidates: List[str] = [
        os.path.abspath(data_dir), # Caso você passe o caminho completo no terminal
        os.path.join(dataset_root, data_dir) # Procura dentro de ml/dataset/WESAD
    ]

    tested: List[str] = []
    for base in candidates:
        tested.append(base)
        # Busca por WESAD/S2/S2.pkl, etc.
        pkls = sorted(glob.glob(os.path.join(base, "S*", "S*.pkl")))
        if pkls:
            return pkls

    tested_str = ", ".join(tested)
    raise FileNotFoundError(
        f"Nenhum arquivo S*.pkl encontrado. Caminhos testados: {tested_str}"
    )


def load_subject_pkl(path: str) -> Dict:
    with open(path, "rb") as f:
        return pickle.load(f, encoding="latin1")


def signal_slice(sig: np.ndarray, fs: float, t0: float, t1: float) -> np.ndarray:
    i0 = int(max(0, np.floor(t0 * fs)))
    i1 = int(max(0, np.floor(t1 * fs)))
    i1 = min(i1, sig.shape[0])
    if i1 <= i0:
        return np.empty((0,), dtype=float)
    arr = sig[i0:i1]
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    return arr


def robust_stats(x: np.ndarray) -> List[float]:
    if x.size == 0:
        return [np.nan] * 10
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).any():
        return [np.nan] * 10
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    q25 = float(np.percentile(x, 25))
    q75 = float(np.percentile(x, 75))
    std = float(np.std(x))
    dx = np.diff(x)
    slope = float(np.mean(dx)) if dx.size else 0.0
    energy = float(np.mean(x * x))
    return [
        float(np.mean(x)),
        std,
        float(np.min(x)),
        float(np.max(x)),
        float(np.median(x)),
        q25,
        q75,
        float(q75 - q25),
        slope,
        energy,
    ]


def psd_bandpowers(x: np.ndarray, fs: float) -> List[float]:
    if x.size < 8:
        return [np.nan] * 6
    x = np.asarray(x, dtype=float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = x - np.mean(x)

    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(x.size, d=1.0 / fs)

    if spec.size <= 1:
        return [np.nan] * 6

    total = float(np.sum(spec))
    if total <= 0:
        return [0.0] * 6

    def band(a: float, b: float) -> float:
        mask = (freqs >= a) & (freqs < b)
        if not np.any(mask):
            return 0.0
        return float(np.sum(spec[mask]))

    p_lf = band(0.04, 0.15)
    p_mf = band(0.15, 0.40)
    p_hf = band(0.40, 1.00)

    idx = int(np.argmax(spec[1:]) + 1)
    peak_f = float(freqs[idx])
    centroid = float(np.sum(freqs * spec) / np.sum(spec))

    return [
        p_lf / total,
        p_mf / total,
        p_hf / total,
        (p_lf / (p_hf + 1e-12)),
        peak_f,
        centroid,
    ]


def hrv_from_bvp(bvp: np.ndarray, fs: float) -> List[float]:
    if bvp.size < int(fs * 4):
        return [np.nan] * 7

    x = np.asarray(bvp, dtype=float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = (x - np.mean(x)) / (np.std(x) + 1e-12)

    thr = float(np.percentile(x, 75))
    mid = x[1:-1]
    peak_mask = (mid > x[:-2]) & (mid >= x[2:]) & (mid > thr)
    peaks = np.where(peak_mask)[0] + 1

    if peaks.size < 3:
        return [np.nan] * 7

    min_dist = max(1, int(0.35 * fs))
    filtered = [int(peaks[0])]
    for p in peaks[1:]:
        if p - filtered[-1] >= min_dist:
            filtered.append(int(p))
        elif x[p] > x[filtered[-1]]:
            filtered[-1] = int(p)

    peaks = np.asarray(filtered, dtype=int)
    if peaks.size < 3:
        return [np.nan] * 7

    rr = np.diff(peaks) / fs
    rr = rr[(rr > 0.3) & (rr < 1.7)]
    if rr.size < 3:
        return [np.nan] * 7

    drr = np.diff(rr)
    sdnn = float(np.std(rr))
    rmssd = float(np.sqrt(np.mean(drr * drr))) if drr.size else np.nan
    pnn50 = float(np.mean(np.abs(drr) > 0.05)) if drr.size else np.nan
    hr = 60.0 / rr

    return [
        float(np.mean(rr)),
        sdnn,
        rmssd,
        pnn50,
        float(np.mean(hr)),
        float(np.std(hr)),
        float(rr.size),
    ]


def extract_window_features(
    wrist: Dict[str, np.ndarray], t0: float, t1: float, enable_psd: bool, enable_hrv: bool
) -> np.ndarray:
    features: List[float] = []

    specs: List[Tuple[str, float]] = [
        ("ACC", 32.0),
        ("BVP", 64.0),
        ("EDA", 4.0),
        ("TEMP", 4.0),
    ]

    for name, fs in specs:
        sig = wrist[name]
        if name == "ACC":
            seg = signal_slice(sig, fs, t0, t1)
            if seg.ndim != 2 or seg.shape[1] != 3:
                features.extend([np.nan] * (10 * 4))
                if enable_psd:
                    features.extend([np.nan] * 6)
                continue
            for ax in range(3):
                features.extend(robust_stats(seg[:, ax]))
            mag = np.linalg.norm(seg, axis=1)
            features.extend(robust_stats(mag))
            if enable_psd:
                features.extend(psd_bandpowers(mag, fs))
        else:
            seg = signal_slice(sig, fs, t0, t1)
            features.extend(robust_stats(seg))
            if enable_psd:
                features.extend(psd_bandpowers(seg, fs))
            if enable_hrv and name == "BVP":
                features.extend(hrv_from_bvp(seg, fs))

    return np.asarray(features, dtype=float)


def window_majority_label(
    labels_700hz: np.ndarray,
    t0: float,
    t1: float,
    allowed_labels: Sequence[int],
    threshold: float,
) -> int:
    i0 = int(max(0, np.floor(t0 * TARGET_FS_LABEL)))
    i1 = int(min(labels_700hz.shape[0], np.floor(t1 * TARGET_FS_LABEL)))
    if i1 <= i0:
        return -1
    seg = labels_700hz[i0:i1].astype(int)
    seg = seg[np.isin(seg, allowed_labels)]
    if seg.size == 0:
        return -1
    c = Counter(seg.tolist())
    label, count = c.most_common(1)[0]
    purity = count / seg.size
    if purity < threshold:
        return -1
    return int(label)


def build_subject_windows(
    subj_pkl: str,
    allowed_labels: Sequence[int],
    window_sec: float,
    stride_sec: float,
    majority_threshold: float,
    min_samples_per_window: int,
    enable_psd: bool,
    enable_hrv: bool,
) -> SubjectWindows:
    obj = load_subject_pkl(subj_pkl)
    subject = os.path.splitext(os.path.basename(subj_pkl))[0]
    labels = np.asarray(obj["label"]).reshape(-1)
    wrist = obj["signal"]["wrist"]

    duration_sec = labels.shape[0] / TARGET_FS_LABEL
    windows_X: List[np.ndarray] = []
    windows_y: List[int] = []

    t = 0.0
    while t + window_sec <= duration_sec:
        t0, t1 = t, t + window_sec

        ok = True
        if signal_slice(wrist["EDA"], 4.0, t0, t1).shape[0] < min_samples_per_window:
            ok = False
        if signal_slice(wrist["TEMP"], 4.0, t0, t1).shape[0] < min_samples_per_window:
            ok = False
        if signal_slice(wrist["ACC"], 32.0, t0, t1).shape[0] < min_samples_per_window:
            ok = False
        if signal_slice(wrist["BVP"], 64.0, t0, t1).shape[0] < min_samples_per_window:
            ok = False

        if ok:
            y = window_majority_label(labels, t0, t1, allowed_labels, majority_threshold)
            if y != -1:
                feat = extract_window_features(
                    wrist=wrist,
                    t0=t0,
                    t1=t1,
                    enable_psd=enable_psd,
                    enable_hrv=enable_hrv,
                )
                windows_X.append(feat)
                windows_y.append(y)

        t += stride_sec

    if windows_X:
        X = np.vstack(windows_X)
        y = np.asarray(windows_y, dtype=int)
    else:
        X = np.empty((0, 0), dtype=float)
        y = np.empty((0,), dtype=int)
    return SubjectWindows(subject=subject, X=X, y=y)


def apply_subject_zscore(subject_data: List[SubjectWindows]) -> List[SubjectWindows]:
    out: List[SubjectWindows] = []
    for s in subject_data:
        if s.X.size == 0:
            out.append(s)
            continue
        mu = np.nanmean(s.X, axis=0, keepdims=True)
        sd = np.nanstd(s.X, axis=0, keepdims=True)
        sd = np.where((sd < 1e-8) | ~np.isfinite(sd), 1.0, sd)
        Xn = (s.X - mu) / sd
        out.append(SubjectWindows(subject=s.subject, X=Xn, y=s.y))
    return out


def random_oversample(X: np.ndarray, y: np.ndarray, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    cls, counts = np.unique(y, return_counts=True)
    if cls.size <= 1:
        return X, y

    max_n = int(np.max(counts))
    idx_all: List[np.ndarray] = []
    for c in cls:
        idx = np.where(y == c)[0]
        if idx.size == max_n:
            idx_all.append(idx)
            continue
        extra = rng.choice(idx, size=max_n - idx.size, replace=True)
        idx_all.append(np.concatenate([idx, extra]))

    idx_out = np.concatenate(idx_all)
    rng.shuffle(idx_out)
    return X[idx_out], y[idx_out]


def _normalize_class_weight(choice: str, model: str):
    if choice == "none":
        return None
    if model == "svm_rbf" and choice == "balanced_subsample":
        return "balanced"
    return choice


def build_estimator(args: argparse.Namespace):
    try:
        from sklearn.ensemble import RandomForestClassifier, VotingClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC
    except Exception as exc:
        raise RuntimeError(
            "scikit-learn não encontrado. Instale com: pip install -r ml/stress/requirements.txt"
        ) from exc

    cw = _normalize_class_weight(args.class_weight, args.model)

    rf = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=args.n_estimators,
                    random_state=args.random_state,
                    n_jobs=-1,
                    class_weight=cw,
                    min_samples_leaf=2,
                ),
            ),
        ]
    )

    svm = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "svc",
                SVC(
                    kernel="rbf",
                    C=3.0,
                    gamma="scale",
                    class_weight=_normalize_class_weight(args.class_weight, "svm_rbf"),
                    probability=True,
                    random_state=args.random_state,
                ),
            ),
        ]
    )

    if args.model == "rf":
        return rf
    if args.model == "svm_rbf":
        return svm

    if args.model == "xgb":
        try:
            from xgboost import XGBClassifier
        except Exception as exc:
            raise RuntimeError(
                "xgboost não encontrado. Instale com: pip install xgboost"
            ) from exc

        objective = "binary:logistic" if args.mode == "binary" else "multi:softprob"
        num_class = 2 if args.mode == "binary" else 3
        xgb = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "xgb",
                    XGBClassifier(
                        objective=objective,
                        num_class=None if num_class == 2 else num_class,
                        n_estimators=args.n_estimators,
                        max_depth=6,
                        learning_rate=0.05,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        random_state=args.random_state,
                        n_jobs=-1,
                        eval_metric="mlogloss" if num_class > 2 else "logloss",
                    ),
                ),
            ]
        )
        return xgb

    # ensemble
    estimators = [("rf", rf), ("svm", svm)]
    try:
        from xgboost import XGBClassifier

        xgb = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "xgb",
                    XGBClassifier(
                        objective="binary:logistic" if args.mode == "binary" else "multi:softprob",
                        num_class=None if args.mode == "binary" else 3,
                        n_estimators=max(200, args.n_estimators // 2),
                        max_depth=5,
                        learning_rate=0.07,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        random_state=args.random_state,
                        n_jobs=-1,
                        eval_metric="logloss" if args.mode == "binary" else "mlogloss",
                    ),
                ),
            ]
        )
        estimators.append(("xgb", xgb))
    except Exception:
        pass

    return VotingClassifier(estimators=estimators, voting="soft", n_jobs=None)


def train_loso(subject_data: List[SubjectWindows], args: argparse.Namespace) -> None:
    try:
        from sklearn.metrics import classification_report, confusion_matrix, f1_score
    except Exception as exc:
        raise RuntimeError(
            "scikit-learn não encontrado. Instale com: pip install -r ml/stress/requirements.txt"
        ) from exc

    valid_subjects = [s for s in subject_data if s.X.size > 0]
    if len(valid_subjects) < 2:
        raise RuntimeError("Poucos sujeitos com janelas válidas para LOSO")

    all_true: List[int] = []
    all_pred: List[int] = []

    for i, test_subj in enumerate(valid_subjects):
        train_subjects = [s for s in valid_subjects if s.subject != test_subj.subject]
        X_train = np.vstack([s.X for s in train_subjects])
        y_train = np.concatenate([s.y for s in train_subjects])
        X_test = test_subj.X
        y_test = test_subj.y

        if args.oversample:
            X_train, y_train = random_oversample(
                X_train, y_train, seed=args.random_state + i
            )

        clf = build_estimator(args)
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        all_true.extend(y_test.tolist())
        all_pred.extend(y_pred.tolist())

        fold_f1 = f1_score(y_test, y_pred, average="macro")
        print(
            f"[LOSO] test={test_subj.subject:>4} windows={len(y_test):>4} "
            f"macro_f1={fold_f1:.4f}"
        )

    y_true = np.asarray(all_true)
    y_pred = np.asarray(all_pred)

    print("\n=== Resultado Global LOSO ===")
    print(f"Modelo: {args.model}")
    print(f"Class-weight: {args.class_weight}")
    print(f"Oversample: {args.oversample}")
    print(f"Subject z-score: {args.subject_zscore}")
    print(f"PSD features: {args.enable_psd}")
    print(f"HRV features: {args.enable_hrv}")
    print(f"Total windows avaliadas: {len(y_true)}")
    print(f"Macro-F1: {f1_score(y_true, y_pred, average='macro'):.4f}")
    print("\nMatriz de confusão (linhas=true, colunas=pred):")
    labels_sorted = sorted(np.unique(np.concatenate([y_true, y_pred])))
    print("labels:", labels_sorted)
    print(confusion_matrix(y_true, y_pred, labels=labels_sorted))
    print("\nRelatório:")
    print(classification_report(y_true, y_pred, labels=labels_sorted, digits=4))


def main() -> None:
    args = parse_args()
    classes = resolve_classes(args)
    print("Classes alvo:", classes, [LABEL_MAP.get(c, str(c)) for c in classes])

    pkl_paths = find_subject_pkls(args.data_dir)
    print(f"Sujeitos encontrados: {len(pkl_paths)}")

    subject_data: List[SubjectWindows] = []
    for p in pkl_paths:
        s = build_subject_windows(
            subj_pkl=p,
            allowed_labels=classes,
            window_sec=args.window_sec,
            stride_sec=args.stride_sec,
            majority_threshold=args.majority_threshold,
            min_samples_per_window=args.min_samples_per_window,
            enable_psd=args.enable_psd,
            enable_hrv=args.enable_hrv,
        )
        if s.y.size > 0:
            cnt = Counter(s.y.tolist())
            cnt_str = ", ".join(f"{k}:{v}" for k, v in sorted(cnt.items()))
            print(f"{s.subject}: windows={len(s.y)} | {cnt_str}")
        else:
            print(f"{s.subject}: windows=0")
        subject_data.append(s)

    total = int(sum(len(s.y) for s in subject_data))
    feat_dim = int(next((s.X.shape[1] for s in subject_data if s.X.size > 0), 0))
    print(f"Total de janelas válidas: {total}")
    print(f"Dimensão de features por janela: {feat_dim}")

    if args.subject_zscore:
        subject_data = apply_subject_zscore(subject_data)
        print("Normalização por sujeito aplicada (z-score por feature).")

    if args.dry_run:
        return

    train_loso(subject_data=subject_data, args=args)


if __name__ == "__main__":
    main()
