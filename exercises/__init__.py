# exercises/__init__.py

from .squat import Squat
from .lunge import Lunge
from .plank import Plank

# __all__ 變數用來定義當其他模組使用 from exercises import * 時，
# 會將哪些類別或函式暴露出去，是一種良好的 Python 封裝習慣。
__all__ = ['Squat', 'Lunge', 'Plank']
