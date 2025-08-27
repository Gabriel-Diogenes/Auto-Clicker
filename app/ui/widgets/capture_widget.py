"""
Este módulo contém o CaptureWidget, um widget de tela cheia e transparente
que permite ao usuário desenhar um retângulo para selecionar uma área da tela.
Emite um sinal com as coordenadas da área selecionada.
"""

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen

class CaptureWidget(QWidget):
    """Widget para capturar uma área da tela."""
    area_selecionada = Signal(tuple)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Pega a geometria da tela principal para se expandir nela
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        self.begin = None
        self.end = None
        self.setMouseTracking(True) 

    def paintEvent(self, event):
        painter = QPainter(self)
        # Fundo escuro semi-transparente
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        
        # Desenha o retângulo de seleção
        if self.begin and self.end:
            painter.setPen(QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(0, 255, 0, 30))
            rect = QRect(self.begin, self.end)
            painter.drawRect(rect.normalized())

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        rect = QRect(self.begin, self.end).normalized()
        self.hide()
        
        # Mapeia o ponto do widget para a coordenada global da tela
        ponto_global = self.mapToGlobal(rect.topLeft())
        
        # Emite o sinal com as coordenadas globais
        self.area_selecionada.emit((ponto_global.x(), ponto_global.y(), rect.width(), rect.height()))
        
        # Garante que o widget seja destruído após o uso
        self.deleteLater()