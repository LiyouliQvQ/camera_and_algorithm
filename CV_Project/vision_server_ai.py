import cv2
import os


class VisionServer:
    def __init__(self):
        pass

    def infer(self, image_path):
        if not os.path.exists(image_path):
            raise Exception("图片不存在")

        image = cv2.imread(image_path)

        # 模拟检测（你后面换PatchCore）
        has_defect = True

        # 假设检测到缺陷位置 → 转成机械臂坐标
        pose = [0.4, 0.2, 0.3, 0, 3.14, 0]

        return has_defect, pose