import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

class UIRenderer:
    def __init__(self, font_path="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        """
        初始化 UI 渲染器 (效能最佳化版)。
        實作文字遮罩快取機制，大幅降低 Jetson Nano 的 CPU 負載。
        """
        self.font_path = font_path
        
        # UI 區塊的位置與大小 (對應原 CSS 設定)
        self.x, self.y = 30, 30
        self.w, self.h = 480, 180
        
        # 預先建立一張全白的 Numpy 陣列，用於快速合成半透明背景
        self.white_bg = np.ones((self.h, self.w, 3), dtype=np.uint8) * 255
        
        # 狀態追蹤變數 (用來判斷是否需要重新渲染 PIL)
        self.last_mode_text = ""
        self.last_info_text = ""
        self.last_feedback_text = ""
        self.last_color = None
        
        # 暫存的文字圖層
        self.text_bgr = None
        self.text_alpha = None
        
        try:
            self.font_mode = ImageFont.truetype(self.font_path, 24)
            self.font_info = ImageFont.truetype(self.font_path, 32)
            self.font_feedback = ImageFont.truetype(self.font_path, 24)
        except IOError:
            print(f"⚠️ 警告: 找不到字型檔 {self.font_path}！")
            self.font_mode = ImageFont.load_default()
            self.font_info = ImageFont.load_default()
            self.font_feedback = ImageFont.load_default()

    def update_text_cache(self, mode_text, info_text, feedback_state):
        """
        只在文字內容改變時呼叫：利用 PIL 重新生成透明的文字遮罩
        """
        # 建立一個只涵蓋 UI 大小的透明 RGBA 畫布 (不對整張影像處理)
        image_pil = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image_pil)

        mode_color = (255, 165, 0, 255)
        info_color = (0, 0, 0, 255)
        
        b, g, r = feedback_state.color.value
        feedback_color = (r, g, b, 255)

        # 這裡的座標是相對於 480x180 畫布的內部座標
        draw.text((20, 20), mode_text, font=self.font_mode, fill=mode_color)
        draw.text((20, 70), info_text, font=self.font_info, fill=info_color)
        draw.text((20, 130), feedback_state.text, font=self.font_feedback, fill=feedback_color)

        # 轉為 Numpy 陣列
        text_rgba = np.array(image_pil)

        # 拆分出 BGR 通道與 Alpha 透明通道
        self.text_bgr = cv2.cvtColor(text_rgba, cv2.COLOR_RGBA2BGR)
        
        # 將 Alpha 歸一化為 0.0 ~ 1.0 的浮點數矩陣，並擴充維度以利後續矩陣相乘
        self.text_alpha = text_rgba[:, :, 3] / 255.0
        self.text_alpha = np.expand_dims(self.text_alpha, axis=-1)

        # 更新追蹤狀態
        self.last_mode_text = mode_text
        self.last_info_text = info_text
        self.last_feedback_text = feedback_state.text
        self.last_color = feedback_state.color

    def draw_dashboard(self, image, mode_text, info_text, feedback_state):
        """
        利用 Numpy 矩陣局部疊加，避開 CPU 迴圈的極速渲染
        """
        # 1. 檢查畫面文字是否發生變化
        text_changed = (
            mode_text != self.last_mode_text or
            info_text != self.last_info_text or
            feedback_state.text != self.last_feedback_text or
            feedback_state.color != self.last_color
        )

        # 只有在文字有變動，或是剛啟動沒有快取時，才去呼叫肥重的 PIL
        if text_changed or self.text_bgr is None:
            self.update_text_cache(mode_text, info_text, feedback_state)

        # 2. 擷取原圖中對應 UI 位置的 ROI (Region of Interest)
        roi = image[self.y : self.y + self.h, self.x : self.x + self.w]

        # 3. 繪製半透明白色背景
        # 直接拿預先做好的白底 self.white_bg 跟 ROI 融合，權重對應 rgba(255, 255, 255, 0.9)
        blended_bg = cv2.addWeighted(self.white_bg, 0.9, roi, 0.1, 0)

        # 4. 疊加高畫質文字遮罩 (利用 Numpy 向量化矩陣運算，速度極快)
        # 演算法：最終像素 = 文字圖 * Alpha + 背景圖 * (1 - Alpha)
        roi_final = (self.text_bgr * self.text_alpha + blended_bg * (1 - self.text_alpha)).astype(np.uint8)

        # 5. 將處理完的小區塊塞回原來的全螢幕影像中
        image[self.y : self.y + self.h, self.x : self.x + self.w] = roi_final
        
        return image
