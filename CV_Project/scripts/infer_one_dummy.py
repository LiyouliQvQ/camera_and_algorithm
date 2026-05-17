import argparse
import json
import sys
from pathlib import Path


def build_result(image_path, pose="", product_id=""):
    image_name = Path(image_path).stem.lower()
    is_ng = any(keyword in image_name for keyword in ("ng", "bad", "defect"))

    if is_ng:
        return {
            "ok": False,
            "label": "NG",
            "score": 0.9,
            "threshold": 0.5,
            "defect_type": "dummy_defect",
            "message": "dummy检测到缺陷",
            "image_path": str(image_path),
            "heatmap_path": "",
            "pose": pose,
            "product_id": product_id,
        }

    return {
        "ok": True,
        "label": "OK",
        "score": 0.0,
        "threshold": 0.5,
        "defect_type": "none",
        "message": "dummy检测正常",
        "image_path": str(image_path),
        "heatmap_path": "",
        "pose": pose,
        "product_id": product_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Dummy single-image defect inference.")
    parser.add_argument("--image", required=True, help="Path to the image to inspect.")
    parser.add_argument("--pose", default="", help="Optional robot pose name.")
    parser.add_argument("--product-id", default="", help="Optional product id.")
    args = parser.parse_args()

    image_path = Path(args.image).expanduser()
    if not image_path.exists():
        print(f"image does not exist: {image_path}", file=sys.stderr)
        return 2

    result = build_result(image_path.resolve(), pose=args.pose, product_id=args.product_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
