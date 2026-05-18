import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DUMMY_SCRIPT = ROOT / "CV_Project" / "scripts" / "infer_one_dummy.py"
REQUIRED_FIELDS = {
    "ok",
    "label",
    "score",
    "threshold",
    "defect_type",
    "message",
    "image_path",
    "heatmap_path",
}


def make_test_image(path):
    png_1x1_gray = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.write_bytes(png_1x1_gray)


def run_dummy(image_path, pose, product_id):
    cmd = [
        sys.executable,
        str(DUMMY_SCRIPT),
        "--image",
        str(image_path),
        "--pose",
        pose,
        "--product-id",
        product_id,
    ]

    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    if completed.returncode != 0:
        raise AssertionError(
            f"dummy script exited with {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "dummy script stdout is not valid JSON\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        ) from exc

    missing_fields = REQUIRED_FIELDS - result.keys()
    if missing_fields:
        raise AssertionError(f"dummy JSON missing fields: {sorted(missing_fields)}")

    return result


def assert_branch(result, expected_label, expected_ok):
    if result.get("label") != expected_label:
        raise AssertionError(f"expected label {expected_label}, got {result}")
    if result.get("ok") is not expected_ok:
        raise AssertionError(f"expected ok={expected_ok}, got {result}")


def main():
    if not DUMMY_SCRIPT.exists():
        raise AssertionError(f"dummy script not found: {DUMMY_SCRIPT}")

    with tempfile.TemporaryDirectory(prefix="dummy_smoke_") as temp_dir:
        temp_path = Path(temp_dir)

        ok_image = temp_path / "ok_probe.png"
        make_test_image(ok_image)
        ok_result = run_dummy(ok_image, pose="P_OK", product_id="PART_OK")
        assert_branch(ok_result, expected_label="OK", expected_ok=True)

        ng_image = temp_path / "ng_probe.png"
        make_test_image(ng_image)
        ng_result = run_dummy(ng_image, pose="P_NG", product_id="PART_NG")
        assert_branch(ng_result, expected_label="NG", expected_ok=False)

    print("dummy smoke test passed")


if __name__ == "__main__":
    main()
