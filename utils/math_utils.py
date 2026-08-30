import math

class MathUtils:
    @staticmethod
    def get_angle(p1, p2, p3):
        """
        計算三點之間的夾角 (p2為頂點)[cite: 1]。
        傳入的 p1, p2, p3 需為包含 'x' 與 'y' 鍵值的字典。
        """
        x1, y1 = p1['x'], p1['y']
        x2, y2 = p2['x'], p2['y']
        x3, y3 = p3['x'], p3['y']

        # 計算弧度並轉換為角度[cite: 1]
        radians = math.atan2(y3 - y2, x3 - x2) - math.atan2(y1 - y2, x1 - x2)
        angle = abs(radians * 180.0 / math.pi)
        
        # 確保角度落在 0~180 度之間[cite: 1]
        if angle > 180.0:
            angle = 360.0 - angle
            
        return angle

    @staticmethod
    def get_horizontal_angle(p1, p2):
        """
        計算兩點連線與水平線的夾角 (例如腳跟到腳尖)[cite: 1]。
        傳入的 p1, p2 需為包含 'x' 與 'y' 鍵值的字典。
        """
        x1, y1 = p1['x'], p1['y']
        x2, y2 = p2['x'], p2['y']

        # 加上 abs() 絕對值，確保無論面向左邊或右邊，算出來的角度都會是銳角(0~90度)[cite: 1]
        dy = abs(y2 - y1)
        dx = abs(x2 - x1)
        
        # 計算與水平線的夾角[cite: 1]
        radians = math.atan2(dy, dx)
        return radians * 180.0 / math.pi
