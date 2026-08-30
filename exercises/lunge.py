import time
from utils.math_utils import MathUtils
from utils.state_machine import UIState, PoseIssue, FeedbackState

class Lunge:
    def __init__(self):
        # 紀錄倒數計時的起始點與狀態[cite: 1]
        self.lunge_hold_start = 0
        self.is_holding = False

    def validate(self, lm_list):
        """
        驗證弓箭步的姿勢正確性，包含膝蓋彎曲度、後腳打直度以及身體直立度[cite: 1]。
        """
        issues = []
        
        # 取得左右腳節點[cite: 1]
        l_leg = {
            'hip': lm_list[23], 'knee': lm_list[25], 'ankle': lm_list[27],
            'heel': lm_list[29], 'toe': lm_list[31]
        }
        r_leg = {
            'hip': lm_list[24], 'knee': lm_list[26], 'ankle': lm_list[28],
            'heel': lm_list[30], 'toe': lm_list[32]
        }

        # 計算雙膝角度[cite: 1]
        l_knee_ang = MathUtils.get_angle(l_leg['hip'], l_leg['knee'], l_leg['ankle'])
        r_knee_ang = MathUtils.get_angle(r_leg['hip'], r_leg['knee'], r_leg['ankle'])

        # 判斷前後腳 (膝蓋彎曲角度較小的為前腳)[cite: 1]
        if l_knee_ang < r_knee_ang:
            front_leg, back_leg = l_leg, r_leg
            f_ang, b_ang = l_knee_ang, r_knee_ang
        else:
            front_leg, back_leg = r_leg, l_leg
            f_ang, b_ang = r_knee_ang, l_knee_ang

        # 姿勢幾何驗證
        # 1. 前膝彎曲未達 90 度 (允許範圍 80~130)[cite: 1]
        if not (80 <= f_ang <= 130):
            issues.append(PoseIssue(
                f"前膝彎曲未達90度({int(f_ang)}°)", 
                [front_leg['hip'], front_leg['knee'], front_leg['ankle']]
            ))
            
        # 2. 後腳未打直 (大於 130 度才算打直)[cite: 1]
        if b_ang <= 130:
            issues.append(PoseIssue(
                f"後腳未打直({int(b_ang)}°)", 
                [back_leg['hip'], back_leg['knee'], back_leg['ankle']]
            ))

        # 3. 後腳跟浮起過高[cite: 1]
        back_foot_angle = MathUtils.get_horizontal_angle(back_leg['heel'], back_leg['toe'])
        if back_foot_angle > 50:
            issues.append(PoseIssue("後腳跟浮起(請貼地)", [back_leg['heel'], back_leg['toe']]))

        # 4. 上半身未直立[cite: 1]
        shoulder = lm_list[11] if front_leg == l_leg else lm_list[12]
        vertical_point = {'x': front_leg['hip']['x'], 'y': front_leg['hip']['y'] - 100}
        trunk_angle = MathUtils.get_angle(vertical_point, front_leg['hip'], shoulder)
        
        if trunk_angle > 40:
            issues.append(PoseIssue(f"上半身未直立({int(trunk_angle)}°)", [shoulder, front_leg['hip']]))

        return {'is_valid': len(issues) == 0, 'issues': issues}

    def get_front_knee_angle(self, lm_list):
        """
        取得前腳的膝蓋角度，用於觸發狀態機判定[cite: 1]。
        """
        l_knee_ang = MathUtils.get_angle(lm_list[23], lm_list[25], lm_list[27])
        r_knee_ang = MathUtils.get_angle(lm_list[24], lm_list[26], lm_list[28])
        
        if l_knee_ang < r_knee_ang:
            pts = [lm_list[23], lm_list[25], lm_list[27]]
        else:
            pts = [lm_list[24], lm_list[26], lm_list[28]]
            
        return {'front_knee_ang': min(l_knee_ang, r_knee_ang), 'track_pts': pts}

    def process_frame(self, lm_list):
        """
        封裝弓箭步的動作狀態機 (FSM) 與物理邊界啟動邏輯[cite: 1]。
        """
        front_data = self.get_front_knee_angle(lm_list)
        front_knee_ang = front_data['front_knee_ang']

        # 計算相對比例門檻[cite: 1]
        torso_h = abs(((lm_list[11]['y'] + lm_list[12]['y']) / 2) - ((lm_list[23]['y'] + lm_list[24]['y']) / 2))
        ankle_dist_x = abs(lm_list[27]['x'] - lm_list[28]['x'])

        # 確保上下限門檻在每一幀即時運算[cite: 1]
        is_in_posture = (ankle_dist_x > torso_h * 0.6) and (front_knee_ang < 140)
        
        dashboard_info = ""
        feedback = None

        if is_in_posture:
            val_res = self.validate(lm_list)
            if val_res['is_valid']:
                if not self.is_holding:
                    self.is_holding = True
                    # 將 Python 的 time.time() 作為秒數基準[cite: 1]
                    self.lunge_hold_start = time.time()
                
                # 計算經過時間[cite: 1]
                elapsed = int(time.time() - self.lunge_hold_start)
                
                if elapsed < 5:
                    dashboard_info = f"維持中: {elapsed} 秒"
                    feedback = FeedbackState("姿勢完美!請繼續維持", UIState.GREEN)
                else:
                    dashboard_info = "完成!請換邊"
                    feedback = FeedbackState("目標達成!", UIState.GREEN)
            else:
                self.is_holding = False
                feedback = FeedbackState(f"{val_res['issues'][0].msg}\n(請即時調整姿勢)", UIState.YELLOW)
        else:
            self.is_holding = False
            dashboard_info = "請下蹲進入弓箭步"
            feedback = FeedbackState("準備開始...(請側對鏡頭)", UIState.RED)

        return dashboard_info, feedback
