# autoclicker.py (VERSÃO REATORADA E ESTÁVEL)
import sys
import os
import json
import time
import threading
import random
from typing import List, Tuple, Dict, Any
import ctypes
from enum import Enum, auto

# PySide6 Imports
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSize, QUrl, QRect, QThread, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSlider, QDoubleSpinBox, QSpinBox, QTextEdit, QStackedWidget,
    QFrame, QMessageBox, QComboBox, QFileDialog, QGridLayout, QScrollArea, QProgressBar,
    QSizePolicy, QGraphicsOpacityEffect, QMenu, QSystemTrayIcon, QListWidget, QInputDialog
)
from PySide6.QtGui import QIcon, QCursor, QAction, QPixmap, QPainter, QColor, QScreen, QPen
from PySide6.QtMultimedia import QSoundEffect
from PIL import ImageGrab

# Tenta importar bibliotecas opcionais
try:
    import qtawesome as qta
except ImportError:
    qta = None
try:
    import win32gui
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
import cv2
import numpy as np

# pynput Imports
from pynput.keyboard import Controller as KeyboardController, Listener as KeyboardListener, Key, KeyCode
from pynput.mouse import Controller as MouseController, Button as MouseButton, Listener as MouseListener

# --- ARQUITETURA REFEITA: ESTADO E COMUNICAÇÃO ---

class AppState(Enum):
    """Define o estado atual da aplicação de forma clara e segura."""
    IDLE = auto()
    EXECUTING = auto()
    RECORDING_KEYBOARD = auto()
    RECORDING_MOUSE = auto()

class Bus(QObject):
    """Canal de comunicação central para a UI."""
    status_updated = Signal(str)
    counter_updated = Signal(int)
    macro_keyboard_updated = Signal(list)
    macro_mouse_updated = Signal(list)
    execution_finished = Signal()

