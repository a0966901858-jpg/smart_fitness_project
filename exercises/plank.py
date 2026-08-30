import time
from utils.math_utils import MathUtils
from utils.state_machine import UIState, PoseIssue, FeedbackState

class Plank:
    def __init__(self):
        # 初始化累積時間與狀態機[cite: 1]
        self.accumulated_time = 0.0
        self.last_tick = 0.0
        self.is_planking = False

    def validate(self, lm_list):
        """
        驗證棒式姿勢，包含身體是否平直(避免塌腰/翹臀)、膝蓋是否打直，以及手肘的支撐角度[cite: 1]。
        """
        issues = []
        
        # 取得所需關節節點[cite: 1]
        shoulder = lm_list[12]
        elbow = lm_list[14]
        hip = lm_list[24]
        knee = lm_list[26]
        ankle = lm_list[28]

        # 1. 身體角度 (判斷是否塌腰/翹臀)[cite: 1]
        body_angle = MathUtils.get_angle(shoulder, hip, ankle)
        if body_angle < 140:
            issues.append(PoseIssue("核心未收緊(塌腰/翹臀)", [shoulder, hip, ankle]))

        # 2. 膝蓋角度 (判斷是否彎曲)[cite: 1]
        knee_angle = MathUtils.get_angle(hip, knee, ankle)
        if knee_angle < 140:
            issues.append(PoseIssue("膝蓋彎曲(請打直雙腿)", [hip, knee, ankle]))

        # 3. 手肘與肩膀垂直度[cite: 1]
        vertical_point = {'x': elbow['x'], 'y': elbow['y'] - 100}
        arm_alignment = MathUtils.get_angle(vertical_point, elbow, shoulder)
        if arm_alignment > 40:
            issues.append(PoseIssue("手肘未垂直於肩膀下方", [shoulder, elbow]))

        return {'is_valid': len(issues) == 0, 'issues': issues}

    def process_frame(self, lm_list):
        """
        處理每一幀的棒式判定與 60 秒倒數邏輯[cite: 1]。
        """
        # 利用肩膀與腳踝的長寬差來判定是否處於水平趴姿[cite: 1]
        body_h_diff = abs(lm_list[11]['y'] - lm_list[27]['y'])
        body_w_diff = abs(lm_list[11]['x'] - lm_list[27]['x'])

        dashboard_info = ""
        feedback = None

        # 寬鬆門檻：身體高度差不大，代表呈現趴姿[cite: 1]
        if body_h_diff < body_w_diff * 0.8:
            val_res = self.validate(lm_list)
            
            if val_res['is_valid']:
                if not self.is_planking:
                    self.is_planking = True
                    self.last_tick = time.time()
                
                # 限制單次增加的秒數(最大不超過0.5秒)，防止嚴重掉幀時時間暴衝[cite: 1]
                current_time = time.time()
                time_delta = min(current_time - self.last_tick, 0.5)
                self.accumulated_time += time_delta
                self.last_tick = current_time

                # 計算剩餘秒數[cite: 1]
                remain = max(0, 60 - int(self.accumulated_time))
                
                if remain > 0:
                    dashboard_info = f"棒式倒數: {remain} 秒"
                    feedback = FeedbackState("核心收緊,棒式維持中!", UIState.GREEN)
                else:
                    dashboard_info = "目標達成!太棒了!"
                    feedback = FeedbackState("恭喜完成60秒棒式!", UIState.GREEN)
            else:
                # 修復偷吃步 Bug：姿勢錯誤時必須中斷狀態，避免將錯誤的時間累加[cite: 1]
                self.is_planking = False
                feedback = FeedbackState(f"{val_res['issues'][0].msg}\n(請即時調整姿勢)", UIState.YELLOW)
        else:
            self.is_planking = False
            dashboard_info = "請撐起進入棒式"
            feedback = FeedbackState("準備開始...(請側對鏡頭)", UIState.RED)

        return dashboard_info, feedback
