import argparse
import os

import tensorflow as tf
import torch
import torch.nn as nn

# WESAD MLP architecture
# Input dimension: 85 (ACC: 46, BVP: 23, TEMP: 16) -> EDA (16) removed from original 101
class MLP(nn.Module):
    def __init__(self, input_dim=85, num_classes=3, dropout_rate=0.25):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.net(x)


def _build_tf_mlp(input_dim=85, num_classes=3, dropout_rate=0.25):
    # Dropout kept for parity with PyTorch; it is disabled during inference.
    return tf.keras.Sequential(
        [
            tf.keras.layers.InputLayer(input_shape=(input_dim,)),
            tf.keras.layers.Dense(256, activation="relu"),
            tf.keras.layers.Dropout(dropout_rate),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(dropout_rate),
            tf.keras.layers.Dense(num_classes),
        ]
    )


def _transfer_pytorch_to_tf(torch_model, tf_model):
    # Force TF variable initialization before setting weights.
    tf_model(tf.zeros((1, 85), dtype=tf.float32))

    # Linear layers in torch Sequential: indices 0, 3, 6
    torch_linear_layers = [m for m in torch_model.net if isinstance(m, nn.Linear)]
    tf_dense_layers = [m for m in tf_model.layers if isinstance(m, tf.keras.layers.Dense)]

    if len(torch_linear_layers) != len(tf_dense_layers):
        raise ValueError(
            f"Layer count mismatch: torch={len(torch_linear_layers)} tf={len(tf_dense_layers)}"
        )

    for torch_layer, tf_layer in zip(torch_linear_layers, tf_dense_layers):
        weight = torch_layer.weight.detach().cpu().numpy()
        bias = torch_layer.bias.detach().cpu().numpy()
        # PyTorch uses [out, in] and TF uses [in, out].
        tf_layer.set_weights([weight.T, bias])


def _log_info(message):
    print(f"[INFO] {message}")


def _exit_with_error(message):
    raise SystemExit(f"[ERROR] {message}")


def export_model(model_checkpoint_path, tflite_output_path):
    _log_info(f"Loading model from {model_checkpoint_path}...")

    if not os.path.exists(model_checkpoint_path):
        _exit_with_error(f"Model file not found at {model_checkpoint_path}")

    checkpoint = torch.load(model_checkpoint_path, map_location="cpu")
    torch_model = MLP(input_dim=85, num_classes=3)

    # Handle different checkpoint formats: full dict with state_dict or raw state_dict.
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    elif isinstance(checkpoint, dict):
        state_dict = checkpoint
    else:
        state_dict = checkpoint

    # If weights are incompatible (e.g., 101-dim model), load_state_dict will fail.
    try:
        torch_model.load_state_dict(state_dict)
        _log_info("Model loaded successfully.")
    except RuntimeError as exc:
        _exit_with_error(
            "Could not load state dict into the 85-input architecture. "
            f"Details: {exc}"
        )

    torch_model.eval()

    # Build equivalent TF model and transfer weights.
    _log_info("Building TensorFlow model and transferring weights...")
    tf_model = _build_tf_mlp(input_dim=85, num_classes=3)
    _transfer_pytorch_to_tf(torch_model, tf_model)
    _log_info("TensorFlow model ready.")

    # Convert TF model to TFLite with Float16 quantization.
    _log_info("Converting to TFLite with Float16 Quantization...")
    converter = tf.lite.TFLiteConverter.from_keras_model(tf_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]

    tflite_model = converter.convert()

    # Persist the TFLite file.
    with open(tflite_output_path, "wb") as f:
        f.write(tflite_model)

    _log_info(f"TFLite model exported to {tflite_output_path}")


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Export a PyTorch WESAD MLP checkpoint to TFLite."
    )
    parser.add_argument(
        "--model-path",
        default="best_model.pt",
        help="Path to the PyTorch checkpoint.",
    )
    parser.add_argument(
        "--output-path",
        default="stress_model.tflite",
        help="Path to save the TFLite file.",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    export_model(args.model_path, args.output_path)