class GlobalListener(QObject):
    """
    Objeto que roda em uma thread separada para escutar todos os inputs globais.
    Ele NUNCA interage com a UI diretamente, apenas emite sinais.
    """
    hotkey_pressed = Signal(str)  # Sinal principal para atalhos
    key_pressed = Signal(object)
    key_released = Signal(object)
    mouse_event = Signal(str, tuple) # (event_type, data)

    def __init__(self, hotkeys: Dict[str, str]):
        super().__init__()
        self.hotkeys = hotkeys
        self.keyboard_listener = None
        self.mouse_listener = None
        self.ctrl_pressed = False
        self.shift_pressed = False

    def run(self):
        """Inicia os listeners do pynput. Este método bloqueia até que os listeners parem."""
        self.keyboard_listener = KeyboardListener(on_press=self._on_press, on_release=self._on_release)
        self.mouse_listener = MouseListener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
        self.keyboard_listener.start()
        self.mouse_listener.start()
        self.keyboard_listener.join()
        self.mouse_listener.join()

    def stop(self):
        """Para os listeners de forma segura."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

    def update_hotkeys(self, new_hotkeys: Dict[str, str]):
        self.hotkeys = new_hotkeys

    def _key_to_str(self, key):
        if isinstance(key, Key):
            return KEY_MAP_SAVE.get(key, f"Key.{key.name}")
        if isinstance(key, KeyCode):
            return key.char if key.char is not None else str(key)
        return str(key)

    # --- Callbacks do Pynput (Apenas emitem sinais) ---
    def _on_press(self, key):
        if key in (Key.ctrl_l, Key.ctrl_r): self.ctrl_pressed = True
        if key in (Key.shift_l, Key.shift_r): self.shift_pressed = True
        
        key_name = self._key_to_str(key)
        # Verifica se é um atalho
        for hotkey_name, hotkey_value in self.hotkeys.items():
            if key_name == hotkey_value:
                self.hotkey_pressed.emit(hotkey_name)
                return  # Se for um atalho, não processa como input de macro
        
        # Verifica captura de posição do mouse (Ctrl+Shift+C)
        try:
            cond_char = getattr(key, "char", None)
            if self.ctrl_pressed and self.shift_pressed and cond_char == 'c':
                 self.mouse_event.emit("capture_pos", tuple(MouseController().position))
                 return
        except Exception:
            pass

        self.key_pressed.emit(key)

    def _on_release(self, key):
        if key in (Key.ctrl_l, Key.ctrl_r): self.ctrl_pressed = False
        if key in (Key.shift_l, Key.shift_r): self.shift_pressed = False
        self.key_released.emit(key)

    def _on_move(self, x, y):
        self.mouse_event.emit("move", (x, y))

    def _on_click(self, x, y, button, pressed):
        if pressed:
            self.mouse_event.emit("click", (x, y, button))

    def _on_scroll(self, x, y, dx, dy):
        self.mouse_event.emit("scroll", (x, y, dx, dy))

# --- FIM DA ARQUITETURA REFEITA ---


# Constantes e Globais
PROFILES_FILE = "macro_profiles.json"
SPECIAL_KEYS: Dict[str, Key] = {
    "Espaço": Key.space, "Enter": Key.enter, "Shift": Key.shift,
    "Ctrl": Key.ctrl, "Alt": Key.alt, "Tab": Key.tab,
    "Backspace": Key.backspace, "Esc": Key.esc,
}
KEY_MAP_SAVE = {v: f"Key.{k.capitalize()}" for k, v in SPECIAL_KEYS.items()}
KEY_MAP_LOAD = {v: k for k, v in KEY_MAP_SAVE.items()}
bus = Bus()

# Variáveis globais para dados das macros (mais simples de manter assim por enquanto)
macro_gravado_teclado: List[Tuple[Any, str, float]] = []
macro_gravado_mouse: List[Tuple[Any, Any, float]] = []
ultimo_tempo = 0.0


# Funções Auxiliares
def set_status(text: str):
    bus.status_updated.emit(text)

def set_counter(value: int):
    bus.counter_updated.emit(value)

# O restante do seu código (Widgets, Páginas, etc.) começa aqui.
# A maior parte dele permanece igual, as mudanças principais estão na MainWindow.
# Colei todo o restante do código para garantir que tudo esteja no lugar.

# ====== WIDGET PARA CAPTURA DE IMAGEM ======
class CaptureWidget(QWidget):
    area_selecionada = Signal(tuple)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        self.begin = None
        self.end = None
        self.setMouseTracking(True) 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        
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
        ponto_global = self.mapToGlobal(rect.topLeft())
        self.area_selecionada.emit((ponto_global.x(), ponto_global.y(), rect.width(), rect.height()))
        self.deleteLater()
        
# ====== Páginas e Widgets (QWidgets) ======

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

class PageAutoClickers(QWidget):
    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Auto Clickers")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(20)
        
        keys_frame = QFrame()
        keys_frame.setObjectName("sectionFrame")
        keys_layout = QVBoxLayout(keys_frame)
        keys_title = QLabel("Auto Clicker de Teclado")
        keys_title.setObjectName("sectionTitle")
        keys_layout.addWidget(keys_title)
        row_keys = QHBoxLayout()
        row_keys.addWidget(QLabel("Teclas normais (ex: wasd):"))
        self.input_keys = QLineEdit()
        self.input_keys.setPlaceholderText("Digite sequência de letras/números…")
        row_keys.addWidget(self.input_keys)
        keys_layout.addLayout(row_keys)
        special_title = QLabel("Teclas especiais:")
        keys_layout.addWidget(special_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.chk_specials: Dict[str, QCheckBox] = {}
        specials_grid = QHBoxLayout()
        for name in SPECIAL_KEYS.keys():
            chk = QCheckBox(name)
            self.chk_specials[name] = chk
            specials_grid.addWidget(chk)
        keys_layout.addLayout(specials_grid)
        self.btn_start_keyboard_ac = QPushButton("▶ Iniciar Auto Clicker Teclado")
        self.btn_start_keyboard_ac.setObjectName("startButton")
        keys_layout.addWidget(self.btn_start_keyboard_ac)
        main_grid.addWidget(keys_frame, 0, 0, 1, 1)

        mouse_ac_frame = QFrame()
        mouse_ac_frame.setObjectName("sectionFrame")
        mouse_ac_layout = QVBoxLayout(mouse_ac_frame)
        mouse_title = QLabel("Auto Clicker do Mouse")
        mouse_title.setObjectName("sectionTitle")
        mouse_ac_layout.addWidget(mouse_title)
        row_button = QHBoxLayout()
        row_button.addWidget(QLabel("Botão do mouse:"))
        self.combo_mouse_button = QComboBox()
        self.combo_mouse_button.addItems(["Esquerdo", "Direito", "Meio"])
        row_button.addWidget(self.combo_mouse_button)
        mouse_ac_layout.addLayout(row_button)
        self.btn_start_mouse_ac = QPushButton("▶ Iniciar Auto Clicker Mouse")
        self.btn_start_mouse_ac.setObjectName("startButton")
        mouse_ac_layout.addWidget(self.btn_start_mouse_ac)
        main_grid.addWidget(mouse_ac_frame, 0, 1, 1, 1)
        root.addLayout(main_grid)

        config_frame = QFrame()
        config_frame.setObjectName("sectionFrame")
        config_layout = QVBoxLayout(config_frame)
        config_title = QLabel("Configurações de Execução")
        config_title.setObjectName("sectionTitle")
        config_layout.addWidget(config_title)
        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Delay entre ciclos (s):"))
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.001, 100.0)
        self.spin_speed.setDecimals(3)
        self.spin_speed.setSingleStep(0.01)
        self.spin_speed.setValue(0.500)
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 1000)
        self.slider_speed.setValue(int(self.spin_speed.value() * 1000))
        self.slider_speed.valueChanged.connect(lambda val: self.spin_speed.setValue(val / 1000.0))
        self.spin_speed.valueChanged.connect(lambda val: self.slider_speed.setValue(int(val * 1000)))
        row_speed.addWidget(self.slider_speed)
        row_speed.addWidget(self.spin_speed)
        config_layout.addLayout(row_speed)
        row_rand_speed = QHBoxLayout()
        self.chk_random_delay = QCheckBox("Delay Aleatório")
        lbl_ate = QLabel("  até (s):")
        lbl_ate.setFixedWidth(60)
        self.spin_speed_max = QDoubleSpinBox()
        self.spin_speed_max.setRange(0.001, 100.0)
        self.spin_speed_max.setDecimals(3)
        self.spin_speed_max.setSingleStep(0.01)
        self.spin_speed_max.setValue(1.0)
        self.spin_speed_max.setEnabled(False)
        row_rand_speed.addWidget(self.chk_random_delay)
        row_rand_speed.addWidget(lbl_ate)
        row_rand_speed.addWidget(self.spin_speed_max)
        self.chk_random_delay.stateChanged.connect(lambda state: self.spin_speed_max.setEnabled(bool(state)))
        config_layout.addLayout(row_rand_speed)
        row_rep = QHBoxLayout()
        self.chk_infinite = QCheckBox("Modo infinito")
        self.chk_infinite.setChecked(True)
        self.chk_infinite.stateChanged.connect(self._toggle_reps)
        row_rep.addWidget(self.chk_infinite)
        lbl_reps = QLabel("Repetições:")
        lbl_reps.setFixedWidth(110)
        row_rep.addWidget(lbl_reps)
        self.spin_reps = QSpinBox()
        self.spin_reps.setRange(1, 999999)
        self.spin_reps.setValue(1)
        self.spin_reps.setEnabled(False)
        row_rep.addWidget(self.spin_reps)
        config_layout.addLayout(row_rep)
        self.btn_stop = QPushButton("⏹ Parar Tudo")
        config_layout.addWidget(self.btn_stop)
        root.addWidget(config_frame)
        root.addStretch()

    def _toggle_reps(self, state):
        self.spin_reps.setEnabled(not self.chk_infinite.isChecked())

    def get_selected_keys(self) -> List[Any]:
        keys = [ch for ch in self.input_keys.text().strip()]
        keys.extend(SPECIAL_KEYS[name] for name, chk in self.chk_specials.items() if chk.isChecked())
        return keys

    def get_delay(self) -> float:
        return self.spin_speed.value()

    def is_infinite(self) -> bool:
        return self.chk_infinite.isChecked()

    def get_reps(self) -> int:
        return self.spin_reps.value()

    def get_mouse_button(self) -> MouseButton:
        return {"Esquerdo": MouseButton.left, "Direito": MouseButton.right, "Meio": MouseButton.middle}.get(self.combo_mouse_button.currentText(), MouseButton.left)

    def set_from_config(self, cfg: dict):
        self.input_keys.setText(cfg.get("teclas_normais", ""))
        for name, v in cfg.get("teclas_especiais", {}).items():
            if name in self.chk_specials: self.chk_specials[name].setChecked(bool(v))
        speed_val = float(cfg.get("velocidade", 0.5))
        self.spin_speed.setValue(speed_val)
        self.slider_speed.setValue(int(speed_val * 1000))
        self.chk_random_delay.setChecked(cfg.get("random_delay", False))
        self.spin_speed_max.setValue(cfg.get("random_delay_max", 1.0))
        self.chk_infinite.setChecked(bool(cfg.get("modo_infinito", True)))
        self.spin_reps.setValue(int(cfg.get("repeticoes", 1)))
        self.combo_mouse_button.setCurrentText(cfg.get("mouse_button", "Esquerdo"))

    def to_config(self) -> dict:
        return {
            "teclas_normais": self.input_keys.text(),
            "teclas_especiais": {name: chk.isChecked() for name, chk in self.chk_specials.items()},
            "velocidade": self.get_delay(),
            "random_delay": self.chk_random_delay.isChecked(),
            "random_delay_max": self.spin_speed_max.value(),
            "modo_infinito": self.is_infinite(),
            "repeticoes": self.get_reps(),
            "mouse_button": self.combo_mouse_button.currentText()
        }

class PageMacros(QWidget):
    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Macros de Teclado e Mouse")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(20)
        
        teclado_frame = QFrame()
        teclado_frame.setObjectName("sectionFrame")
        teclado_layout = QVBoxLayout(teclado_frame)
        teclado_title = QLabel("Macro de Teclado")
        teclado_title.setObjectName("sectionTitle")
        teclado_layout.addWidget(teclado_title)
        row_teclado_rec = QHBoxLayout()
        self.btn_rec_teclado = QPushButton("⏺ Gravar Macro")
        self.btn_rec_teclado.setObjectName("recButton")
        self.btn_stop_rec_teclado = QPushButton("⏹ Parar Gravação")
        row_teclado_rec.addWidget(self.btn_rec_teclado)
        row_teclado_rec.addWidget(self.btn_stop_rec_teclado)
        teclado_layout.addLayout(row_teclado_rec)
        row_teclado_play = QHBoxLayout()
        self.btn_play_teclado = QPushButton("▶ Executar Macro")
        self.btn_play_teclado.setObjectName("startButton")
        self.btn_capture_pixel_teclado = QPushButton("🎯 Capturar Pixel")
        self.btn_duplicate_step_teclado = QPushButton("❐ Duplicar Passo")
        self.btn_delete_step_teclado = QPushButton("🗑️ Deletar Passo")
        self.btn_clear_teclado = QPushButton("❌ Limpar Macro")
        row_teclado_play.addWidget(self.btn_play_teclado)
        row_teclado_play.addWidget(self.btn_capture_pixel_teclado)
        row_teclado_play.addWidget(self.btn_duplicate_step_teclado)
        row_teclado_play.addWidget(self.btn_delete_step_teclado)
        row_teclado_play.addWidget(self.btn_clear_teclado)
        teclado_layout.addLayout(row_teclado_play)
        self.list_macro_teclado = QListWidget()
        self.list_macro_teclado.setToolTip("Dê um clique duplo em um item para editar seus detalhes.")
        self.list_macro_teclado.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_macro_teclado.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_macro_teclado.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_macro_teclado.setMinimumHeight(160)
        teclado_layout.addWidget(self.list_macro_teclado)
        grid_layout.addWidget(teclado_frame, 0, 0, 1, 1)

        mouse_frame = QFrame()
        mouse_frame.setObjectName("sectionFrame")
        mouse_layout = QVBoxLayout(mouse_frame)
        mouse_title = QLabel("Macro de Mouse")
        mouse_title.setObjectName("sectionTitle")
        mouse_layout.addWidget(mouse_title)
        row_mouse_rec = QHBoxLayout()
        self.btn_rec_mouse = QPushButton("⏺ Gravar Macro")
        self.btn_rec_mouse.setObjectName("recButton")
        self.btn_stop_rec_mouse = QPushButton("⏹ Parar Gravação")
        row_mouse_rec.addWidget(self.btn_rec_mouse)
        row_mouse_rec.addWidget(self.btn_stop_rec_mouse)
        mouse_layout.addLayout(row_mouse_rec)
        row_mouse_play = QHBoxLayout()
        self.btn_play_mouse = QPushButton("▶ Executar Macro")
        self.btn_play_mouse.setObjectName("startButton")
        self.btn_duplicate_step_mouse = QPushButton("❐ Duplicar Passo")
        self.btn_delete_step_mouse = QPushButton("🗑️ Deletar Passo")
        self.btn_clear_mouse = QPushButton("❌ Limpar Macro")
        row_mouse_play.addWidget(self.btn_play_mouse)
        row_mouse_play.addWidget(self.btn_duplicate_step_mouse)
        row_mouse_play.addWidget(self.btn_delete_step_mouse)
        row_mouse_play.addWidget(self.btn_clear_mouse)
        mouse_layout.addLayout(row_mouse_play)
        self.lbl_mouse_pos = QLabel("Posição atual: (0, 0)")
        self.lbl_mouse_pos.setStyleSheet("color: #a0a0b0; font-size: 16px; font-weight: bold;")
        self.lbl_mouse_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mouse_layout.addWidget(self.lbl_mouse_pos)
        
        self.chk_relative_mouse = QCheckBox("Gravar movimentos relativos à janela ativa")
        if PYWIN32_AVAILABLE:
            self.chk_relative_mouse.setToolTip("Grava as coordenadas do mouse como uma distância a partir do canto da janela em foco.")
        else:
            self.chk_relative_mouse.setToolTip("Funcionalidade indisponível. Instale a biblioteca 'pywin32'.")
            self.chk_relative_mouse.setEnabled(False)
        mouse_layout.addWidget(self.chk_relative_mouse)
        
        self.btn_capture_pixel = QPushButton("🎯 Capturar Pixel/Cor")
        self.btn_capture_pixel.setToolTip("Inicia o modo de captura. O próximo clique na tela irá adicionar um passo de 'Aguardar por Pixel' na macro de mouse.")
        mouse_layout.addWidget(self.btn_capture_pixel)

        self.btn_capture_image = QPushButton("📸 Capturar Área/Imagem")
        self.btn_capture_image.setToolTip("Inicia o modo de captura para selecionar uma área da tela (imagem).")
        mouse_layout.addWidget(self.btn_capture_image)

        self.list_macro_mouse = QListWidget()
        self.list_macro_mouse.setToolTip("Dê um clique duplo em um item para editar seus detalhes.")
        self.list_macro_mouse.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_macro_mouse.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_macro_mouse.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_macro_mouse.setMinimumHeight(160)
        mouse_layout.addWidget(self.list_macro_mouse)
        grid_layout.addWidget(mouse_frame, 0, 1, 1, 1)
        root.addLayout(grid_layout)
        
        macro_reps_frame = QFrame()
        macro_reps_frame.setObjectName("sectionFrame")
        macro_reps_layout = QVBoxLayout(macro_reps_frame)
        macro_config_title = QLabel("Configurações de Execução de Macro")
        macro_config_title.setObjectName("sectionTitle")
        macro_reps_layout.addWidget(macro_config_title)
        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Delay entre ciclos (s):"))
        self.spin_macro_speed = QDoubleSpinBox()
        self.spin_macro_speed.setRange(0.001, 100.0)
        self.spin_macro_speed.setDecimals(3)
        self.spin_macro_speed.setSingleStep(0.01)
        self.spin_macro_speed.setValue(0.500)
        self.slider_macro_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_macro_speed.setRange(1, 1000)
        self.slider_macro_speed.setValue(int(self.spin_macro_speed.value() * 10))
        self.slider_macro_speed.valueChanged.connect(lambda val: self.spin_macro_speed.setValue(val / 1000.0))
        self.spin_macro_speed.valueChanged.connect(lambda val: self.slider_macro_speed.setValue(int(val * 1000)))
        row_speed.addWidget(self.slider_macro_speed)
        row_speed.addWidget(self.spin_macro_speed)
        macro_reps_layout.addLayout(row_speed)
        row_rand_speed_macro = QHBoxLayout()
        self.chk_macro_random_delay = QCheckBox("Delay Aleatório")
        lbl_ate_macro = QLabel("  até (s):")
        lbl_ate_macro.setFixedWidth(60)
        self.spin_macro_speed_max = QDoubleSpinBox()
        self.spin_macro_speed_max.setRange(0.001, 100.0)
        self.spin_macro_speed_max.setDecimals(3)
        self.spin_macro_speed_max.setSingleStep(0.01)
        self.spin_macro_speed_max.setValue(1.0)
        self.spin_macro_speed_max.setEnabled(False)
        row_rand_speed_macro.addWidget(self.chk_macro_random_delay)
        row_rand_speed_macro.addWidget(lbl_ate_macro)
        row_rand_speed_macro.addWidget(self.spin_macro_speed_max)
        self.chk_macro_random_delay.stateChanged.connect(lambda state: self.spin_macro_speed_max.setEnabled(bool(state)))
        macro_reps_layout.addLayout(row_rand_speed_macro)
        row_rep = QHBoxLayout()
        self.chk_macro_infinite = QCheckBox("Modo infinito")
        self.chk_macro_infinite.setChecked(True)
        self.chk_macro_infinite.stateChanged.connect(self._toggle_reps)
        row_rep.addWidget(self.chk_macro_infinite)
        lbl_macro_reps = QLabel("Repetições:")
        lbl_macro_reps.setFixedWidth(110)
        row_rep.addWidget(lbl_macro_reps)
        self.spin_macro_reps = QSpinBox()
        self.spin_macro_reps.setRange(1, 999999)
        self.spin_macro_reps.setValue(1)
        self.spin_macro_reps.setEnabled(False)
        row_rep.addWidget(self.spin_macro_reps)
        macro_reps_layout.addLayout(row_rep)
        root.addWidget(macro_reps_frame)
        root.addStretch()

    def update_keyboard_macro_list(self, macro_data: list):
        self.list_macro_teclado.clear()
        for i, (t, a, d) in enumerate(macro_data):
            delay_str = f"{d:.4f}s" if d > 0.001 else "0.000s"
            t_str = ""
            try:
                if isinstance(t, Key):
                    t_str = f"Key.{t.name}"
                elif isinstance(t, KeyCode):
                    t_str = t.char if t.char is not None else str(t)
                else:
                    t_str = str(t)
            except Exception:
                t_str = str(t)
            
            if t == 'wait_pixel':
                px, py, pcolor = a
                line_text = f"{i+1:02d}: Aguardar Pixel em ({px}, {py}) ser da cor {pcolor}"
            else:
                line_text = f"{i+1:02d}: {t_str} - {a.capitalize()} (Delay: {delay_str})"
            
            self.list_macro_teclado.addItem(line_text)

    def update_mouse_macro_list(self, macro_data: list):
        self.list_macro_mouse.clear()
        for i, (action_type, value, d) in enumerate(macro_data):
            delay_str = f"{d:.4f}s" if d > 0.001 else "0.000s"
            line_text = f"{i+1:02d}: "
            
            if action_type == "move" or action_type == "position":
                prefix = "Mover para" if action_type == "move" else "Pos. Fixa"
                line_text += f"{prefix} ({value[0]}, {value[1]}) (Delay: {delay_str})"
            elif action_type == "click":
                try:
                    btn = str(value).split('.')[-1].capitalize()
                except Exception:
                    btn = str(value)
                line_text += f"Clique {btn} (Delay: {delay_str})"
            elif action_type == "scroll":
                line_text += f"Rolagem {value[0]} (Delay: {delay_str})"
            elif action_type == "wait_pixel":
                px, py, pcolor = value
                line_text += f"Aguardar Pixel em ({px}, {py}) ser da cor {pcolor}"
            elif action_type == "wait_image":
                line_text += f"Aguardar Imagem '{os.path.basename(value)}' (Delay: {delay_str})"
            elif action_type == "click_image":
                line_text += f"Clicar na Imagem '{os.path.basename(value)}' (Delay: {delay_str})"
            elif action_type == "set_relative_origin":
                line_text += f"Origem Relativa: Janela '{value}'"

            self.list_macro_mouse.addItem(line_text)

    def _toggle_reps(self, state):
        self.spin_macro_reps.setEnabled(not self.chk_macro_infinite.isChecked())

    def get_reps(self) -> int:
        return self.spin_macro_reps.value()

    def is_infinite(self) -> bool:
        return self.chk_macro_infinite.isChecked()

    def get_delay(self) -> float:
        return self.spin_macro_speed.value()

class PageSettings(QWidget):
    def __init__(self):
        super().__init__()
        self.is_capturing = False
        self.current_hotkey_field = None
        self.hotkey_listener = None
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Configurações e Perfis")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        profiles_frame = QFrame()
        profiles_frame.setObjectName("sectionFrame")
        profiles_layout = QVBoxLayout(profiles_frame)
        profiles_layout.addWidget(QLabel("Gerenciar Perfis (Salva/Carrega Todas as Configurações):"))
        prof_row1 = QHBoxLayout()
        self.input_profile_name = QLineEdit()
        self.input_profile_name.setPlaceholderText("Nome do perfil (ex: Jogo X, Trabalho)")
        self.btn_profile_save = QPushButton("💾 Salvar Perfil")
        prof_row1.addWidget(self.input_profile_name)
        prof_row1.addWidget(self.btn_profile_save)
        profiles_layout.addLayout(prof_row1)
        prof_row2 = QHBoxLayout()
        self.combo_profiles = QComboBox()
        self.btn_profile_load = QPushButton("📂 Carregar Perfil")
        self.btn_profile_delete = QPushButton("🗑️ Excluir Perfil")
        prof_row2.addWidget(self.combo_profiles)
        prof_row2.addWidget(self.btn_profile_load)
        prof_row2.addWidget(self.btn_profile_delete)
        profiles_layout.addLayout(prof_row2)
        content_layout.addWidget(profiles_frame)
        
        import_export_frame = QFrame()
        import_export_frame.setObjectName("sectionFrame")
        import_export_layout = QVBoxLayout(import_export_frame)
        profiles_title = QLabel("Importar / Exportar Perfis")
        profiles_title.setObjectName("sectionTitle")
        import_export_layout.addWidget(profiles_title)
        import_export_layout.addWidget(QLabel("Compartilhe seus perfis de macro com outros usuários."))
        row2 = QHBoxLayout()
        self.btn_export_profiles = QPushButton("⬆ Exportar Perfis")
        self.btn_import_profiles = QPushButton("⬇ Importar Perfis")
        row2.addWidget(self.btn_export_profiles)
        row2.addWidget(self.btn_import_profiles)
        import_export_layout.addLayout(row2)
        content_layout.addWidget(import_export_frame)
        
        hotkeys_frame = QFrame()
        hotkeys_frame.setObjectName("sectionFrame")
        hotkeys_layout = QVBoxLayout(hotkeys_frame)
        hotkeys_title = QLabel("Atalhos Globais")
        hotkeys_title.setObjectName("sectionTitle")
        hotkeys_layout.addWidget(hotkeys_title)
        grid_hotkeys = QGridLayout()
        grid_hotkeys.setColumnStretch(0, 0)
        grid_hotkeys.setColumnStretch(1, 1)
        self.lbl_info_hotkeys = QLabel("Clique no campo para capturar uma tecla de atalho.")
        self.lbl_info_hotkeys.setStyleSheet("color: #a0a0b0;")
        grid_hotkeys.addWidget(self.lbl_info_hotkeys, 0, 0, 1, 2)
        self.input_ac_teclado = QLineEdit(objectName="input_autoclicker_teclado")
        self.input_ac_mouse = QLineEdit(objectName="input_autoclicker_mouse")
        self.input_macro_teclado = QLineEdit(objectName="input_macro_teclado")
        self.input_macro_mouse = QLineEdit(objectName="input_macro_mouse")
        self.input_parar_tudo = QLineEdit(objectName="input_parar_tudo")
        self.input_gravar_macro_teclado = QLineEdit(objectName="input_gravar_macro_teclado")
        self.input_gravar_macro_mouse = QLineEdit(objectName="input_gravar_macro_mouse")
        self.input_parar_gravacao = QLineEdit(objectName="input_parar_gravacao")
        for inp in [self.input_ac_teclado, self.input_ac_mouse, self.input_macro_teclado, self.input_macro_mouse, self.input_parar_tudo, self.input_gravar_macro_teclado, self.input_gravar_macro_mouse, self.input_parar_gravacao]:
            inp.setReadOnly(True)
        grid_hotkeys.addWidget(QLabel("Iniciar/Parar Autoclicker Teclado:"), 1, 0)
        grid_hotkeys.addWidget(self.input_ac_teclado, 1, 1)
        grid_hotkeys.addWidget(QLabel("Iniciar/Parar Autoclicker Mouse:"), 2, 0)
        grid_hotkeys.addWidget(self.input_ac_mouse, 2, 1)
        grid_hotkeys.addWidget(QLabel("Executar/Parar Macro Teclado:"), 3, 0)
        grid_hotkeys.addWidget(self.input_macro_teclado, 3, 1)
        grid_hotkeys.addWidget(QLabel("Executar/Parar Macro Mouse:"), 4, 0)
        grid_hotkeys.addWidget(self.input_macro_mouse, 4, 1)
        grid_hotkeys.addWidget(QLabel("Gravar Macro Teclado:"), 5, 0)
        grid_hotkeys.addWidget(self.input_gravar_macro_teclado, 5, 1)
        grid_hotkeys.addWidget(QLabel("Gravar Macro Mouse:"), 6, 0)
        grid_hotkeys.addWidget(self.input_gravar_macro_mouse, 6, 1)
        grid_hotkeys.addWidget(QLabel("Parar Gravação (Hotkeys):"), 7, 0)
        grid_hotkeys.addWidget(self.input_parar_gravacao, 7, 1)
        grid_hotkeys.addWidget(QLabel("Parar Todas as Ações (Emergência):"), 8, 0)
        grid_hotkeys.addWidget(self.input_parar_tudo, 8, 1)
        hotkeys_layout.addLayout(grid_hotkeys)
        content_layout.addWidget(hotkeys_frame)

        other_settings_frame = QFrame()
        other_settings_frame.setObjectName("sectionFrame")
        other_settings_layout = QVBoxLayout(other_settings_frame)
        other_title = QLabel("Outras Configurações")
        other_title.setObjectName("sectionTitle")
        other_settings_layout.addWidget(other_title)
        self.chk_enable_sounds = QCheckBox("Habilitar sinais sonoros para iniciar/parar ações")
        self.chk_enable_sounds.setChecked(True)
        other_settings_layout.addWidget(self.chk_enable_sounds)
        content_layout.addWidget(other_settings_frame)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        root.addWidget(scroll_area)
        
    def start_capture_hotkey(self, line_edit: QLineEdit):
        if self.is_capturing: self.stop_capture_hotkey()
        self.is_capturing = True
        self.current_hotkey_field = line_edit
        self.current_hotkey_field.setPlaceholderText("Pressione uma tecla...")
        self.current_hotkey_field.setStyleSheet("background: #4a4a62; border: 1px solid #5c6efc;")
        self.lbl_info_hotkeys.setText("Capturando tecla...")

        def on_press(key):
            try:
                key_str = self.window()._key_to_str(key)
                if not key_str: return
                self.current_hotkey_field.setText(key_str)
                hotkey_name = self.current_hotkey_field.objectName().replace("input_", "")
                if win := self.window():
                    win.hotkeys[hotkey_name] = key_str
                    win.listener.update_hotkeys(win.hotkeys) # ATUALIZA OS ATALHOS NO LISTENER
            finally:
                self.stop_capture_hotkey()
                return False

        self.hotkey_listener = KeyboardListener(on_press=on_press)
        self.hotkey_listener.start()

    def stop_capture_hotkey(self):
        if self.hotkey_listener and getattr(self.hotkey_listener, "running", False):
            self.hotkey_listener.stop()
        self.is_capturing = False
        if self.current_hotkey_field:
            self.current_hotkey_field.setPlaceholderText("")
            self.current_hotkey_field.setStyleSheet("")
            self.current_hotkey_field = None
        self.lbl_info_hotkeys.setText("Clique no campo para capturar uma tecla.")
        set_status("Captura de atalho finalizada.")
        
    def refresh_profiles(self, profiles: Dict[str, Any]):
        current_selection = self.combo_profiles.currentText()
        self.combo_profiles.clear()
        names = sorted(profiles.keys())
        self.combo_profiles.addItems(names)
        self.combo_profiles.setCurrentText(current_selection)

class PageAbout(QWidget):
    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Sobre / Instruções")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        txt = QTextEdit()
        txt.setReadOnly(True)
        about_text = """
        <h2 style="color:#9f7aea;">Sobre o Aplicativo</h2>
        <p>Este aplicativo é uma poderosa ferramenta de automação para tarefas repetitivas. Com ele, você pode criar e gerenciar <b>macros de teclado e mouse</b>, além de utilizar um <b>autoclicker</b> para agilizar ações em jogos, testes de software ou qualquer atividade que exija cliques ou pressionamentos de tecla repetitivos.</p>
        <hr style="border: 1px solid #3c3c52;">
        <h3 style="color:#9f7aea;">Instruções de Uso</h3>
        <ul>
            <li><b>Macros:</b> Clique em "Gravar Macro", realize as ações e pare a gravação.</li>
            <li><b>Autoclicker:</b> Configure delay e repetições, use os botões ou hotkeys.</li>
            <li><b>Perfis:</b> Salve/carregue perfis para usos distintos.</li>
        </ul>
        <hr style="border: 1px solid #3c3c52;">
        <p style="text-align: center; color: #7a7a7a;">
            Versão 3.0 (Refatorada)<br>
            Desenvolvido por Gabriel Alves da Silva Diógenes<br>
            Copyright © 2025
        </p>
        """
        txt.setHtml(about_text)
        root.addWidget(txt)
        root.addStretch()

# ====== Janela principal (integra tudo)
class MainWindow(QMainWindow):
    # --- PROPRIEDADES PRINCIPAIS ---
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Clicker + Macro Dashboard (v3 - Refatorado)")
        self.setMinimumSize(QSize(1200, 700))
        self.resize(1200, 700)
        try:
            self.setWindowIcon(QIcon("app.ico"))
        except Exception:
            pass
        
        # --- ARQUITETURA REFEITA: INICIALIZAÇÃO ---
        self.app_state = AppState.IDLE
        self.hotkeys = {}
        self.worker_thread = None
        self.stop_event = threading.Event()

        # Configura o listener para rodar em sua própria thread de forma segura
        self.listener_thread = QThread()
        self.listener = GlobalListener(self.hotkeys)
        self.listener.moveToThread(self.listener_thread)
        
        # Conexões de sinais do listener
        self.listener_thread.started.connect(self.listener.run)
        self.listener.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.listener.key_pressed.connect(self.on_key_pressed_for_macro)
        self.listener.key_released.connect(self.on_key_released_for_macro)
        self.listener.mouse_event.connect(self.on_mouse_event_for_macro)
        # --- FIM DA ARQUITETURA ---

        self.mouse_pos_timer = None
        self._current_animation = None
        self.current_total_reps = None
        self.is_capturing_pixel = False
        self.is_capturing_pixel_teclado = False
        self.capture_widget = None
        self.recording_origin = None

        if not os.path.exists("captures"):
            os.makedirs("captures")
        
        # --- Construção da UI (sem grandes mudanças aqui) ---
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setObjectName("sidebar")
        vside = QVBoxLayout(sidebar)
        vside.setContentsMargins(16, 12, 12, 12)
        logo = QLabel("Automator")
        logo.setObjectName("logoTitle")
        vside.addWidget(logo)
        
        def get_icon_try(names):
            if qta is None: return None
            for n in names:
                try: return qta.icon(n)
                except Exception: continue
            return None

        icon_auto = get_icon_try(["fa.mouse-pointer", "fa5s.mouse-pointer", "fa.rocket"])
        icon_macro = get_icon_try(["fa.keyboard-o", "fa5s.keyboard", "fa.keyboard"])
        icon_settings = get_icon_try(["fa.cog", "fa5s.cog"])
        icon_about = get_icon_try(["fa.info-circle", "fa5s.info-circle"])
        
        self.btn_go_auto = QPushButton("  Auto Clickers")
        if icon_auto: self.btn_go_auto.setIcon(icon_auto)
        self.btn_go_macro = QPushButton("  Macros")
        if icon_macro: self.btn_go_macro.setIcon(icon_macro)
        self.btn_go_settings = QPushButton("  Configurações")
        if icon_settings: self.btn_go_settings.setIcon(icon_settings)
        self.btn_go_about = QPushButton("  Sobre")
        if icon_about: self.btn_go_about.setIcon(icon_about)
        self.nav_buttons = [self.btn_go_auto, self.btn_go_macro, self.btn_go_settings, self.btn_go_about]
        for b in self.nav_buttons:
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            vside.addWidget(b)
        vside.addStretch()
        
        status_vbox = QVBoxLayout()
        status_vbox.setSpacing(6)
        status_vbox.setContentsMargins(0, 0, 0, 0)
        self.status_badge = QLabel()
        self.status_badge.setFixedSize(14, 14)
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setToolTip("Status: Pronto")
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_status = QLabel("Status: Pronto")
        self.lbl_status.setObjectName("statusLabel")
        top_row.addWidget(self.lbl_status, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()
        status_vbox.addLayout(top_row)
        self.lbl_counter = QLabel("Repetições: 0")
        self.lbl_counter.setObjectName("counterLabel")
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_vbox.addWidget(self.lbl_counter)
        vside.addLayout(status_vbox)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        vside.addWidget(self.progress)

        self.pages = QStackedWidget()
        self.page_auto = PageAutoClickers()
        self.page_macro = PageMacros()
        self.page_settings = PageSettings()
        self.page_about = PageAbout()
        self.pages.addWidget(self.page_auto)
        self.pages.addWidget(self.page_macro)
        self.pages.addWidget(self.page_settings)
        self.pages.addWidget(self.page_about)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(sidebar)
        root.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        self.overlay = OverlayWidget()
        screen_geometry = QScreen.availableGeometry(QApplication.primaryScreen())
        self.overlay.move(
            screen_geometry.width() - self.overlay.width() - 20,
            screen_geometry.height() - self.overlay.height() - 40
        )
        # --- Fim da Construção da UI ---

        # --- Conexões de Sinais e Slots ---
        self.btn_go_auto.clicked.connect(lambda: self.set_active_page(self.btn_go_auto, self.page_auto))
        self.btn_go_macro.clicked.connect(lambda: self.set_active_page(self.btn_go_macro, self.page_macro))
        self.btn_go_settings.clicked.connect(lambda: self.set_active_page(self.btn_go_settings, self.page_settings))
        self.btn_go_about.clicked.connect(lambda: self.set_active_page(self.btn_go_about, self.page_about))
        self.set_active_page(self.btn_go_auto, self.page_auto)

        bus.status_updated.connect(self.on_status)
        bus.counter_updated.connect(self.on_counter)
        bus.macro_keyboard_updated.connect(self.page_macro.update_keyboard_macro_list)
        bus.macro_mouse_updated.connect(self.page_macro.update_mouse_macro_list)
        bus.execution_finished.connect(self.on_execution_finished)

        self.page_auto.btn_start_keyboard_ac.clicked.connect(self.start_auto_click_teclado)
        self.page_auto.btn_start_mouse_ac.clicked.connect(self.start_auto_click_mouse)
        self.page_auto.btn_stop.clicked.connect(self.stop_all)
        self.page_macro.btn_rec_teclado.clicked.connect(self.start_record_teclado)
        self.page_macro.btn_stop_rec_teclado.clicked.connect(self.stop_record_teclado)
        self.page_macro.btn_play_teclado.clicked.connect(self.start_macro_teclado)
        self.page_macro.btn_clear_teclado.clicked.connect(self.clear_current_macro_teclado)
        self.page_macro.btn_delete_step_teclado.clicked.connect(self.delete_keyboard_macro_step)
        self.page_macro.btn_duplicate_step_teclado.clicked.connect(self.duplicate_keyboard_macro_step)
        self.page_macro.list_macro_teclado.itemDoubleClicked.connect(self.edit_keyboard_macro_step)
        self.page_macro.list_macro_teclado.model().rowsMoved.connect(
            lambda parent, start, end, dest, row: self.handle_macro_reorder(
                macro_gravado_teclado, start, end, row
            )
        )
        self.page_macro.btn_rec_mouse.clicked.connect(self.start_record_mouse)
        self.page_macro.btn_stop_rec_mouse.clicked.connect(self.stop_record_mouse)
        self.page_macro.btn_play_mouse.clicked.connect(self.start_macro_mouse)
        self.page_macro.btn_clear_mouse.clicked.connect(self.clear_current_macro_mouse)
        self.page_macro.btn_delete_step_mouse.clicked.connect(self.delete_mouse_macro_step)
        self.page_macro.btn_duplicate_step_mouse.clicked.connect(self.duplicate_mouse_macro_step)
        self.page_macro.list_macro_mouse.itemDoubleClicked.connect(self.edit_mouse_macro_step)
        self.page_macro.list_macro_mouse.model().rowsMoved.connect(
            lambda parent, start, end, dest, row: self.handle_macro_reorder(
                macro_gravado_mouse, start, end, row, is_mouse=True
            )
        )
        self.page_macro.btn_capture_pixel.clicked.connect(self.start_pixel_capture_mouse)
        self.page_macro.btn_capture_pixel_teclado.clicked.connect(self.start_pixel_capture_teclado)
        self.page_macro.btn_capture_image.clicked.connect(self.start_image_capture)
        
        self.page_settings.btn_profile_save.clicked.connect(self.save_profile)
        self.page_settings.btn_profile_load.clicked.connect(self.load_profile)
        self.page_settings.btn_profile_delete.clicked.connect(self.delete_profile)
        self.page_settings.btn_export_profiles.clicked.connect(self.export_profiles)
        self.page_settings.btn_import_profiles.clicked.connect(self.import_profiles)
        
        self.page_settings.input_ac_teclado.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_ac_teclado)
        self.page_settings.input_ac_mouse.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_ac_mouse)
        self.page_settings.input_macro_teclado.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_macro_teclado)
        self.page_settings.input_macro_mouse.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_macro_mouse)
        self.page_settings.input_parar_tudo.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_parar_tudo)
        self.page_settings.input_gravar_macro_teclado.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_gravar_macro_teclado)
        self.page_settings.input_gravar_macro_mouse.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_gravar_macro_mouse)
        self.page_settings.input_parar_gravacao.mousePressEvent = lambda e: self.page_settings.start_capture_hotkey(self.page_settings.input_parar_gravacao)

        self.set_default_hotkeys()
        self.load_profiles()
        self.start_cursor_tracker()
        self.setup_tray_icon()
        self.listener_thread.start() # Inicia a thread do listener

        # Carrega sons
        self.start_sound = QSoundEffect()
        self.start_sound.setSource(QUrl.fromLocalFile("start.wav"))
        self.start_sound.setVolume(0.8)
        self.stop_sound = QSoundEffect()
        self.stop_sound.setSource(QUrl.fromLocalFile("stop.wav"))
        self.stop_sound.setVolume(0.8)

    # --- NOVO SLOT CENTRAL PARA GERENCIAR ATALHOS ---
    def on_hotkey_pressed(self, hotkey_name: str):
        """Este slot é o novo centro de controle para todos os atalhos."""
        
        # Lógica para parar ações
        is_stop_key = hotkey_name in ("parar_tudo", "parar_gravacao")
        if self.app_state == AppState.EXECUTING and (is_stop_key or "autoclicker" in hotkey_name or "macro" in hotkey_name):
            self.stop_all()
            return
        if (self.app_state == AppState.RECORDING_KEYBOARD or self.app_state == AppState.RECORDING_MOUSE) and is_stop_key:
            self.stop_all()
            return

        # Lógica para iniciar ações (só funciona se estiver ocioso)
        if self.app_state == AppState.IDLE:
            if hotkey_name == "autoclicker_teclado":
                self.start_auto_click_teclado()
            elif hotkey_name == "autoclicker_mouse":
                self.start_auto_click_mouse()
            elif hotkey_name == "macro_teclado":
                self.start_macro_teclado()
            elif hotkey_name == "macro_mouse":
                self.start_macro_mouse()
            elif hotkey_name == "gravar_macro_teclado":
                self.start_record_teclado()
            elif hotkey_name == "gravar_macro_mouse":
                self.start_record_mouse()

    # --- NOVOS SLOTS PARA GRAVAÇÃO DE MACRO ---
    def on_key_pressed_for_macro(self, key):
        global ultimo_tempo, macro_gravado_teclado
        if self.app_state != AppState.RECORDING_KEYBOARD:
            return
        if key == Key.esc:
            self.stop_record_teclado()
            return
        agora = time.time()
        atraso = agora - ultimo_tempo if ultimo_tempo != 0 else 0.0
        macro_gravado_teclado.append((key, "press", atraso))
        ultimo_tempo = agora
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)

    def on_key_released_for_macro(self, key):
        global ultimo_tempo, macro_gravado_teclado
        if self.app_state != AppState.RECORDING_KEYBOARD:
            return
        if key == Key.esc: return
        agora = time.time()
        atraso = agora - ultimo_tempo
        macro_gravado_teclado.append((key, "release", atraso))
        ultimo_tempo = agora
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)

    def on_mouse_event_for_macro(self, event_type, data):
        global ultimo_tempo, macro_gravado_mouse
        
        # Captura de pixel/posição
        if event_type == "click":
            x, y, button = data
            if self.is_capturing_pixel:
                self.add_pixel_wait_step(x, y, is_keyboard_macro=False)
                return
            if self.is_capturing_pixel_teclado:
                self.add_pixel_wait_step(x, y, is_keyboard_macro=True)
                return
        elif event_type == "capture_pos":
             x, y = data
             macro_gravado_mouse.append(("position", (x, y), 0.0))
             bus.macro_mouse_updated.emit(macro_gravado_mouse)
             set_status(f"Posição ({x}, {y}) capturada.")
             return

        # Lógica de gravação de macro
        if self.app_state != AppState.RECORDING_MOUSE:
            return
        
        agora = time.time()
        atraso = agora - ultimo_tempo if ultimo_tempo != 0 else 0.0
        
        if event_type == "move":
            x, y = data
            if self.recording_origin:
                origin_x, origin_y = self.recording_origin
                record_x, record_y = x - origin_x, y - origin_y
            else:
                record_x, record_y = x, y
            macro_gravado_mouse.append(("move", (record_x, record_y), atraso))
        
        elif event_type == "click":
            x, y, button = data
            macro_gravado_mouse.append(("click", button, atraso))

        elif event_type == "scroll":
            x, y, dx, dy = data
            direction = "para cima" if dy > 0 else "para baixo"
            macro_gravado_mouse.append(("scroll", (direction, dy), atraso))

        ultimo_tempo = agora
        bus.macro_mouse_updated.emit(macro_gravado_mouse)

    def set_default_hotkeys(self):
        default_keys = {
            "autoclicker_teclado": "Key.f6", "autoclicker_mouse": "Key.f7",
            "macro_teclado": "Key.f8", "macro_mouse": "Key.f10",
            "parar_tudo": "Key.f9", "gravar_macro_teclado": "Key.f1",
            "gravar_macro_mouse": "Key.f2", "parar_gravacao": "Key.f5",
        }
        self.hotkeys.update(default_keys)
        for name, key_str in self.hotkeys.items():
            if input_field := self.page_settings.findChild(QLineEdit, f"input_{name}"):
                input_field.setText(key_str)
        if self.listener:
            self.listener.update_hotkeys(self.hotkeys)
        set_status("Atalhos padrão carregados.")

    def play_start_sound(self):
        if self.page_settings.chk_enable_sounds.isChecked() and self.start_sound.isLoaded():
            self.start_sound.play()

    def play_stop_sound(self):
        if self.page_settings.chk_enable_sounds.isChecked() and self.stop_sound.isLoaded():
            self.stop_sound.play()
            
    def show_overlay_message(self, text: str):
        self.overlay.show_message(text)
        screen_geometry = QScreen.availableGeometry(QApplication.primaryScreen())
        self.overlay.move(
            screen_geometry.width() - self.overlay.frameGeometry().width() - 20,
            screen_geometry.height() - self.overlay.frameGeometry().height() - 60
        )

    def setup_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray_icon = QSystemTrayIcon(self)
        try:
            icon = QIcon("app.ico")
        except:
            pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
            painter.setBrush(QColor("#b890ff")); painter.setPen(Qt.NoPen); painter.drawEllipse(4, 4, 24, 24); painter.end()
            icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)
        tray_menu = QMenu()
        show_action = QAction("Mostrar", self); quit_action = QAction("Sair", self)
        show_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(show_action); tray_menu.addSeparator(); tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def quit_application(self):
        """Método seguro para fechar a aplicação."""
        self.listener.stop()
        self.listener_thread.quit()
        self.listener_thread.wait()
        QApplication.instance().quit()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        if event.spontaneous(): # Garante que o evento venha do usuário
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Automator está em Execução",
                "O aplicativo foi minimizado para a bandeja. Os atalhos continuam ativos.",
                QSystemTrayIcon.MessageIcon.Information, 2000
            )

    def set_active_page(self, btn: QPushButton, page: QWidget):
        for b in self.nav_buttons: b.setChecked(False)
        btn.setChecked(True)
        try:
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            self.pages.setCurrentWidget(page)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(220); anim.setStartValue(0.0); anim.setEndValue(1.0)
            anim.finished.connect(lambda: page.setGraphicsEffect(None))
            anim.start()
        except Exception:
            self.pages.setCurrentWidget(page)
        
    def start_cursor_tracker(self):
        self.mouse_pos_timer = QTimer(self)
        self.mouse_pos_timer.setInterval(100)
        self.mouse_pos_timer.timeout.connect(self._update_mouse_pos)
        self.mouse_pos_timer.start()

    def _update_mouse_pos(self):
        pos = QCursor.pos()
        self.page_macro.lbl_mouse_pos.setText(f"Posição atual: ({pos.x()}, {pos.y()})")

    def start_pixel_capture_mouse(self):
        self.is_capturing_pixel = True; self.hide(); set_status("MODO DE CAPTURA (MOUSE): Clique no pixel desejado...")

    def start_pixel_capture_teclado(self):
        self.is_capturing_pixel_teclado = True; self.hide(); set_status("MODO DE CAPTURA (TECLADO): Clique no pixel desejado...")
        
    def start_image_capture(self):
        self.hide()
        self.capture_widget = CaptureWidget()
        self.capture_widget.area_selecionada.connect(self.add_image_macro_step)
        QTimer.singleShot(50, self.capture_widget.show)
        set_status("MODO DE CAPTURA: Clique e arraste para selecionar uma área.")

    def add_image_macro_step(self, rect_coords):
        """Captura a imagem da área selecionada e a adiciona na macro."""
        global macro_gravado_mouse
        x_log, y_log, w_log, h_log = rect_coords

        if w_log == 0 or h_log == 0:
            self.showNormal()
            self.activateWindow()
            set_status("Captura cancelada (área inválida).")
            return
    
        ratio = self.screen().devicePixelRatio()
        
        # Converte as coordenadas lógicas para coordenadas físicas
        x_phys = int(x_log * ratio)
        y_phys = int(y_log * ratio)
        w_phys = int(w_log * ratio)
        h_phys = int(h_log * ratio)

        # Usa as coordenadas físicas corrigidas para tirar o screenshot
        screenshot = ImageGrab.grab(bbox=(x_phys, y_phys, x_phys + w_phys, y_phys + h_phys))
        
        # Salva a imagem com um nome único
        timestamp = int(time.time() * 1000)
        image_path = os.path.join("captures", f"capture_{timestamp}.png")
        screenshot.save(image_path)

        # Pergunta ao usuário qual ação adicionar
        items = ["Aguardar esta imagem aparecer", "Clicar no centro desta imagem"]
        item, ok = QInputDialog.getItem(self, "Ação de Macro de Imagem", 
                                        "Qual passo você deseja adicionar?", items, 0, False)

        if ok and item:
            action_type = "wait_image" if "Aguardar" in item else "click_image"
            macro_gravado_mouse.append((action_type, image_path, 0.0))
            bus.macro_mouse_updated.emit(macro_gravado_mouse)
            set_status(f"Passo '{item}' adicionado com a imagem '{os.path.basename(image_path)}'.")

        self.showNormal()
        self.activateWindow()

    def add_pixel_wait_step(self, x, y, is_keyboard_macro: bool = False):
        global macro_gravado_mouse, macro_gravado_teclado
        pixel_color = ImageGrab.grab().getpixel((x, y))
        if is_keyboard_macro:
            macro_gravado_teclado.append(('wait_pixel', (x, y, pixel_color), 0.0))
            bus.macro_keyboard_updated.emit(macro_gravado_teclado)
            self.is_capturing_pixel_teclado = False
        else:
            macro_gravado_mouse.append(('wait_pixel', (x, y, pixel_color), 0.0))
            bus.macro_mouse_updated.emit(macro_gravado_mouse)
            self.is_capturing_pixel = False
        self.showNormal(); self.activateWindow(); set_status(f"Passo 'Aguardar por Pixel' adicionado.")
        
    def _prepare_execution(self, is_macro: bool = False):
        """Prepara a UI para uma nova execução."""
        if is_macro:
            infinite = self.page_macro.is_infinite()
            reps = self.page_macro.get_reps()
        else:
            infinite = self.page_auto.is_infinite()
            reps = self.page_auto.get_reps()
        
        if not infinite:
            self.current_total_reps = reps
            self.progress.setVisible(True)
            self.progress.setValue(0)
        else:
            self.current_total_reps = None
            self.progress.setVisible(False)
        
        set_counter(0)
        self.stop_event.clear()
        self.app_state = AppState.EXECUTING
        self.play_start_sound()

    def start_auto_click_teclado(self):
        if self.app_state != AppState.IDLE: return
        keys = self.page_auto.get_selected_keys()
        if not keys: set_status("Nenhuma tecla selecionada."); return
        self._prepare_execution()
        set_status("Executando Auto Clicker (Teclado)…")
        self.show_overlay_message("Executando Auto Clicker...")

        def worker():
            delay_min = self.page_auto.get_delay()
            delay_max = self.page_auto.spin_speed_max.value()
            use_random = self.page_auto.chk_random_delay.isChecked()
            reps = self.page_auto.get_reps() if not self.page_auto.is_infinite() else -1
            counter = 0
            
            loop_range = range(reps) if reps != -1 else iter(int, 1)
            try:
                for _ in loop_range:
                    if self.stop_event.is_set(): break
                    for t in keys:
                        if self.stop_event.is_set(): break
                        KeyboardController().press(t)
                        KeyboardController().release(t)
                        time.sleep(0.01)
                    counter += 1
                    set_counter(counter)
                    delay = random.uniform(delay_min, delay_max) if use_random and delay_max > delay_min else delay_min
                    time.sleep(delay)
            finally:
                bus.execution_finished.emit() 
                
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def start_auto_click_mouse(self):
        if self.app_state != AppState.IDLE: return
        self._prepare_execution()
        set_status("Executando Auto Clicker (Mouse)…")
        self.show_overlay_message("Executando Auto Clicker...")
        
        def worker():
            button = self.page_auto.get_mouse_button()
            delay_min = self.page_auto.get_delay()
            delay_max = self.page_auto.spin_speed_max.value()
            use_random = self.page_auto.chk_random_delay.isChecked()
            reps = self.page_auto.get_reps() if not self.page_auto.is_infinite() else -1
            counter = 0

            loop_range = range(reps) if reps != -1 else iter(int, 1)
            try:
                for _ in loop_range:
                    if self.stop_event.is_set(): break
                    MouseController().click(button)
                    counter += 1
                    set_counter(counter)
                    delay = random.uniform(delay_min, delay_max) if use_random and delay_max > delay_min else delay_min
                    time.sleep(delay)
            finally:
                bus.execution_finished.emit() 
                
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
    
    def stop_all(self):
        if self.app_state != AppState.IDLE:
            set_status("Parando...")
            self.stop_event.set() # Sinaliza para a thread de trabalho parar
            # A transição de estado e limpeza da UI acontece em on_execution_finished
            if self.app_state in (AppState.RECORDING_KEYBOARD, AppState.RECORDING_MOUSE):
                 bus.execution_finished.emit() # Força a finalização se estiver gravando

    def on_execution_finished(self):
        self.app_state = AppState.IDLE
        self.play_stop_sound()
        self.overlay.hide()
        self.current_total_reps = None
        self.progress.setVisible(False)
        self.recording_origin = None
        self.is_capturing_pixel = False
        self.is_capturing_pixel_teclado = False
        set_status("Pronto")

    def start_record_teclado(self):
        global ultimo_tempo
        if self.app_state != AppState.IDLE: return
        self.app_state = AppState.RECORDING_KEYBOARD
        self.play_start_sound()
        ultimo_tempo = time.time()
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)
        self.show_overlay_message("Gravando Macro de Teclado...")
        set_status("Gravando Macro (Teclado)...")
        
    def stop_record_teclado(self):
        if self.app_state != AppState.RECORDING_KEYBOARD: return
        self.app_state = AppState.IDLE # Transição de estado
        bus.execution_finished.emit() # Usa o mesmo sinal para limpar a UI
        set_status("Gravação de Teclado encerrada.")
        
    def start_macro_teclado(self):
        if self.app_state != AppState.IDLE: return
        if not macro_gravado_teclado: set_status("Nenhuma macro de teclado gravada."); return
        self._prepare_execution(is_macro=True)
        set_status("Executando Macro (Teclado)…")
        self.show_overlay_message("Executando Macro de Teclado...")
        
        def worker():
            delay_min = self.page_macro.get_delay()
            delay_max = self.page_macro.spin_macro_speed_max.value()
            use_random = self.page_macro.chk_macro_random_delay.isChecked()
            reps = self.page_macro.get_reps() if not self.page_macro.is_infinite() else -1
            counter = 0

            loop_range = range(reps) if reps != -1 else iter(int, 1)
            try:
                for _ in loop_range:
                    if self.stop_event.is_set(): break
                    for tecla, acao, tempo in macro_gravado_teclado:
                        if self.stop_event.is_set(): break
                        
                        if tecla == 'wait_pixel':
                            target_x, target_y, target_color = acao; timeout = 30; start_time = time.time()
                            set_status(f"Aguardando pixel em ({target_x}, {target_y})...")
                            while time.time() - start_time < timeout:
                                if self.stop_event.is_set(): break
                                if ImageGrab.grab().getpixel((target_x, target_y)) == target_color:
                                    set_status("Pixel encontrado!"); break
                                time.sleep(0.2)
                            else: set_status(f"TIMEOUT: Pixel não encontrado. Parando."); self.stop_event.set()
                            if self.stop_event.is_set(): break
                            continue

                        time.sleep(tempo)
                        if acao == "press": KeyboardController().press(tecla)
                        elif acao == "release": KeyboardController().release(tecla)
                    
                    if self.stop_event.is_set(): break
                    counter += 1; set_counter(counter)
                    delay = random.uniform(delay_min, delay_max) if use_random and delay_max > delay_min else delay_min
                    time.sleep(delay)
            finally:
                bus.execution_finished.emit()
                
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def clear_current_macro_teclado(self):
        global macro_gravado_teclado
        macro_gravado_teclado.clear(); bus.macro_keyboard_updated.emit(macro_gravado_teclado)
        set_status("Macro de teclado atual limpa.")
    
    def delete_keyboard_macro_step(self):
        global macro_gravado_teclado
        current_row = self.page_macro.list_macro_teclado.currentRow()
        if current_row == -1: set_status("Nenhum passo selecionado para deletar."); return
        del macro_gravado_teclado[current_row]
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)
        set_status(f"Passo {current_row + 1} deletado.")

    def duplicate_keyboard_macro_step(self):
        global macro_gravado_teclado
        current_row = self.page_macro.list_macro_teclado.currentRow()
        if current_row == -1: set_status("Nenhum passo selecionado para duplicar."); return
        item_to_duplicate = macro_gravado_teclado[current_row]
        macro_gravado_teclado.insert(current_row + 1, item_to_duplicate)
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)
        set_status(f"Passo {current_row + 1} duplicado.")

    def _edit_step_delay(self, macro_list, row, is_mouse=False):
        action_type, value, old_delay = macro_list[row]
        new_delay, ok = QInputDialog.getDouble(self, "Editar Delay", "Novo delay (em segundos):", old_delay, 0, 100, 4)
        if ok and new_delay >= 0:
            macro_list[row] = (action_type, value, new_delay)
            if is_mouse: bus.macro_mouse_updated.emit(macro_list)
            else: bus.macro_keyboard_updated.emit(macro_list)
            set_status(f"Delay do passo {row + 1} alterado para {new_delay:.4f}s.")

    def edit_keyboard_macro_step(self, item):
        global macro_gravado_teclado
        row = self.page_macro.list_macro_teclado.row(item)
        if row == -1: return
        key_obj, action, old_delay = macro_gravado_teclado[row]
        if isinstance(key_obj, (Key, KeyCode)): self._edit_step_delay(macro_gravado_teclado, row, is_mouse=False)
        else: QMessageBox.information(self, "Edição Não Suportada", "A edição de detalhes para este tipo de passo ainda não foi implementada.")

    def edit_mouse_macro_step(self, item):
        row = self.page_macro.list_macro_mouse.row(item);
        if row == -1: return
        action_type, value, delay = macro_gravado_mouse[row]
        if action_type in ("move", "position"): self._edit_mouse_coords(row, (action_type, value, delay))
        elif action_type == "click": self._edit_mouse_click(row, (action_type, value, delay))
        elif action_type == "scroll": self._edit_mouse_scroll(row, (action_type, value, delay))
        elif action_type in ("wait_image", "click_image"): self._edit_step_delay(macro_gravado_mouse, row, is_mouse=True)
        else: QMessageBox.information(self, "Edição Não Suportada", "A edição deste tipo de passo não é suportada.")

    def _edit_mouse_coords(self, row, data):
        action_type, (old_x, old_y), old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Movimento", "O que você deseja editar?", ["Coordenadas", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(macro_gravado_mouse, row, is_mouse=True)
        elif choice == "Coordenadas":
            new_coords_str, ok = QInputDialog.getText(self, "Editar Coordenadas", "Novas coordenadas (x, y):", QLineEdit.EchoMode.Normal, f"{old_x}, {old_y}")
            if ok and new_coords_str:
                try:
                    parts = new_coords_str.split(','); new_x = int(parts[0].strip()); new_y = int(parts[1].strip())
                    macro_gravado_mouse[row] = (action_type, (new_x, new_y), old_delay)
                    bus.macro_mouse_updated.emit(macro_gravado_mouse); set_status(f"Coordenadas do passo {row + 1} alteradas.")
                except: QMessageBox.warning(self, "Erro de Formato", "Insira no formato 'x, y'")

    def _edit_mouse_click(self, row, data):
        action_type, old_button, old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Clique", "O que você deseja editar?", ["Botão do Mouse", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(macro_gravado_mouse, row, is_mouse=True)
        elif choice == "Botão do Mouse":
            items = ["Esquerdo", "Direito", "Meio"]; current_item = "Esquerdo"
            if old_button == MouseButton.right: current_item = "Direito"
            if old_button == MouseButton.middle: current_item = "Meio"
            new_button_str, ok = QInputDialog.getItem(self, "Editar Botão", "Selecione o novo botão:", items, items.index(current_item), False)
            if ok and new_button_str:
                button_map = {"Esquerdo": MouseButton.left, "Direito": MouseButton.right, "Meio": MouseButton.middle}
                macro_gravado_mouse[row] = (action_type, button_map[new_button_str], old_delay)
                bus.macro_mouse_updated.emit(macro_gravado_mouse); set_status(f"Botão do passo {row + 1} alterado.")

    def _edit_mouse_scroll(self, row, data):
        action_type, (old_direction, old_dy), old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Rolagem", "O que você deseja editar?", ["Direção/Força", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(macro_gravado_mouse, row, is_mouse=True)
        elif choice == "Direção/Força":
            new_dy, ok = QInputDialog.getInt(self, "Editar Força da Rolagem", "Força (positivo=cima, negativo=baixo):", old_dy, -100, 100, 1)
            if ok:
                new_direction = "para cima" if new_dy > 0 else "para baixo"
                macro_gravado_mouse[row] = (action_type, (new_direction, new_dy), old_delay)
                bus.macro_mouse_updated.emit(macro_gravado_mouse); set_status(f"Rolagem do passo {row + 1} alterada.")

    def handle_macro_reorder(self, macro_list: list, source_start: int, source_end: int, dest_row: int, is_mouse: bool = False):
        count = source_end - source_start + 1
        if source_start <= dest_row <= source_end + 1: return
        moved_items = [macro_list[i] for i in range(source_start, source_end + 1)]
        for i in sorted(range(source_start, source_end + 1), reverse=True): del macro_list[i]
        if dest_row > source_start: dest_row -= count
        for i, item in enumerate(moved_items): macro_list.insert(dest_row + i, item)
        if is_mouse: bus.macro_mouse_updated.emit(macro_list)
        else: bus.macro_keyboard_updated.emit(macro_list)
        set_status("Ordem da macro atualizada.")

    def start_record_mouse(self):
        global ultimo_tempo, macro_gravado_mouse
        if self.app_state != AppState.IDLE: return
        self.app_state = AppState.RECORDING_MOUSE
        self.play_start_sound()
        
        self.recording_origin = None
        if self.page_macro.chk_relative_mouse.isChecked():
            if not PYWIN32_AVAILABLE: set_status("ERRO: pywin32 não instalado.")
            else:
                try:
                    hwnd = win32gui.GetForegroundWindow(); title = win32gui.GetWindowText(hwnd); rect = win32gui.GetWindowRect(hwnd)
                    if not title: set_status("AVISO: Janela sem título. Gravando em modo absoluto.")
                    else:
                        macro_gravado_mouse.append(('set_relative_origin', title, 0.0))
                        self.recording_origin = (rect[0], rect[1])
                        set_status(f"Gravação relativa à janela '{title}' iniciada.")
                except Exception as e: set_status(f"Erro ao obter janela: {e}. Gravando em modo absoluto.")

        ultimo_tempo = time.time()
        bus.macro_mouse_updated.emit(macro_gravado_mouse)
        self.show_overlay_message("Gravando Macro de Mouse...")
        if not self.recording_origin: set_status("Gravando Macro (Mouse)...")

    def stop_record_mouse(self):
        if self.app_state != AppState.RECORDING_MOUSE: return
        self.app_state = AppState.IDLE
        bus.execution_finished.emit()
        set_status("Gravação de Mouse encerrada.")

    def start_macro_mouse(self):
        if self.app_state != AppState.IDLE: return
        if not macro_gravado_mouse: set_status("Nenhuma macro de mouse gravada."); return
        self._prepare_execution(is_macro=True)
        set_status("Executando Macro (Mouse)…")
        self.show_overlay_message("Executando Macro de Mouse...")
        
        def worker():
            delay_min = self.page_macro.get_delay()
            delay_max = self.page_macro.spin_macro_speed_max.value()
            use_random = self.page_macro.chk_macro_random_delay.isChecked()
            reps = self.page_macro.get_reps() if not self.page_macro.is_infinite() else -1
            counter = 0; playback_origin = (0, 0)
            
            loop_range = range(reps) if reps != -1 else iter(int, 1)
            try:
                for _ in loop_range:
                    if self.stop_event.is_set(): break
                    for action_type, value, tempo in macro_gravado_mouse:
                        if self.stop_event.is_set(): break
                        time.sleep(tempo)

                        if action_type == 'set_relative_origin':
                            window_title = value
                            try:
                                if not PYWIN32_AVAILABLE: raise ImportError("pywin32 não encontrado.")
                                hwnd = win32gui.FindWindow(None, window_title)
                                if hwnd == 0: set_status(f"ERRO: Janela '{window_title}' não encontrada."); self.stop_event.set()
                                else: rect = win32gui.GetWindowRect(hwnd); playback_origin = (rect[0], rect[1]); set_status(f"Origem definida para '{window_title}'.")
                            except Exception as e: set_status(f"Erro na janela relativa: {e}"); self.stop_event.set()
                            continue
                        
                        elif action_type in ("move", "position"):
                            origin_x, origin_y = playback_origin; rel_x, rel_y = value
                            MouseController().position = (origin_x + rel_x, origin_y + rel_y)
                        elif action_type == "click":
                            MouseController().click(value)
                        elif action_type == "scroll":
                            MouseController().scroll(0, value[1])
                        elif action_type == 'wait_pixel':
                            target_x, target_y, target_color = value; timeout = 30; start_time = time.time()
                            set_status(f"Aguardando pixel em ({target_x}, {target_y})...")
                            while time.time() - start_time < timeout:
                                if self.stop_event.is_set(): break
                                if ImageGrab.grab().getpixel((target_x, target_y)) == target_color:
                                    set_status("Pixel encontrado!"); break
                                time.sleep(0.2)
                            else: set_status(f"TIMEOUT: Pixel não encontrado. Parando."); self.stop_event.set()
                        elif action_type in ("wait_image", "click_image"):
                            try:
                                template = cv2.imread(value, 0)
                                w, h = template.shape[::-1]
                                timeout = 30; start_time = time.time(); found = False
                                set_status(f"Procurando por imagem '{os.path.basename(value)}'...")
                                while time.time() - start_time < timeout:
                                    if self.stop_event.is_set(): break
                                    screen_gray = cv2.cvtColor(np.array(ImageGrab.grab()), cv2.COLOR_BGR2GRAY)
                                    res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
                                    loc = np.where(res >= 0.8)
                                    if len(loc[0]) > 0:
                                        found = True; set_status(f"Imagem encontrada!")
                                        if action_type == "click_image":
                                            pt = (loc[1][0], loc[0][0]); center_x = pt[0] + w // 2; center_y = pt[1] + h // 2
                                            MouseController().position = (center_x, center_y); time.sleep(0.1)
                                            MouseController().click(MouseButton.left)
                                        break
                                    time.sleep(0.5)
                                if not found: set_status(f"TIMEOUT: Imagem não encontrada."); self.stop_event.set()
                            except Exception as e: set_status(f"Erro no processamento de imagem: {e}"); self.stop_event.set()
                    
                    if self.stop_event.is_set(): break
                    counter += 1; set_counter(counter)
                    delay = random.uniform(delay_min, delay_max) if use_random and delay_max > delay_min else delay_min
                    time.sleep(delay)
            finally:
                bus.execution_finished.emit() 
                
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        
    def clear_current_macro_mouse(self):
        global macro_gravado_mouse
        macro_gravado_mouse.clear(); bus.macro_mouse_updated.emit(macro_gravado_mouse)
        set_status("Macro de mouse atual limpa.")

    def delete_mouse_macro_step(self):
        global macro_gravado_mouse
        current_row = self.page_macro.list_macro_mouse.currentRow()
        if current_row == -1: set_status("Nenhum passo selecionado para deletar."); return
        del macro_gravado_mouse[current_row]
        bus.macro_mouse_updated.emit(macro_gravado_mouse)
        set_status(f"Passo {current_row + 1} da macro de mouse deletado.")
        
    def duplicate_mouse_macro_step(self):
        global macro_gravado_mouse
        current_row = self.page_macro.list_macro_mouse.currentRow()
        if current_row == -1: set_status("Nenhum passo selecionado para duplicar."); return
        item_to_duplicate = macro_gravado_mouse[current_row]
        macro_gravado_mouse.insert(current_row + 1, item_to_duplicate)
        bus.macro_mouse_updated.emit(macro_gravado_mouse)
        set_status(f"Passo {current_row + 1} da macro de mouse duplicado.")
    
    def _key_to_str(self, key_obj: Any) -> str:
        if isinstance(key_obj, Key): return KEY_MAP_SAVE.get(key_obj, f"Key.{key_obj.name}")
        if isinstance(key_obj, KeyCode): return key_obj.char if key_obj.char is not None else str(key_obj)
        return str(key_obj)

    def _str_to_key(self, key_str: str) -> Any:
        if not isinstance(key_str, str): return key_str # Já é um objeto de tecla
        if key_str.startswith("Key."):
            try:
                if mapped_key := KEY_MAP_LOAD.get(key_str): return mapped_key
                return getattr(Key, key_str.split(".")[-1].lower())
            except AttributeError: return None
        try: return KeyCode.from_char(key_str)
        except Exception: return None
    
    def _mouse_action_to_str(self, action):
        return str(action) if isinstance(action, MouseButton) else action
        
    def get_all_settings_as_dict(self) -> Dict[str, Any]:
        return {
            "autoclicker": self.page_auto.to_config(),
            "macro_keyboard": [(self._key_to_str(k), a, d) if k != 'wait_pixel' else (k, a, d) for k, a, d in macro_gravado_teclado],
            "macro_mouse": [(a, self._mouse_action_to_str(v), d) for a, v, d in macro_gravado_mouse],
            "macro_settings": {
                "infinite": self.page_macro.is_infinite(), "reps": self.page_macro.get_reps(),
                "delay": self.page_macro.get_delay(), "random_delay": self.page_macro.chk_macro_random_delay.isChecked(),
                "random_delay_max": self.page_macro.spin_macro_speed_max.value()
            },
            "hotkeys": self.hotkeys,
            "enable_sounds": self.page_settings.chk_enable_sounds.isChecked()
        }

    def set_all_settings_from_dict(self, data: Dict[str, Any]):
        global macro_gravado_teclado, macro_gravado_mouse
        self.page_auto.set_from_config(data.get("autoclicker", {}))
        
        macro_gravado_teclado = []
        for k_str, a, d in data.get("macro_keyboard", []):
            if k_str == 'wait_pixel': macro_gravado_teclado.append((k_str, a, d))
            else: k_obj = self._str_to_key(k_str); macro_gravado_teclado.append((k_obj, a, d))
        bus.macro_keyboard_updated.emit(macro_gravado_teclado)

        macro_gravado_mouse = []
        for a, v, d in data.get("macro_mouse", []):
            val = v
            if a == "click":
                try: val = getattr(MouseButton, v.split('.')[-1])
                except Exception: pass
            macro_gravado_mouse.append((a, val, d))
        bus.macro_mouse_updated.emit(macro_gravado_mouse)

        macro_settings = data.get("macro_settings", {})
        self.page_macro.chk_macro_infinite.setChecked(macro_settings.get("infinite", True))
        self.page_macro.spin_macro_reps.setValue(macro_settings.get("reps", 1))
        self.page_macro.spin_macro_speed.setValue(macro_settings.get("delay", 0.5))
        self.page_macro.chk_macro_random_delay.setChecked(macro_settings.get("random_delay", False))
        self.page_macro.spin_macro_speed_max.setValue(macro_settings.get("random_delay_max", 1.0))
        
        self.hotkeys = data.get("hotkeys", {})
        self.listener.update_hotkeys(self.hotkeys)
        for name, value in self.hotkeys.items():
            if inp := self.page_settings.findChild(QLineEdit, f"input_{name}"): inp.setText(value)
        
        self.page_settings.chk_enable_sounds.setChecked(data.get("enable_sounds", True))

    def load_profiles(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, "r", encoding="utf-8") as f: self._profiles = json.load(f)
            except: self._profiles = {}
        else: self._profiles = {}
        self.page_settings.refresh_profiles(self._profiles)

    def save_profile(self):
        name = self.page_settings.input_profile_name.text().strip()
        if not name: QMessageBox.warning(self, "Salvar Perfil", "Informe um nome."); return
        self._profiles[name] = self.get_all_settings_as_dict()
        try:
            with open(PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            set_status(f"Perfil '{name}' salvo."); self.page_settings.refresh_profiles(self._profiles)
        except Exception as e: QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar: {e}")

    def load_profile(self):
        name = self.page_settings.combo_profiles.currentText()
        if not name or name not in self._profiles: set_status("Nenhum perfil válido selecionado."); return
        self.set_all_settings_from_dict(self._profiles[name])
        set_status(f"Perfil '{name}' carregado.")

    def delete_profile(self):
        name = self.page_settings.combo_profiles.currentText()
        if not name or name not in self._profiles: set_status("Nenhum perfil para excluir."); return
        reply = QMessageBox.question(self, "Excluir Perfil", f"Tem certeza que deseja excluir '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self._profiles[name]
            try:
                with open(PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
                set_status(f"Perfil '{name}' excluído."); self.page_settings.refresh_profiles(self._profiles)
            except Exception as e: QMessageBox.critical(self, "Erro ao Excluir", f"Não foi possível salvar: {e}")

    def export_profiles(self):
        if not self._profiles: QMessageBox.information(self, "Exportar", "Não há perfis para exportar."); return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Perfis", "perfis.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            set_status(f"Perfis exportados para: {path}")
        except Exception as e: QMessageBox.critical(self, "Erro de Exportação", f"Erro: {e}")

    def import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Perfis", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f: data_from_file = json.load(f)
            if not isinstance(data_from_file, dict): raise ValueError("Estrutura inválida.")
            self._profiles.update(data_from_file)
            with open(PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            self.page_settings.refresh_profiles(self._profiles); set_status("Perfis importados.")
        except Exception as e: QMessageBox.critical(self, "Erro de Importação", f"Erro: {e}")

    def on_status(self, text: str):
        self.lbl_status.setText(f"Status: {text}")
        self.status_badge.setToolTip(f"Status: {text}")
        lower = text.lower()
        if "executando" in lower or "gravando" in lower: self.status_badge.setStyleSheet("background: #39d353; border-radius: 7px;")
        elif "pronto" in lower or "parado" in lower: self.status_badge.setStyleSheet("background: #6b6b7a; border-radius: 7px;")
        elif "erro" in lower or "não" in lower: self.status_badge.setStyleSheet("background: #ff5f56; border-radius: 7px;")
        else: self.status_badge.setStyleSheet("background: #6b6b7a; border-radius: 7px;")

    def on_counter(self, value: int):
        self.lbl_counter.setText(f"Repetições: {value}")
        if self.current_total_reps:
            try: self.progress.setValue(int(min(100, (value / self.current_total_reps) * 100)))
            except: self.progress.setValue(0)

# ====== Execução
def main():
    app = QApplication(sys.argv)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except: print("AVISO: Não foi possível definir o DPI awareness.")
    
    app.setStyleSheet("""
