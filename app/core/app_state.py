from enum import Enum, auto

class AppState(Enum):
    """Define o estado atual da aplicação de forma clara e segura."""
    IDLE = auto()
    EXECUTING = auto()
    RECORDING_KEYBOARD = auto()
    RECORDING_MOUSE = auto()