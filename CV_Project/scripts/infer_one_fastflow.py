"""Fastflow single-image inference with GUI-compatible JSON output."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


DEBUG_FIELDS = (
    "pred_score",
    "pred_scores",
    "anomaly_score",
    "anomaly_scores",
    "anomaly_map",
    "pred_label",
    "pred_labels",
    "pred_mask",
    "image_path",
)


def configure_utf8_stdio() -> None:
    """Reduce Windows console encoding surprises for child-process inference."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONLEGACYWINDOWSSTDIO", "0")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def build_result(
    ok: bool,
    label: str,
    score: float,
    threshold: float,
    defect_type: str,
    message: str,
    image_path: str | Path,
    heatmap_path: str | Path,
    pose: str,
    product_id: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Build a GUI-compatible inference result."""
    return {
        "ok": bool(ok),
        "label": str(label),
        "score": float(score),
        "threshold": float(threshold),
        "defect_type": str(defect_type),
        "message": str(message),
        "image_path": str(image_path),
        "heatmap_path": str(heatmap_path or ""),
        "boxes": [],
        "pose": str(pose or ""),
        "product_id": str(product_id or ""),
        "algorithm_script": "infer_one_fastflow.py",
        "elapsed_ms": int(elapsed_ms),
    }


def error_result(
    message: str,
    image_path: str | Path = "",
    threshold: float = 0.5,
    pose: str = "",
    product_id: str = "",
    started_at: float | None = None,
) -> dict[str, Any]:
    """Build an ERROR result while keeping stdout valid JSON."""
    elapsed_ms = int((time.time() - started_at) * 1000) if started_at else 0
    return build_result(
        ok=False,
        label="ERROR",
        score=0.0,
        threshold=threshold,
        defect_type="algorithm_error",
        message=message,
        image_path=image_path,
        heatmap_path="",
        pose=pose,
        product_id=product_id,
        elapsed_ms=elapsed_ms,
    )


def scalar_to_float(value: Any) -> float:
    """Convert tensor/list/scalar prediction values to float."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "flatten"):
        value = value.flatten()[0]
    elif isinstance(value, (list, tuple)):
        value = value[0]
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def tensor_max_to_float(value: Any) -> float:
    """Convert tensor/array max value to float."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "max"):
        value = value.max()
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def first_prediction(predictions: Any) -> Any:
    """Return the first prediction item from common anomalib prediction shapes."""
    batch = predictions[0] if isinstance(predictions, (list, tuple)) else predictions
    if isinstance(batch, (list, tuple)) and batch:
        return batch[0]
    return batch


def summarize_value(value: Any) -> str:
    """Summarize tensors/arrays safely without printing full contents."""
    try:
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is not None:
            return f"type={type(value).__name__}, shape={tuple(shape)}, dtype={dtype}"
        if isinstance(value, (list, tuple)):
            return f"type={type(value).__name__}, len={len(value)}"
        return f"type={type(value).__name__}, value={value}"
    except Exception as exc:
        return f"type={type(value).__name__}, summary_error={exc}"


def debug_prediction_structure(predictions: Any) -> None:
    """Print prediction structure to stderr for score-field diagnosis."""
    print(f"[DEBUG] predictions type: {type(predictions).__name__}", file=sys.stderr)
    if isinstance(predictions, (list, tuple)):
        print(f"[DEBUG] predictions len: {len(predictions)}", file=sys.stderr)
    batch = first_prediction(predictions)
    print(f"[DEBUG] first prediction type: {type(batch).__name__}", file=sys.stderr)

    if isinstance(batch, dict):
        print(f"[DEBUG] dict keys: {list(batch.keys())}", file=sys.stderr)
        for key in DEBUG_FIELDS:
            if key in batch:
                print(f"[DEBUG] {key}: {summarize_value(batch[key])}", file=sys.stderr)
        return

    attrs = [name for name in DEBUG_FIELDS if hasattr(batch, name)]
    print(f"[DEBUG] supported attrs: {attrs}", file=sys.stderr)
    for name in attrs:
        print(f"[DEBUG] {name}: {summarize_value(getattr(batch, name))}", file=sys.stderr)


def get_prediction_value(prediction: Any, key: str) -> Any:
    """Read a value from dict-like or object-like anomalib prediction."""
    if isinstance(prediction, dict):
        return prediction.get(key)
    return getattr(prediction, key, None)


def extract_score(predictions: Any) -> float:
    """Extract anomaly score from common anomalib prediction outputs."""
    if predictions is None:
        raise ValueError("prediction result is None")

    prediction = first_prediction(predictions)
    score_keys = ("pred_score", "pred_scores", "anomaly_score", "anomaly_scores", "score", "scores")
    candidates: list[tuple[str, float]] = []

    for key in score_keys:
        value = get_prediction_value(prediction, key)
        if value is not None:
            candidates.append((key, scalar_to_float(value)))

    anomaly_map = get_prediction_value(prediction, "anomaly_map")
    if anomaly_map is not None:
        candidates.append(("anomaly_map.max", tensor_max_to_float(anomaly_map)))

    if not candidates:
        if isinstance(prediction, dict):
            raise KeyError(f"prediction dict has no score field; keys={list(prediction.keys())}")
        raise AttributeError(f"prediction object has no supported score field: {type(prediction).__name__}")

    chosen_key, score = max(candidates, key=lambda item: item[1])
    print(f"[DEBUG] score candidates: {candidates}; chosen={chosen_key}", file=sys.stderr)
    return float(score)


def save_heatmap_if_available(predictions: Any, output_dir: Path, image_path: Path) -> str:
    """Save anomaly map as a grayscale PNG when available.

    TODO: Replace this simple grayscale map with an image overlay if the
    deployment workflow needs a human-friendly heatmap preview.
    """
    anomaly_map = get_prediction_value(first_prediction(predictions), "anomaly_map")
    if anomaly_map is None:
        print("[DEBUG] no anomaly_map found; heatmap_path will be empty", file=sys.stderr)
        return ""

    try:
        import numpy as np
        from PIL import Image

        if hasattr(anomaly_map, "detach"):
            anomaly_map = anomaly_map.detach()
        if hasattr(anomaly_map, "cpu"):
            anomaly_map = anomaly_map.cpu()
        if hasattr(anomaly_map, "numpy"):
            anomaly_map = anomaly_map.numpy()

        array = np.asarray(anomaly_map)
        array = np.squeeze(array)
        if array.ndim != 2:
            print(f"[DEBUG] unsupported anomaly_map ndim={array.ndim}; heatmap_path will be empty", file=sys.stderr)
            return ""

        min_value = float(np.nanmin(array))
        max_value = float(np.nanmax(array))
        if max_value > min_value:
            array = (array - min_value) / (max_value - min_value)
        else:
            array = np.zeros_like(array)
        image = Image.fromarray((array * 255).astype("uint8"), mode="L")

        output_dir.mkdir(parents=True, exist_ok=True)
        heatmap_path = output_dir / f"{int(time.time() * 1000)}_{image_path.stem}_fastflow_heatmap.png"
        image.save(heatmap_path)
        return str(heatmap_path.resolve())
    except Exception as exc:
        print(f"[DEBUG] failed to save heatmap: {exc}", file=sys.stderr)
        return ""


def make_predict_dataset(image_path: Path, image_size: int = 256):
    """Create an anomalib PredictDataset for one image."""
    from anomalib.data import PredictDataset

    return PredictDataset(path=image_path, image_size=(image_size, image_size))


def run_fastflow(
    image_path: Path,
    checkpoint_path: Path,
    threshold: float,
    output_dir: Path,
    device: str,
) -> tuple[bool, str, float, str, str, str]:
    """Load Fastflow checkpoint and run one-image inference."""
    import torch
    from anomalib.engine import Engine
    from anomalib.models import Fastflow

    accelerator = "cpu"
    if device == "cuda":
        accelerator = "gpu"
    elif device == "auto" and torch.cuda.is_available():
        accelerator = "gpu"

    print(f"[INFO] accelerator={accelerator}", file=sys.stderr)
    model = Fastflow(backbone="resnet18", pre_trained=False)

    engine_kwargs: dict[str, Any] = {"accelerator": accelerator}
    if accelerator == "gpu":
        engine_kwargs["devices"] = 1
    engine = Engine(**engine_kwargs)

    dataset = make_predict_dataset(image_path)
    try:
        predictions = engine.predict(model=model, dataset=dataset, ckpt_path=str(checkpoint_path))
    except TypeError:
        predictions = engine.predict(model=model, data_path=str(image_path), ckpt_path=str(checkpoint_path))

    debug_prediction_structure(predictions)
    score = extract_score(predictions)
    heatmap_path = save_heatmap_if_available(predictions, output_dir=output_dir, image_path=image_path)
    label = "NG" if score > threshold else "OK"
    ok = label == "OK"
    defect_type = "anomaly" if label == "NG" else "none"
    message = "Fastflow detected anomaly" if label == "NG" else "Fastflow inspection normal"
    return ok, label, score, defect_type, message, heatmap_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fastflow single-image inference.")
    parser.add_argument("--image", required=True, help="Path to the image to inspect.")
    parser.add_argument("--checkpoint", required=True, help="Path to the Fastflow checkpoint.")
    parser.add_argument("--threshold", type=float, default=0.5, help="NG threshold for anomaly score.")
    parser.add_argument("--pose", default="", help="Optional robot pose name.")
    parser.add_argument("--product-id", default="", help="Optional product id.")
    parser.add_argument("--output-dir", default="", help="Directory for heatmap/result outputs.")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto", help="Inference device.")
    return parser.parse_args()


def main() -> int:
    configure_utf8_stdio()
    args = parse_args()
    started_at = time.time()
    image_path = Path(args.image).expanduser()
    checkpoint_path = Path(args.checkpoint).expanduser()
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else Path.cwd() / "fastflow_infer_outputs"

    try:
        if not image_path.is_file():
            raise FileNotFoundError(f"image does not exist: {image_path}")
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"checkpoint does not exist: {checkpoint_path}")
        if checkpoint_path.suffix.lower() not in {".ckpt", ".pt", ".pth"}:
            raise ValueError(f"unsupported checkpoint suffix: {checkpoint_path.suffix}")

        with contextlib.redirect_stdout(sys.stderr):
            ok, label, score, defect_type, message, heatmap_path = run_fastflow(
                image_path=image_path.resolve(),
                checkpoint_path=checkpoint_path.resolve(),
                threshold=float(args.threshold),
                output_dir=output_dir,
                device=args.device,
            )

        result = build_result(
            ok=ok,
            label=label,
            score=score,
            threshold=args.threshold,
            defect_type=defect_type,
            message=message,
            image_path=image_path.resolve(),
            heatmap_path=heatmap_path,
            pose=args.pose,
            product_id=args.product_id,
            elapsed_ms=int((time.time() - started_at) * 1000),
        )
    except Exception as exc:
        print(f"Fastflow inference error: {exc}", file=sys.stderr)
        result = error_result(
            message=str(exc),
            image_path=str(image_path),
            threshold=args.threshold,
            pose=args.pose,
            product_id=args.product_id,
            started_at=started_at,
        )

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
