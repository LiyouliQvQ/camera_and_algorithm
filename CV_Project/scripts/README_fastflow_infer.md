# FastFlow Single-Image Inference

`infer_one_fastflow.py` is the planned GUI-facing single-image inference entry
for Fastflow checkpoints.

## Command

Run with the real `cv_lab` Python:

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO="0"
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\infer_one_fastflow.py --image D:\path\to\image.png --checkpoint D:\path\to\model.ckpt --threshold 0.5 --pose P01 --product-id PART001 --output-dir D:\run_code\camera_and_algorithm\CV_Project\fastflow_infer_outputs --device auto
```

## JSON Protocol

stdout contains only one JSON object compatible with the GUI detector protocol:

```json
{
  "ok": true,
  "label": "OK",
  "score": 0.0,
  "threshold": 0.5,
  "defect_type": "none",
  "message": "",
  "image_path": "",
  "heatmap_path": "",
  "boxes": [],
  "pose": "",
  "product_id": ""
}
```

Debug logs and Anomalib output go to stderr.

## Notes

- The script constructs `Fastflow(backbone="resnet18", pre_trained=False)` to
  avoid Hugging Face/timm downloads during inference.
- If `anomaly_map` is available, a simple grayscale heatmap PNG is saved to
  `--output-dir` and returned as `heatmap_path`.
- If heatmap extraction is unstable for a future Anomalib API, the script keeps
  `heatmap_path=""` instead of failing the GUI call.
- Do not commit inference outputs, heatmaps, checkpoints, datasets, or files
  under `CV_Project/results/`.
