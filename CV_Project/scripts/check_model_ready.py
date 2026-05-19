import argparse
import importlib.util
from pathlib import Path


SUPPORTED_SUFFIXES = {".ckpt", ".pt", ".pth", ".onnx", ".engine"}


def check_import(module_name):
    """Return whether a Python module can be imported in the current environment."""
    return importlib.util.find_spec(module_name) is not None


def main():
    parser = argparse.ArgumentParser(description="Check whether a model file and AI environment are ready.")
    parser.add_argument("--model", required=True, help="Path to the model file to check.")
    args = parser.parse_args()

    model_path = Path(args.model).expanduser()
    exists = model_path.is_file()
    suffix = model_path.suffix.lower()
    suffix_ok = suffix in SUPPORTED_SUFFIXES
    torch_ok = check_import("torch")
    anomalib_ok = check_import("anomalib")

    print("Model readiness check")
    print("=====================")
    print(f"model_path: {model_path}")
    print(f"model_exists: {'OK' if exists else 'MISSING'}")
    print(f"model_suffix: {suffix or '<none>'}")
    print(f"suffix_supported: {'OK' if suffix_ok else 'UNSUPPORTED'}")
    print(f"torch_import: {'OK' if torch_ok else 'MISSING'}")
    print(f"anomalib_import: {'OK' if anomalib_ok else 'MISSING'}")

    if exists and suffix_ok and torch_ok and anomalib_ok:
        print("overall: READY")
        return 0

    print("overall: NOT_READY")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
