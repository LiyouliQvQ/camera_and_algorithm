# PROJECT_OVERVIEW.md

## 项目名称

汽车差速器壳体工业视觉检测系统

## 当前目标

实现眼在手上的检测流程：

1. 艾利特 EC66 机械臂移动到指定检测位姿。
2. 海康工业相机软件触发拍照。
3. 保存当前点位图像。
4. 调用工业视觉异常检测算法。
5. 返回 OK / NG。
6. GUI 显示单点位结果和整件产品结果。

## 当前目录结构

```text
camera_and_algorithm/
  camera/
    vision_robot_inspection_gui.py
    ec66_hik_single_pose_capture.py
    hik_camera_gui.py
    MvImport/
    captures/
    inspection_captures/

  CV_Project/
    config.py
    main_system.py
    vision_server.py
    vision_server_ai.py
    robot_client.py
    train_my_data.py
    train_my_data_efficientAD.py
    anomalib/
    datasets/
    pre_trained/
    results/
    output_results/
```