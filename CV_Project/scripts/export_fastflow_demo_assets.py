"""Export Fastflow metal_nut demo assets for meeting slides.

This script does not train or infer. It copies selected Anomalib visualization
images from a completed 30 epoch run and records source image / GT mask paths.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


CV_PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_IMAGES = (
    CV_PROJECT_DIR
    / "results"
    / "fastflow_mvtec_metal_nut"
    / "Fastflow"
    / "MVTecAD"
    / "metal_nut"
    / "latest"
    / "images"
)
DEFAULT_DATASET_ROOT = CV_PROJECT_DIR / "datasets" / "MVTec" / "metal_nut"
DEFAULT_OUTPUT_DIR = CV_PROJECT_DIR / "output_results" / "fastflow_demo_metal_nut"

METRICS = {
    "image_AUROC": 0.9604105949401855,
    "image_F1Score": 0.9680851101875305,
    "pixel_AUROC": 0.9528902173042297,
    "pixel_F1Score": 0.6568253636360168,
}

EXPERIMENT = {
    "Dataset": "MVTec AD metal_nut",
    "Model": "FastFlow",
    "Backbone": "ResNet18",
    "pre_trained": True,
    "epochs": 30,
    "image_size": 256,
    "batch_size": 4,
    "GPU": "RTX 3060 Ti",
    "note": "Group meeting reproduction experiment, not differential housing field data.",
}

DEFECT_CLASSES = ("bent", "color", "flip", "scratch")
GOOD_CLASS = "good"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Fastflow demo assets for PPT.")
    parser.add_argument("--results-images", default=str(DEFAULT_RESULTS_IMAGES), help="Anomalib latest/images path.")
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="MVTec metal_nut dataset root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Demo asset output directory.")
    parser.add_argument("--defect-k", type=int, default=3, help="Number of examples per defect class.")
    parser.add_argument("--good-k", type=int, default=2, help="Number of good examples.")
    return parser.parse_args()


def candidate_gt_mask(dataset_root: Path, class_name: str, stem: str) -> Path | None:
    """Return the matching MVTec ground-truth mask path when it exists."""
    if class_name == GOOD_CLASS:
        return None

    candidates = (
        dataset_root / "ground_truth" / class_name / f"{stem}_mask.png",
        dataset_root / "ground_truth" / class_name / f"{stem}.png",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def candidate_source_image(dataset_root: Path, class_name: str, filename: str) -> Path | None:
    """Return the matching MVTec test image path when it exists."""
    path = dataset_root / "test" / class_name / filename
    return path if path.is_file() else None


def select_cases(results_images: Path, dataset_root: Path, defect_k: int, good_k: int) -> list[dict[str, str]]:
    """Select deterministic examples for each class without reading image contents."""
    cases: list[dict[str, str]] = []
    class_plan = {class_name: defect_k for class_name in DEFECT_CLASSES}
    class_plan[GOOD_CLASS] = good_k

    for class_name, count in class_plan.items():
        class_dir = results_images / class_name
        if not class_dir.is_dir():
            raise FileNotFoundError(f"missing visualization class directory: {class_dir}")

        for rank, vis_path in enumerate(sorted(class_dir.glob("*.png"))[:count], start=1):
            source_image = candidate_source_image(dataset_root, class_name, vis_path.name)
            gt_mask = candidate_gt_mask(dataset_root, class_name, vis_path.stem)
            cases.append(
                {
                    "class": class_name,
                    "rank": str(rank),
                    "visualization_path": str(vis_path.resolve()),
                    "source_image_path": str(source_image.resolve()) if source_image else "",
                    "gt_mask_path": str(gt_mask.resolve()) if gt_mask else "",
                }
            )
    return cases


def write_metrics_summary(output_dir: Path) -> Path:
    """Write markdown metrics summary for PPT notes."""
    path = output_dir / "metrics_summary.md"
    lines = [
        "# FastFlow MVTec AD metal_nut 30 Epoch Reproduction",
        "",
        "## Experiment",
        "",
    ]
    for key, value in EXPERIMENT.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
        ]
    )
    for key, value in METRICS.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "These metrics are from the 30 epoch `pre_trained=True` reproduction run.",
            "They are for group meeting demonstration and are not differential housing field-data results.",
            "",
            "Do not commit `datasets/`, `results/`, `output_results/`, checkpoints, source images, GT masks, heatmaps, or visualization images.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_metrics_json(output_dir: Path) -> Path:
    """Write machine-readable metrics summary."""
    path = output_dir / "metrics_summary.json"
    payload = {"experiment": EXPERIMENT, "metrics": METRICS}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def copy_visualizations(output_dir: Path, cases: list[dict[str, str]]) -> None:
    """Copy selected Anomalib visualization PNGs into class subdirectories."""
    for case in cases:
        src = Path(case["visualization_path"])
        class_dir = output_dir / "visualizations" / case["class"]
        class_dir.mkdir(parents=True, exist_ok=True)
        dst = class_dir / f"{case['rank']}_{src.name}"
        shutil.copy2(src, dst)
        case["copied_visualization_path"] = str(dst.resolve())


def write_selected_cases(output_dir: Path, cases: list[dict[str, str]]) -> tuple[Path, Path]:
    """Write selected case manifests as CSV and Markdown."""
    csv_path = output_dir / "selected_cases.csv"
    fieldnames = [
        "class",
        "rank",
        "copied_visualization_path",
        "visualization_path",
        "source_image_path",
        "gt_mask_path",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for case in cases:
            writer.writerow({name: case.get(name, "") for name in fieldnames})

    md_path = output_dir / "selected_cases.md"
    lines = [
        "# Selected FastFlow Demo Cases",
        "",
        "Selected visualization images are copied from the 30 epoch Anomalib output.",
        "Original images and GT masks are recorded as paths only; no fake overlays are generated.",
        "",
        "| Class | Rank | Visualization | Source image | GT mask |",
        "|---|---:|---|---|---|",
    ]
    for case in cases:
        lines.append(
            "| {class_name} | {rank} | {vis} | {src} | {gt} |".format(
                class_name=case["class"],
                rank=case["rank"],
                vis=case.get("copied_visualization_path", ""),
                src=case.get("source_image_path", ""),
                gt=case.get("gt_mask_path", "") or "N/A",
            )
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> int:
    args = parse_args()
    results_images = Path(args.results_images).expanduser().resolve()
    dataset_root = Path(args.dataset_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not results_images.is_dir():
        raise FileNotFoundError(f"results images directory does not exist: {results_images}")
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"dataset root does not exist: {dataset_root}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cases = select_cases(
        results_images=results_images,
        dataset_root=dataset_root,
        defect_k=args.defect_k,
        good_k=args.good_k,
    )
    copy_visualizations(output_dir, cases)
    metrics_md = write_metrics_summary(output_dir)
    metrics_json = write_metrics_json(output_dir)
    cases_csv, cases_md = write_selected_cases(output_dir, cases)

    print(f"output_dir: {output_dir}")
    print(f"metrics_summary_md: {metrics_md}")
    print(f"metrics_summary_json: {metrics_json}")
    print(f"selected_cases_csv: {cases_csv}")
    print(f"selected_cases_md: {cases_md}")
    print(f"selected_cases_count: {len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
