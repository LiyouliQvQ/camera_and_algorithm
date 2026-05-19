import argparse
import contextlib
import json
import sys
import time
from pathlib import Path


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


def build_result(
    ok,
    label,
    score,
    threshold,
    defect_type,
    message,
    image_path,
    pose,
    product_id,
    elapsed_ms,
):
    """Build a GUI-compatible inference result."""
    return {
        "ok": bool(ok),
        "label": str(label),
        "score": float(score),
        "threshold": float(threshold),
        "defect_type": str(defect_type),
        "message": str(message),
        "image_path": str(image_path),
        "heatmap_path": "",
        "pose": str(pose or ""),
        "product_id": str(product_id or ""),
        "algorithm_script": "infer_one_patchcore.py",
        "elapsed_ms": int(elapsed_ms),
        "boxes": [],
    }


def error_result(message, image_path="", threshold=0.5, pose="", product_id="", started_at=None):
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
        pose=pose,
        product_id=product_id,
        elapsed_ms=elapsed_ms,
    )


def scalar_to_float(value):
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


def tensor_max_to_float(value):
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


def summarize_value(value):
    """Summarize tensors/arrays safely without printing full contents."""
    try:
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()

        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is not None:
            summary = f"type={type(value).__name__}, shape={tuple(shape)}, dtype={dtype}"
            if hasattr(value, "min") and hasattr(value, "max"):
                try:
                    min_value = value.min().item() if hasattr(value.min(), "item") else value.min()
                    max_value = value.max().item() if hasattr(value.max(), "item") else value.max()
                    summary += f", min={float(min_value):.6f}, max={float(max_value):.6f}"
                except Exception as exc:
                    summary += f", min/max unavailable: {exc}"
            return summary

        if isinstance(value, (list, tuple)):
            return f"type={type(value).__name__}, len={len(value)}"

        return f"type={type(value).__name__}, value={value}"
    except Exception as exc:
        return f"type={type(value).__name__}, summary_error={exc}"


def debug_prediction_structure(predictions):
    """Print anomalib prediction structure to stderr for score-field diagnosis."""
    print(f"[DEBUG] predictions type: {type(predictions).__name__}", file=sys.stderr)
    if isinstance(predictions, (list, tuple)):
        print(f"[DEBUG] predictions len: {len(predictions)}", file=sys.stderr)
        batch = predictions[0] if predictions else None
    else:
        batch = predictions

    print(f"[DEBUG] batch type: {type(batch).__name__}", file=sys.stderr)
    if isinstance(batch, (list, tuple)) and batch:
        print(f"[DEBUG] nested batch len: {len(batch)}", file=sys.stderr)
        batch = batch[0]
        print(f"[DEBUG] nested item type: {type(batch).__name__}", file=sys.stderr)

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


def extract_score(predictions):
    """Extract anomaly score from common anomalib prediction outputs."""
    if predictions is None:
        raise ValueError("prediction result is None")

    batch = predictions[0] if isinstance(predictions, (list, tuple)) else predictions
    if isinstance(batch, (list, tuple)) and batch:
        batch = batch[0]

    score_keys = ("pred_score", "pred_scores", "anomaly_score", "anomaly_scores", "score", "scores")
    candidates = []
    if isinstance(batch, dict):
        for key in score_keys:
            if key in batch:
                candidates.append((key, scalar_to_float(batch[key])))
        if "anomaly_map" in batch:
            candidates.append(("anomaly_map.max", tensor_max_to_float(batch["anomaly_map"])))
        if not candidates:
            raise KeyError(f"prediction dict has no score field; keys={list(batch.keys())}")
        chosen_key, score = max(candidates, key=lambda item: item[1])
        print(f"[DEBUG] score candidates: {candidates}; chosen={chosen_key}", file=sys.stderr)
        return score

    for key in score_keys:
        if hasattr(batch, key):
            candidates.append((key, scalar_to_float(getattr(batch, key))))
    if hasattr(batch, "anomaly_map"):
        candidates.append(("anomaly_map.max", tensor_max_to_float(getattr(batch, "anomaly_map"))))

    if not candidates:
        raise AttributeError(f"prediction object has no supported score field: {type(batch).__name__}")
    chosen_key, score = max(candidates, key=lambda item: item[1])
    print(f"[DEBUG] score candidates: {candidates}; chosen={chosen_key}", file=sys.stderr)
    return score


def make_predict_dataset(image_path):
    """Create an anomalib PredictDataset for one image, with API fallbacks."""
    from anomalib.data import PredictDataset

    try:
        return PredictDataset(path=image_path)
    except TypeError:
        return PredictDataset(path=image_path, image_size=(256, 256))


def run_patchcore(image_path, model_path, threshold, device):
    """Load PatchCore checkpoint and run one-image inference."""
    import torch
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    accelerator = "cpu"
    if device == "cuda":
        accelerator = "gpu"
    elif device == "auto" and torch.cuda.is_available():
        accelerator = "gpu"

    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=["layer2", "layer3"],
        coreset_sampling_ratio=0.1,
    )

    engine_kwargs = {"accelerator": accelerator}
    if accelerator == "gpu":
        engine_kwargs["devices"] = 1
    engine = Engine(**engine_kwargs)

    dataset = make_predict_dataset(image_path)
    try:
        predictions = engine.predict(model=model, dataset=dataset, ckpt_path=str(model_path))
    except TypeError:
        predictions = engine.predict(model=model, data_path=str(image_path), ckpt_path=str(model_path))

    debug_prediction_structure(predictions)
    score = extract_score(predictions)
    label = "NG" if score >= threshold else "OK"
    ok = label == "OK"
    defect_type = "anomaly" if label == "NG" else "none"
    message = "PatchCore检测到异常" if label == "NG" else "PatchCore检测正常"

    # TODO: 后续从 anomalib anomaly map 保存热力图，并填充 heatmap_path。
    # TODO: 后续可基于 anomaly map 阈值分割提取 boxes。
    return ok, label, score, defect_type, message


def main():
    parser = argparse.ArgumentParser(description="PatchCore single-image inference.")
    parser.add_argument("--image", required=True, help="Path to the image to inspect.")
    parser.add_argument("--model", required=True, help="Path to the PatchCore checkpoint.")
    parser.add_argument("--threshold", type=float, default=0.5, help="NG threshold for anomaly score.")
    parser.add_argument("--pose", default="", help="Optional robot pose name.")
    parser.add_argument("--product-id", default="", help="Optional product id.")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto", help="Inference device.")
    args = parser.parse_args()

    started_at = time.time()
    image_path = Path(args.image).expanduser()
    model_path = Path(args.model).expanduser()

    try:
        if not image_path.is_file():
            raise FileNotFoundError(f"image does not exist: {image_path}")
        if not model_path.is_file():
            raise FileNotFoundError(f"model does not exist: {model_path}")
        if model_path.suffix.lower() not in {".ckpt", ".pt", ".pth", ".onnx", ".engine"}:
            raise ValueError(f"unsupported model suffix: {model_path.suffix}")

        with contextlib.redirect_stdout(sys.stderr):
            ok, label, score, defect_type, message = run_patchcore(
                image_path=image_path.resolve(),
                model_path=model_path.resolve(),
                threshold=float(args.threshold),
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
            pose=args.pose,
            product_id=args.product_id,
            elapsed_ms=int((time.time() - started_at) * 1000),
        )
    except Exception as exc:
        print(f"PatchCore inference error: {exc}", file=sys.stderr)
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
