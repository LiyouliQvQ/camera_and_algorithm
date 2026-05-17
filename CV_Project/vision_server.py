import socket
import time

def start_vision_server():
    # 1. 创建 TCP Socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 绑定本地 IP (127.0.0.1) 和一个不冲突的端口 (比如 8080)
    server.bind(('127.0.0.1', 8080)) 
    # 开始监听，最多允许 1 个机械臂排队
    server.listen(1)
    
    print("=======================================")
    print("👁️ [视觉系统] 已启动，正在端口 8080 监听...")
    print("=======================================")

    # 代码会卡在这里，直到机械臂连上来
    conn, addr = server.accept()
    print(f"✅ [视觉系统] 艾力特机械臂已连接！IP地址: {addr}")

    while True:
        # 等待接收机械臂的指令 (每次最多接收 1024 字节)
        data = conn.recv(1024).decode('utf-8')
        if not data:
            break # 如果断开连接就退出循环
            
        print(f"\n📥 [视觉系统] 收到机械臂指令: {data}")
        
        if data == "SNAP_POS_1":
            print("📸 [视觉系统] 正在触发海康相机拍照...")
            time.sleep(0.5) # 模拟相机曝光和传输时间
            
            print("🧠 [视觉系统] 正在调用 PatchCore 模型进行异常检测...")
            time.sleep(1) # 模拟刚才我们跑引擎推理的时间
            
            # 【核心逻辑】：这里本来应该填入你刚才跑的 AI 结果
            # 为了演示，我们直接假装它发现了一个砂眼
            ai_result = "NG_DEFECT" 
            
            print(f"📤 [视觉系统] 发送判定结果给机械臂: {ai_result}")
            # 把字符串转成字节流发回去
            conn.sendall(ai_result.encode('utf-8'))
            
        elif data == "QUIT":
            print("🛑 [视觉系统] 收到停机指令，关闭服务器。")
            break

    conn.close()
    server.close()

if __name__ == '__main__':
    start_vision_server()