* {
    font-family: 'Segoe UI', 'Helvetica', sans-serif;
    font-size: 14px;
    color: #e6e6e6;
}
QMainWindow {
    background: #15151b;
}
#sidebar {
    background: #161622;
    border-right: 1px solid #2b2b3b;
    padding: 12px;
}
#logoTitle {
    font-size: 26px; font-weight: 700; color: #b890ff;
    margin-bottom: 18px; letter-spacing: 0.4px;
}
#navButton {
    text-align: left; padding: 12px 18px; background: transparent;
    border: none; border-radius: 10px; font-weight: 600; color: #dcdde6;
}
#navButton:hover { background: #232333; }
#navButton:checked {
    background: qlineargradient(x1:0 y1:0, x2:1 y2:0, stop:0 #2b2540, stop:1 #2f2948);
    border-left: 4px solid #b890ff; padding-left: 14px;
}
#statusLabel, #counterLabel { font-size: 13px; color: #a8a8b3; margin-top: 5px; }
#pageTitle { font-size: 22px; font-weight: 700; color: #f1f1f5; margin-bottom: 16px; }
#sectionFrame {
    background: #161622; border: 1px solid #2a2a3e; border-radius: 14px;
    padding: 18px; box-shadow: 0px 6px 18px rgba(0, 0, 0, 0.25);
}
#sectionTitle { font-size: 16px; font-weight: 700; color: #b890ff; margin-bottom: 8px; }
QPushButton {
    background: #222233; color: #f1f1f5; border: none; border-radius: 10px;
    padding: 10px 14px; font-weight: 600;
}
QPushButton:hover { background: #313143; }
QPushButton:pressed { background: #2b2b3b; }
#startButton { background: #b890ff; color: #1b1b1b; font-weight: 800; padding: 10px 16px; }
#startButton:hover { background: #c6a9ff; }
#recButton { background: #ff6b6b; color: #fff; font-weight: 700; }
#recButton:hover { background: #ff8080; }
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {
    background: #1f1f2a; color: #eaeaf0; border: 1px solid #2b2b3b;
    border-radius: 10px; padding: 8px;
    selection-background-color: #b890ff; selection-color: #0b0b0b;
}
QSlider::groove:horizontal {
    border: 1px solid #2b2b3b; height: 8px; background: #1f1f2a;
    margin: 2px 0; border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #b890ff; border: none; width: 16px;
    margin: -4px 0; border-radius: 8px;
}
QCheckBox::indicator {
    border: 1px solid #2b2b3b; width: 16px; height: 16px;
    border-radius: 4px; background-color: #1f1f2a;
}
QCheckBox::indicator:checked { background-color: #b890ff; border: 1px solid #b890ff; }
QScrollArea { border: none; }
QScrollBar:vertical { border: none; background: #161622; width: 10px; }
QScrollBar::handle:vertical { background: #1f1f2a; min-height: 20px; border-radius: 5px; }
QProgressBar {
    background: #151521; border: 1px solid #23232f;
    border-radius: 8px; height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b890ff, stop:1 #8f62ff);
    border-radius: 8px;
}
#statusBadge { border-radius: 7px; }
QWidget { outline: none; }
    """)
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()