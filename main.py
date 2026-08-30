import cv2
import mediapipe as mp
from flask import Flask, Response

# 引入規劃好的模組
from exercises.squat import Squat
from exercises.lunge import Lunge
from exercises.plank import Plank
from utils.state_machine import ExerciseState, UIState, FeedbackState
from utils.ui_renderer import UIRenderer

app = Flask(__name__)

# 定義 GStreamer Pipeline：混合加速模式 (軟體解碼 jpegdec + 硬體轉換 nvvidconv)
def gstreamer_usb_pipeline(sensor_id=0, width=1280, height=720, framerate=30):
    return (
        f"v4l2src device=/dev/video{sensor_id} ! "
        f"image/jpeg, width=(int){width}, height=(int){height}, framerate=(fraction){framerate}/1 ! "
        f"jpegdec ! "
        f"nvvidconv ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! "
        f"appsink drop=1"
    )

def generate_frames():
    print("Smart Fitness Mirror 影像串流初始化中...")

    # 初始化 MediaPipe Pose AI 引擎
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    pose = mp_pose.Pose(
        model_complexity=1,  # Edge 裝置可視效能調整為 0 或 1
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # 啟動相機 (改用 GStreamer API 進行硬體加速)
    pipeline = gstreamer_usb_pipeline(sensor_id=0, width=1280, height=720, framerate=30)
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    
    # 檢查相機是否成功透過 GStreamer 開啟
    if not cap.isOpened():
        print("GStreamer 啟動失敗，退回標準 CPU 讀取模式...")
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    else:
        print("GStreamer 硬體加速相機啟動成功！")

    # 實例化 UI 渲染器
    ui_renderer = UIRenderer()

    # 狀態管理器與緩衝切換參數
    exercise_instances = {
        "SQUAT": Squat(),
        "LUNGE": Lunge(),
        "PLANK": Plank()
    }
    
    current_mode_name = "SQUAT"
    current_exercise = exercise_instances[current_mode_name]

    candidate_mode = current_mode_name
    mode_switch_counter = 0
    MODE_SWITCH_THRESHOLD = 5

    # 初始化 UI 文字狀態
    mode_text = "[自動切換] 深蹲模式"
    info_text = "深蹲次數: 0"
    feedback = FeedbackState("準備開始...(請側對鏡頭)", UIState.RED)

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("無法讀取相機影像，串流中斷。")
            break

        # 畫面鏡像翻轉
        image = cv2.flip(image, 1)
        h, w, _ = image.shape

        # MediaPipe 需要 RGB 格式
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = pose.process(image_rgb)
        image_rgb.flags.writeable = True
        image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

        lm_list = []
        if results.pose_landmarks:
            # 畫骨架與關節點
            mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=4),
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=4)
            )

            # 座標轉換：將比例轉換回真實像素
            for lm in results.pose_landmarks.landmark:
                lm_list.append({
                    'x': lm.x * w,
                    'y': lm.y * h,
                    'z': lm.z * w,
                    'visibility': lm.visibility
                })

        # 確保抓到完整的 33 個骨架節點
        if len(lm_list) == 33:
            # 自動偵測切換模式
            can_switch = False
            if current_mode_name == "SQUAT" and current_exercise.state != ExerciseState.DOWN:
                can_switch = True
            elif current_mode_name == "LUNGE" and not current_exercise.is_holding:
                can_switch = True
            elif current_mode_name == "PLANK" and not current_exercise.is_planking:
                can_switch = True

            if can_switch:
                sx = (lm_list[11]['x'] + lm_list[12]['x']) / 2
                sy = (lm_list[11]['y'] + lm_list[12]['y']) / 2
                hx = (lm_list[23]['x'] + lm_list[24]['x']) / 2
                hy = (lm_list[23]['y'] + lm_list[24]['y']) / 2
                ax = (lm_list[27]['x'] + lm_list[28]['x']) / 2
                ay = (lm_list[27]['y'] + lm_list[28]['y']) / 2

                body_w = abs(sx - ax)
                body_h = abs(sy - ay)
                torso_h = abs(sy - hy)
                
                detected_mode = "SQUAT"
                ankle_dist_x = abs(lm_list[27]['x'] - lm_list[28]['x'])

                if body_w > body_h * 1.2:
                    detected_mode = "PLANK"
                elif ankle_dist_x > torso_h * 1.1:
                    detected_mode = "LUNGE"

                # 緩衝切換機制(Debounce)
                if detected_mode != current_mode_name:
                    if detected_mode == candidate_mode:
                        mode_switch_counter += 1
                        if mode_switch_counter >= MODE_SWITCH_THRESHOLD:
                            current_mode_name = detected_mode
                            current_exercise = exercise_instances[current_mode_name]

                            mode_tw = {"SQUAT": "深蹲", "LUNGE": "弓箭步", "PLANK": "棒式"}
                            mode_text = f"[自動切換] {mode_tw[current_mode_name]}模式"
                            feedback = FeedbackState("切換模式,準備開始...(請側對鏡頭)", UIState.RED)

                            mode_switch_counter = 0
                            candidate_mode = detected_mode
                    else:
                        mode_switch_counter = 1
                        candidate_mode = detected_mode
                else:
                    mode_switch_counter = 0
                    candidate_mode = detected_mode

            # 核心判定邏輯
            dash_info, fb_state = current_exercise.process_frame(lm_list)

            # 更新文字資訊
            if dash_info:
                info_text = dash_info
            
            if mode_switch_counter == 0 and candidate_mode == current_mode_name:
                if fb_state:
                    feedback = fb_state

        # 將文字與資訊畫上影像
        image = ui_renderer.draw_dashboard(image, mode_text, info_text, feedback)

        # 將影像編碼為 JPEG 格式以供網路傳輸
        ret, buffer = cv2.imencode('.jpg', image)
        if not ret:
            continue
        frame = buffer.tobytes()

        # 透過 Generator yield 推送 Multipart 格式影像
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

@app.route('/')
def index():
    """首頁：提供全螢幕顯示的黑色背景 HTML"""
    return '''
    <html>
      <head>
        <title>Smart Fitness Mirror - Web Stream</title>
        <style>
          body { background-color: black; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }
          img { max-width: 100%; max-height: 100%; object-fit: contain; }
        </style>
      </head>
      <body>
        <img src="/video_feed" />
      </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    """提供影像串流的路由"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 智慧健身鏡伺服器已啟動！")
    print("請在筆電的瀏覽器中輸入以下網址觀看畫面：")
    print("👉 http://<Jetson_Nano_IP>:5000")
    print("="*50 + "\n")
    
    # 啟動 Flask 伺服器，允許外部網路 (0.0.0.0) 存取
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
