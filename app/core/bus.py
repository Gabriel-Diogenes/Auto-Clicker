from PySide6.QtCore import QObject, Signal

class Bus(QObject):
    """
    Canal de comunicação central para a aplicação.
    Componentes emitem sinais neste bus, e a UI (ou outros componentes)
    se conectam a esses sinais para reagir a eventos.
    """
    status_updated = Signal(str)
    counter_updated = Signal(int)
    macro_keyboard_updated = Signal(list)
    macro_mouse_updated = Signal(list)
    execution_finished = Signal()

# Criamos uma instância única do Bus aqui.
# Qualquer outro arquivo que precisar usar o bus, irá importar esta variável.
# Ex: from app.core.bus import bus
bus = Bus()