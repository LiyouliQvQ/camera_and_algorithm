# FastFlow + MVTec AD metal_nut Minimal Experiment

This note is for a small Anomalib Fastflow experiment before integrating any
new model into the camera GUI.

## Why metal_nut

MVTec AD has a real screw-nut category named `metal_nut`. Use `metal_nut` for
the nut experiment. Do not use `hazelnut`; that is a food category and is not
the correct class for this test.

## Dataset Location

Place the MVTec AD category here:

```text
D:\run_code\camera_and_algorithm\CV_Project\datasets\MVTec\metal_nut
```

Expected structure:

```text
metal_nut/
  train/good/
  test/
  ground_truth/
```

The script does not download data and does not create dataset files.

## Check Only

Run from `D:\run_code\camera_and_algorithm`:

```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --check-only
```

The default mode is also check-only, so this is equivalent:

```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py
```

Do not use `conda run -n cv_lab`; this machine currently reports an
Access/OpenCL vendors error during conda activation.

## One Epoch Smoke Test

Only run training when the dataset is already present:

```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256
```

By default, `--pre-trained false` is used. This keeps the smoke test offline and
prevents `timm` from trying to download ResNet weights from Hugging Face. The
1 epoch offline result only verifies that the Fastflow training/test/predict
flow can run; its metrics do not represent real detection performance.

For better accuracy later, either run with network access:

```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256 --pre-trained true
```

or prepare the required `timm` pretrained weights in the local cache before
running.

On Windows PowerShell, set UTF-8 environment variables before running the smoke
test. This avoids Lightning/Rich progress output failing on GBK consoles:

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO="0"
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256 --pre-trained false
```

## Verified Smoke Test

Fastflow + MVTec AD `metal_nut` has completed `fit`, `test`, and `predict` in
the `cv_lab` environment:

```text
torch: 2.5.1+cu121
anomalib: 2.3.0dev
CUDA: available
GPU: NVIDIA GeForce RTX 3060 Ti
```

Metrics from the 1 epoch offline run:

```text
image_AUROC: 0.5171065330505371
image_F1Score: 0.8888888955116272
pixel_AUROC: 0.7789766192436218
pixel_F1Score: 0.3588261902332306
```

These metrics are only a process verification result from `max_epochs=1` with
`pre_trained=False`. They do not represent final inspection performance.

## Output Directory

Default output directory:

```text
D:\run_code\camera_and_algorithm\CV_Project\results\fastflow_mvtec_metal_nut
```

Do not commit files from `CV_Project/results/`. Also do not commit datasets,
model weights, prediction images, or heatmaps.

## Later: Differential Housing Data

After the MVTec `metal_nut` API path is verified, create a separate script or
configuration for the self-collected differential housing dataset. Prefer the
existing `Folder`-style Anomalib layout for collected images, keep the same
subprocess + JSON boundary for GUI integration, and do not import PyTorch or
Anomalib directly in the Tkinter GUI process.

The next integration step is to add `CV_Project/scripts/infer_one_fastflow.py`
for single-image inference with GUI-compatible JSON output.
