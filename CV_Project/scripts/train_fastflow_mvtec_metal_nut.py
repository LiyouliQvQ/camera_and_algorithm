r"""Minimal Anomalib Fastflow experiment for MVTec AD metal_nut.

Default mode is check-only. Training starts only when --run-train is passed.
Run from the repository root or from CV_Project with:
    D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any


CV_PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = CV_PROJECT_DIR / "datasets" / "MVTec"
DEFAULT_OUTPUT_DIR = CV_PROJECT_DIR / "results" / "fastflow_mvtec_metal_nut"
DEFAULT_CATEGORY = "metal_nut"
DEFAULT_IMAGE_SIZE = 256
TRAIN_DEFAULT_MAX_EPOCHS = 1
TRAIN_DEFAULT_BATCH_SIZE = 4
CHECK_DISPLAY_MAX_EPOCHS = 3
CHECK_DISPLAY_BATCH_SIZE = 8


def str2bool(value: str | bool) -> bool:
    """Parse explicit bool strings without treating "false" as truthy."""
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False

    raise argparse.ArgumentTypeError(
        "--pre-trained must be one of: true/false, 1/0, yes/no, y/n"
    )


def import_object(module_name: str, object_name: str | None = None) -> tuple[bool, Any, str]:
    """Import a module or object and return a readable status tuple."""
    try:
        module = importlib.import_module(module_name)
        if object_name is None:
            return True, module, "OK"
        return True, getattr(module, object_name), "OK"
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def status_line(name: str, ok: bool, detail: str = "") -> None:
    state = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    print(f"{name}: {state}{suffix}")


def check_environment(dataset_root: Path, category: str) -> bool:
    """Check imports, GPU availability, and expected MVTec AD directories."""
    print("Fastflow MVTec AD environment check")
    print("====================================")
    print(f"python: {sys.executable}")
    print(f"dataset_root: {dataset_root}")
    print(f"category: {category}")
    print()

    all_ok = True

    torch_ok, torch_module, torch_msg = import_object("torch")
    torch_detail = getattr(torch_module, "__version__", "") if torch_ok else torch_msg
    status_line("torch_import", torch_ok, torch_detail)
    all_ok = all_ok and torch_ok

    if torch_ok:
        cuda_available = bool(torch_module.cuda.is_available())
        device_count = torch_module.cuda.device_count()
        status_line("torch_cuda_available", cuda_available, f"device_count={device_count}")
    else:
        status_line("torch_cuda_available", False, "torch is not importable")

    anomalib_ok, anomalib_module, anomalib_msg = import_object("anomalib")
    version = getattr(anomalib_module, "__version__", "") if anomalib_ok else anomalib_msg
    status_line("anomalib_import", anomalib_ok, version)
    all_ok = all_ok and anomalib_ok

    mvtecad_ok, _, mvtecad_msg = import_object("anomalib.data", "MVTecAD")
    mvtecad_detail = "from anomalib.data import MVTecAD" if mvtecad_ok else mvtecad_msg
    status_line("MVTecAD_import", mvtecad_ok, mvtecad_detail)
    all_ok = all_ok and mvtecad_ok

    fastflow_ok, _, fastflow_msg = import_object("anomalib.models", "Fastflow")
    fastflow_detail = "from anomalib.models import Fastflow" if fastflow_ok else fastflow_msg
    status_line("Fastflow_import", fastflow_ok, fastflow_detail)
    all_ok = all_ok and fastflow_ok

    engine_ok, _, engine_msg = import_object("anomalib.engine", "Engine")
    engine_detail = "from anomalib.engine import Engine" if engine_ok else engine_msg
    status_line("Engine_import", engine_ok, engine_detail)
    all_ok = all_ok and engine_ok

    category_dir = dataset_root / category
    expected_dirs = {
        "dataset_root_exists": dataset_root,
        "category_dir_exists": category_dir,
        "train_good_exists": category_dir / "train" / "good",
        "test_exists": category_dir / "test",
        "ground_truth_exists": category_dir / "ground_truth",
    }

    print()
    for name, path in expected_dirs.items():
        exists = path.is_dir()
        status_line(name, exists, str(path))
        all_ok = all_ok and exists

    if not category_dir.is_dir():
        print()
        print("Dataset is not ready. Do not download automatically.")
        print("Please place the MVTec AD metal_nut dataset at:")
        print(str(DEFAULT_DATASET_ROOT / DEFAULT_CATEGORY))

    print()
    status_line("overall", all_ok, "ready for --run-train" if all_ok else "not ready")
    return all_ok


def build_datamodule(dataset_root: Path, category: str, batch_size: int, image_size: int):
    """Create the MVTecAD datamodule with a small resize pipeline."""
    from anomalib.data import MVTecAD
    from torchvision.transforms import v2

    transforms = v2.Compose([v2.Resize((image_size, image_size), antialias=True)])
    return MVTecAD(
        root=dataset_root,
        category=category,
        train_batch_size=batch_size,
        eval_batch_size=batch_size,
        num_workers=0,
        augmentations=transforms,
    )


def run_train(args: argparse.Namespace) -> None:
    """Run a small Fastflow training/test/predict loop."""
    from anomalib.engine import Engine
    from anomalib.models import Fastflow

    dataset_root = Path(args.dataset_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    max_epochs = args.max_epochs if args.max_epochs is not None else TRAIN_DEFAULT_MAX_EPOCHS
    batch_size = args.batch_size if args.batch_size is not None else TRAIN_DEFAULT_BATCH_SIZE

    if not check_environment(dataset_root, args.category):
        raise SystemExit("Dataset or environment is not ready; training was not started.")

    datamodule = build_datamodule(
        dataset_root=dataset_root,
        category=args.category,
        batch_size=batch_size,
        image_size=args.image_size,
    )
    print(f"pre_trained={args.pre_trained}")
    model = Fastflow(backbone="resnet18", pre_trained=args.pre_trained)

    engine_kwargs: dict[str, Any] = {
        "default_root_dir": output_dir,
        "max_epochs": max_epochs,
    }

    torch_ok, torch_module, _ = import_object("torch")
    if torch_ok and torch_module.cuda.is_available():
        engine_kwargs.update({"accelerator": "gpu", "devices": 1})
    else:
        engine_kwargs.update({"accelerator": "cpu"})

    engine = Engine(**engine_kwargs)

    print()
    print("Starting Fastflow training")
    print(f"max_epochs: {max_epochs}")
    print(f"batch_size: {batch_size}")
    print(f"image_size: {args.image_size}")
    print(f"output_dir: {output_dir}")

    engine.fit(model=model, datamodule=datamodule)
    engine.test(model=model, datamodule=datamodule)
    engine.predict(model=model, datamodule=datamodule)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal Anomalib Fastflow experiment for MVTec AD metal_nut."
    )
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="MVTec AD root directory.")
    parser.add_argument("--category", default=DEFAULT_CATEGORY, help="MVTec AD category, default: metal_nut.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Training output directory.")
    parser.add_argument(
        "--max-epochs",
        type=int,
        default=None,
        help=f"Training epochs. Defaults to {TRAIN_DEFAULT_MAX_EPOCHS} with --run-train.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=f"Batch size. Defaults to {TRAIN_DEFAULT_BATCH_SIZE} with --run-train.",
    )
    parser.add_argument("--image-size", type=int, default=DEFAULT_IMAGE_SIZE, help="Resize square image size.")
    parser.add_argument(
        "--pre-trained",
        type=str2bool,
        default=False,
        help="Use timm pretrained weights. Default false keeps the smoke test offline.",
    )
    parser.add_argument("--check-only", action="store_true", help="Only check environment and dataset layout.")
    parser.add_argument("--run-train", action="store_true", help="Explicitly run training/test/predict.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root).expanduser().resolve()

    if args.run_train:
        run_train(args)
        return 0

    if args.max_epochs is None:
        args.max_epochs = CHECK_DISPLAY_MAX_EPOCHS
    if args.batch_size is None:
        args.batch_size = CHECK_DISPLAY_BATCH_SIZE

    print("Default mode: check-only. Pass --run-train to start training.")
    print(f"configured_max_epochs: {args.max_epochs}")
    print(f"configured_batch_size: {args.batch_size}")
    print(f"configured_image_size: {args.image_size}")
    print(f"pre_trained={args.pre_trained}")
    print()
    check_environment(dataset_root, args.category)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
