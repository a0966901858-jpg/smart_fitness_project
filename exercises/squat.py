from utils.math_utils import MathUtils
from utils.state_machine import ExerciseState, UIState, PoseIssue, FeedbackState

class Squat:
    def __init__(self):
        # 初始狀態與計數器[cite: 1]
        self.count = 0
        self.state = ExerciseState.IDLE
        self.hit_target_depth = False
        
        # 動作限制門檻[cite: 1]
        self.SQUAT_FOOT_MAX_ANGLE = 35
        self.SQUAT_TRUNK_MAX_ANGLE = 45

    def get_working_leg(self, lm_list):
        """
        利用 Z 軸深度判斷目前是左側還是右側面對鏡頭，
        動態選取距離鏡頭較近的腿部作為計算基準[cite: 1]。
        """
        # 加總各節點的 Z 軸數值 (數值越小代表越靠近鏡頭)[cite: 1]
        l_z = lm_list[23]['z'] + lm_list[25]['z'] + lm_list[27]['z']
        r_z = lm_list[24]['z'] + lm_list[26]['z'] + lm_list[28]['z']

        if l_z < r_z:
            return {
                'hip': lm_list[23], 'knee': lm_list[25], 'ankle': lm_list[27],
                'heel': lm_list[29], 'toe': lm_list[31], 'shoulder': lm_list[11],
                'name': '左'
            }
        else:
            return {
                'hip': lm_list[24], 'knee': lm_list[26], 'ankle': lm_list[28],
                'heel': lm_list[30], 'toe': lm_list[32], 'shoulder': lm_list[12],
                'name': '右'
            }

    def validate_form(self, leg):
        """
        驗證深蹲過程中的姿勢正確性 (腳跟是否浮起、軀幹是否過度前傾)[cite: 1]。
        """
        issues = []
        
        # 檢查腳跟是否浮起[cite: 1]
        foot_angle = MathUtils.get_horizontal_angle(leg['heel'], leg['toe'])
        if foot_angle > self.SQUAT_FOOT_MAX_ANGLE:
            issues.append(PoseIssue(f"{leg['name']}腳跟浮起", [leg['heel'], leg['toe']]))

        # 檢查軀幹是否過度前傾[cite: 1]
        # 設定一個向上的垂直參考點 (像素座標 Y 軸向上為減)，確保向量正確
        vertical_point = {'x': leg['hip']['x'], 'y': leg['hip']['y'] - 100}
        trunk_angle = MathUtils.get_angle(vertical_point, leg['hip'], leg['shoulder'])
        
        if trunk_angle > self.SQUAT_TRUNK_MAX_ANGLE:
            issues.append(PoseIssue(f"軀幹過度前傾({int(trunk_angle)}°)", [leg['shoulder'], leg['hip']]))

        return {'is_valid': len(issues) == 0, 'issues': issues}

    def process_frame(self, lm_list):
        """
        處理每一幀的深蹲邏輯判定，回傳 UI 資訊與狀態回饋[cite: 1]。
        """
        leg = self.get_working_leg(lm_list)
        hip_y = leg['hip']['y']
        knee_y = leg['knee']['y']

        # 計算軀幹高度作為深度判斷的比例尺[cite: 1]
        torso_h = abs(leg['shoulder']['y'] - leg['hip']['y'])
        torso_h = torso_h if torso_h > 0 else 1.0

        # 1. 計算膝蓋夾角 (用於判斷站立與下蹲的過渡狀態)[cite: 1]
        knee_angle = MathUtils.get_angle(leg['hip'], leg['knee'], leg['ankle'])
        
        # 2. 計算 Y 軸相對高度 (判斷深蹲到底部時的平行深度)[cite: 1]
        depth_ratio = (knee_y - hip_y) / torso_h

        # 物理邊界定義：深度判定[cite: 1]
        is_parallel = -0.15 <= depth_ratio <= 0.25
        is_too_deep = depth_ratio < -0.15

        # 物理邊界定義：狀態判定[cite: 1]
        is_standing = knee_angle >= 150
        is_down_phase = knee_angle <= 110

        dashboard_info = f"深蹲次數: {self.count}"
        feedback = None

        if is_standing:
            if self.hit_target_depth:
                self.count += 1
                self.hit_target_depth = False
            self.state = ExerciseState.UP
            feedback = FeedbackState("準備開始...(請側對鏡頭)", UIState.RED)
            
        elif is_down_phase:
            self.state = ExerciseState.DOWN
            val_res = self.validate_form(leg)
            
            if not val_res['is_valid']:
                feedback = FeedbackState(f"{val_res['issues'][0].msg}\n(請即時調整姿勢)", UIState.YELLOW)
                self.hit_target_depth = False
            else:
                if self.hit_target_depth:
                    if is_too_deep:
                        feedback = FeedbackState("! 蹲太低了!請稍微抬高臀部", UIState.YELLOW)
                        self.hit_target_depth = False
                    else:
                        feedback = FeedbackState("完美深度!請保持並站起", UIState.GREEN)
                elif is_parallel:
                    self.hit_target_depth = True
                    feedback = FeedbackState("完美深度!請保持並站起", UIState.GREEN)
                elif is_too_deep:
                    feedback = FeedbackState("蹲太低了!臀部不可低於膝蓋", UIState.YELLOW)
                else:
                    feedback = FeedbackState("請繼續下蹲至大腿與地面平行", UIState.YELLOW)
        else:
            # 介於 110 度 ~ 150 度之間，屬於單純的動作過渡區間[cite: 1]
            feedback = FeedbackState("動作進行中...", UIState.YELLOW)

        return dashboard_info, feedback
