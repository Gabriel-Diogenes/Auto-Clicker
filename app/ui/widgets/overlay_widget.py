"""
Este módulo contém o OverlayWidget, um widget semi-transparente e sem bordas
usado para exibir mensagens de status rápidas na tela, como "Executando...".
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class OverlayWidget(QWidget):
    """Um widget semi-transparente e sem bordas para exibir status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        self.label = QLabel("Status")
        layout.addWidget(self.label)
        
        self.setStyleSheet("""
            background-color: rgba(21, 21, 27, 0.85);
            color: #e6e6e6;
            font-size: 16px;
            font-weight: bold;
            padding: 10px 15px;
            border-radius: 12px;
        """)
        self.hide()

    def show_message(self, text: str):
        self.label.setText(text)
        self.adjustSize()
        self.show()