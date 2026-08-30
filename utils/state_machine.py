from enum import Enum
from dataclasses import dataclass

# 使用 Python 的 Enum 來替代 JS 的常數物件[cite: 1]
class UIState(Enum):
    # 針對 OpenCV 進行優化，直接定義對應的 BGR 色彩數值
    RED = (0, 0, 255)
    YELLOW = (0, 255, 255)
    GREEN = (0, 255, 0)

class ExerciseState(Enum):
    IDLE = 'IDLE'
    DOWN = 'DOWN'
    UP = 'UP'
    HOLDING = 'HOLDING'
    COMPLETED = 'COMPLETED'

# 利用 dataclass 來建立資料結構，對應原本的類別建構子[cite: 1]
@dataclass
class PoseIssue:
    msg: str
    pts: list  # 紀錄發生姿勢錯誤的骨架節點，方便後續擴充在畫面上特別標示

@dataclass
class FeedbackState:
    text: str = "準備開始,請擺出動作..."
    color: UIState = UIState.RED
