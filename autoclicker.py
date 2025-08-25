import sys
import os
import json
import time
import threading
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSlider, QDoubleSpinBox, QSpinBox, QTextEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QMessageBox, QComboBox, QFileDialog, QSizePolicy, QGridLayout
)
from PySide6.QtGui import QIcon, QFont, QPalette, QColor, QCursor

# ====== Automação de teclado e mouse
from pynput.keyboard import Controller, Listener, Key, KeyCode
from pynput.mouse import Controller as MouseController, Button as MouseButton, Listener as MouseListener

keyboard = Controller()
mouse = MouseController()

CONFIG_FILE = "macro_dashboard_qt.json"
PROFILES_FILE = "macro_profiles.json"

# ----- Teclas especiais mapeadas
SPECIAL_KEYS: Dict[str, Key] = {
    "Espaço": Key.space,
    "Enter": Key.enter,
    "Shift": Key.shift,
    "Ctrl": Key.ctrl,
    "Alt": Key.alt,
    "Tab": Key.tab,
    "Backspace": Key.backspace,
    "Esc": Key.esc,
}

# ====== Estado e comunicação com a UI via sinais (thread-safe)
class Bus(QObject):
    status = Signal(str)      # texto de status
    counter = Signal(int)     # repetições
    macro_teclado_text = Signal(str)
    macro_mouse_text = Signal(str)

bus = Bus()

# ====== Estado global simples (poderia virar uma classe dedicada)
executando = False
gravando = False
gravando_mouse = False
contador = 0
macro_gravado_teclado: List[Tuple[Any, str, float]] = []  # (tecla, "press"/"release", delay_base)
macro_gravado_mouse: List[Tuple[Any, Any, float]] = [] # (tipo, valor, delay_base)
ultimo_tempo = 0.0 # <--- Variável global para gravação de tempo

def fmt_macro_lines_teclado(macro: List[Tuple[Any, str, float]]) -> str:
    lines = []
    for i, (t, a, d) in enumerate(macro):
        delay_str = f"{d:.4f}s" if d > 0.001 else "0.000s"
        lines.append(f"{i+1:02d}: {str(t).replace('Key.', '')} - {a.capitalize()} (Delay: {delay_str})")
    return "\n".join(lines)

def fmt_macro_lines_mouse(macro: List[Tuple[Any, Any, float]]) -> str:
    lines = []
    for i, (action_type, value, d) in enumerate(macro):
        delay_str = f"{d:.4f}s" if d > 0.001 else "0.000s"
        if action_type == "move":
            lines.append(f"{i+1:02d}: Mover para ({value[0]}, {value[1]}) (Delay: {delay_str})")
        elif action_type == "click":
            lines.append(f"{i+1:02d}: Clique {str(value).split('.')[-1].capitalize()} (Delay: {delay_str})")
        elif action_type == "scroll":
            lines.append(f"{i+1:02d}: Rolagem {value[0]} (Delay: {delay_str})")
        elif action_type == "position":
             lines.append(f"{i+1:02d}: Pos. Fixa ({value[0]}, {value[1]})")
    return "\n".join(lines)


# ====== Worker helpers
def set_status(text: str):
    bus.status.emit(text)

def set_counter(value: int):
    bus.counter.emit(value)

def set_macro_text_teclado(macro: List[Tuple[Any, str, float]]):
    bus.macro_teclado_text.emit(fmt_macro_lines_teclado(macro))

def set_macro_text_mouse(macro: List[Tuple[Any, Any, float]]):
    bus.macro_mouse_text.emit(fmt_macro_lines_mouse(macro))


# ====== Listeners globais
def start_global_listener(main_window):
    global ultimo_tempo, macro_gravado_teclado, gravando, gravando_mouse
    
    # Flags para as teclas modificadoras (Ctrl e Shift)
    ctrl_pressed = False
    shift_pressed = False

    def on_press_teclado(key):
        nonlocal ctrl_pressed, shift_pressed
        global gravando, ultimo_tempo, macro_gravado_teclado
        
        # Monitora o estado das teclas Ctrl e Shift
        if key == Key.ctrl_l or key == Key.ctrl_r:
            ctrl_pressed = True
        if key == Key.shift_l or key == Key.shift_r:
            shift_pressed = True

        # Atalho para capturar a posição do mouse
        if ctrl_pressed and shift_pressed and isinstance(key, KeyCode) and key.char == 'c':
            main_window.capture_mouse_position()
            return
        
        # Ignora o atalho de gravação para que ele não seja registrado na macro
        key_name = main_window._key_to_str(key)
        hotkey_gravar_teclado = main_window.hotkeys.get("gravar_macro_teclado")
        hotkey_gravar_mouse = main_window.hotkeys.get("gravar_macro_mouse")
        hotkey_parar_gravacao = main_window.hotkeys.get("parar_gravacao")
        
        if key_name == hotkey_gravar_teclado or key_name == hotkey_gravar_mouse or key_name == hotkey_parar_gravacao:
            return

        if gravando:
            if key == Key.esc:
                main_window.stop_record_teclado()
                return
            agora = time.time()
            atraso = agora - ultimo_tempo if ultimo_tempo != 0 else 0.0
            macro_gravado_teclado.append((key, "press", atraso))
            ultimo_tempo = agora
            set_macro_text_teclado(macro_gravado_teclado)

    def on_release_teclado(key):
        nonlocal ctrl_pressed, shift_pressed
        global gravando, ultimo_tempo, macro_gravado_teclado
        
        # Ignora o atalho de gravação
        key_name = main_window._key_to_str(key)
        hotkey_gravar_teclado = main_window.hotkeys.get("gravar_macro_teclado")
        hotkey_gravar_mouse = main_window.hotkeys.get("gravar_macro_mouse")
        hotkey_parar_gravacao = main_window.hotkeys.get("parar_gravacao")

        if key_name == hotkey_gravar_teclado or key_name == hotkey_gravar_mouse or key_name == hotkey_parar_gravacao:
            return
        
        if key == Key.ctrl_l or key == Key.ctrl_r:
            ctrl_pressed = False
        if key == Key.shift_l or key == Key.shift_r:
            shift_pressed = False
        
        if gravando:
            if key == Key.esc:
                return # Já tratado no press
            agora = time.time()
            atraso = agora - ultimo_tempo
            macro_gravado_teclado.append((key, "release", atraso))
            ultimo_tempo = agora
            set_macro_text_teclado(macro_gravado_teclado)
    
    def on_move_mouse(x, y):
        global gravando_mouse, ultimo_tempo, macro_gravado_mouse
        if gravando_mouse:
            agora = time.time()
            atraso = agora - ultimo_tempo
            macro_gravado_mouse.append(("move", (x, y), atraso))
            ultimo_tempo = agora
            set_macro_text_mouse(macro_gravado_mouse)

    def on_click_mouse(x, y, button, pressed):
        global gravando_mouse, ultimo_tempo, macro_gravado_mouse
        if gravando_mouse:
            agora = time.time()
            atraso = agora - ultimo_tempo
            if pressed:
                macro_gravado_mouse.append(("click", button, atraso))
                ultimo_tempo = agora
                set_macro_text_mouse(macro_gravado_mouse)

    def on_scroll_mouse(x, y, dx, dy):
        global gravando_mouse, ultimo_tempo, macro_gravado_mouse
        if gravando_mouse:
            agora = time.time()
            atraso = agora - ultimo_tempo
            direction = "para cima" if dy > 0 else "para baixo"
            macro_gravado_mouse.append(("scroll", (direction, dy), atraso))
            ultimo_tempo = agora
            set_macro_text_mouse(macro_gravado_mouse)

    def on_press_global(key):
        try:
            hotkeys = main_window.hotkeys
            
            # Converte a tecla pressionada para o formato de string usado nas configs
            key_name = main_window._key_to_str(key)
            
            if key_name == hotkeys.get("macro_teclado"):
                threading.Thread(target=main_window.start_macro_teclado, daemon=True).start()
            elif key_name == hotkeys.get("autoclicker_teclado"):
                main_window.start_auto_click_teclado()
            elif key_name == hotkeys.get("autoclicker_mouse"):
                threading.Thread(target=main_window.start_auto_click_mouse, daemon=True).start()
            elif key_name == hotkeys.get("macro_mouse"):
                 threading.Thread(target=main_window.start_macro_mouse, daemon=True).start()
            elif key_name == hotkeys.get("parar_tudo"):
                main_window.stop_all()
            # Novos atalhos de gravação
            elif key_name == hotkeys.get("gravar_macro_teclado"):
                main_window.start_record_teclado()
            elif key_name == hotkeys.get("gravar_macro_mouse"):
                main_window.start_record_mouse()
            elif key_name == hotkeys.get("parar_gravacao"):
                main_window.stop_all()
        except Exception:
            pass

    keyboard_listener = Listener(
        on_press=lambda k: [on_press_teclado(k), on_press_global(k)],
        on_release=on_release_teclado
    )
    keyboard_listener.daemon = True
    keyboard_listener.start()
    
    mouse_listener = MouseListener(
        on_move=on_move_mouse,
        on_click=on_click_mouse,
        on_scroll=on_scroll_mouse
    )
    mouse_listener.daemon = True
    mouse_listener.start()

    return keyboard_listener, mouse_listener


# ====== Páginas (QWidgets)

class PageAutoClickers(QWidget):
    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Auto Clickers")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        # Seção de Auto Clicker de Teclado
        keys_frame = QFrame()
        keys_frame.setObjectName("sectionFrame")
        keys_layout = QVBoxLayout(keys_frame)
        keys_layout.addWidget(QLabel("Auto Clicker de Teclado:"))
        
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
        for i, name in enumerate(SPECIAL_KEYS.keys()):
            chk = QCheckBox(name)
            chk.setChecked(False)
            self.chk_specials[name] = chk
            specials_grid.addWidget(chk)
        keys_layout.addLayout(specials_grid)
        root.addWidget(keys_frame)

        # Seção de Auto Clicker de Mouse
        mouse_ac_frame = QFrame()
        mouse_ac_frame.setObjectName("sectionFrame")
        mouse_ac_layout = QVBoxLayout(mouse_ac_frame)
        mouse_ac_layout.addWidget(QLabel("Auto Clicker do Mouse:"))

        row_button = QHBoxLayout()
        row_button.addWidget(QLabel("Botão do mouse:"))
        self.combo_mouse_button = QComboBox()
        self.combo_mouse_button.addItems(["Esquerdo", "Direito", "Meio"])
        self.combo_mouse_button.setCurrentText("Esquerdo")
        row_button.addWidget(self.combo_mouse_button)
        mouse_ac_layout.addLayout(row_button)
        root.addWidget(mouse_ac_frame)

        # Seção de Configuração Comum
        config_frame = QFrame()
        config_frame.setObjectName("sectionFrame")
        config_layout = QVBoxLayout(config_frame)

        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Delay entre ciclos (s):"))
        
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.001, 100.0)
        self.spin_speed.setDecimals(3)
        self.spin_speed.setSingleStep(0.01)
        self.spin_speed.setValue(0.500)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 1000)
        self.slider_speed.setValue(int(self.spin_speed.value() * 10))
        
        self.slider_speed.valueChanged.connect(lambda val: self.spin_speed.setValue(val / 1000.0))
        self.spin_speed.valueChanged.connect(lambda val: self.slider_speed.setValue(int(val * 1000)))

        row_speed.addWidget(self.slider_speed)
        row_speed.addWidget(self.spin_speed)
        config_layout.addLayout(row_speed)

        row_rep = QHBoxLayout()
        self.chk_infinite = QCheckBox("Modo infinito")
        self.chk_infinite.setChecked(True)
        self.chk_infinite.stateChanged.connect(self._toggle_reps)
        row_rep.addWidget(self.chk_infinite)
        row_rep.addWidget(QLabel("Repetições:"))
        self.spin_reps = QSpinBox()
        self.spin_reps.setRange(1, 999999)
        self.spin_reps.setValue(1)
        self.spin_reps.setEnabled(False) # Inicia desabilitado
        row_rep.addWidget(self.spin_reps)
        config_layout.addLayout(row_rep)
        
        root.addWidget(config_frame)
        
        row_btns = QHBoxLayout()
        self.btn_start_keyboard_ac = QPushButton("▶ Iniciar Auto Clicker Teclado")
        self.btn_start_keyboard_ac.setObjectName("startButton")
        self.btn_start_mouse_ac = QPushButton("▶ Iniciar Auto Clicker Mouse")
        self.btn_start_mouse_ac.setObjectName("startButton")
        self.btn_stop = QPushButton("⏹ Parar Tudo")
        row_btns.addWidget(self.btn_start_keyboard_ac)
        row_btns.addWidget(self.btn_start_mouse_ac)
        row_btns.addWidget(self.btn_stop)
        root.addLayout(row_btns)

        root.addStretch()

    def _toggle_reps(self, state):
        self.spin_reps.setEnabled(not self.chk_infinite.isChecked())

    def get_selected_keys(self) -> List[Any]:
        keys = []
        text = self.input_keys.text().strip()
        for ch in text:
            keys.append(ch)
        for name, chk in self.chk_specials.items():
            if chk.isChecked():
                keys.append(SPECIAL_KEYS[name])
        return keys

    def get_delay(self) -> float:
        return self.spin_speed.value()

    def is_infinite(self) -> bool:
        return self.chk_infinite.isChecked()

    def get_reps(self) -> int:
        return self.spin_reps.value()

    def get_mouse_button(self) -> MouseButton:
        button_name = self.combo_mouse_button.currentText()
        return MouseButton.left if button_name == "Esquerdo" else MouseButton.right if button_name == "Direito" else MouseButton.middle

    def set_from_config(self, cfg: dict):
        self.input_keys.setText(cfg.get("teclas_normais", ""))
        for name, v in cfg.get("teclas_especiais", {}).items():
            if name in self.chk_specials:
                self.chk_specials[name].setChecked(bool(v))
        
        # --- Modificação para a velocidade ---
        speed_val = float(cfg.get("velocidade", 0.5))
        self.spin_speed.setValue(speed_val)
        self.slider_speed.setValue(int(speed_val * 1000))
        # ------------------------------------

        self.chk_infinite.setChecked(bool(cfg.get("modo_infinito", True)))
        self._toggle_reps(self.chk_infinite.checkState())
        try:
            self.spin_reps.setValue(int(cfg.get("repeticoes", 1)))
        except Exception:
            pass
        self.combo_mouse_button.setCurrentText(cfg.get("mouse_button", "Esquerdo"))

    def to_config(self) -> dict:
        return {
            "teclas_normais": self.input_keys.text(),
            "teclas_especiais": {name: chk.isChecked() for name, chk in self.chk_specials.items()},
            "velocidade": self.get_delay(),
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
        
        # Layout principal com 2 colunas
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(20)
        
        # Coluna da esquerda (Teclado)
        teclado_frame = QFrame()
        teclado_frame.setObjectName("sectionFrame")
        teclado_layout = QVBoxLayout(teclado_frame)
        teclado_layout.addWidget(QLabel("Macro de Teclado:"))
        
        row_teclado_rec = QHBoxLayout()
        self.btn_rec_teclado = QPushButton("⏺ Gravar Macro")
        self.btn_stop_rec_teclado = QPushButton("⏹ Parar Gravação")
        row_teclado_rec.addWidget(self.btn_rec_teclado)
        row_teclado_rec.addWidget(self.btn_stop_rec_teclado)
        teclado_layout.addLayout(row_teclado_rec)

        row_teclado_play = QHBoxLayout()
        self.btn_play_teclado = QPushButton("▶ Executar Macro")
        self.btn_play_teclado.setObjectName("startButton")
        self.btn_clear_teclado = QPushButton("❌ Limpar Macro")
        row_teclado_play.addWidget(self.btn_play_teclado)
        row_teclado_play.addWidget(self.btn_clear_teclado)
        teclado_layout.addLayout(row_teclado_play)

        self.txt_macro_teclado = QTextEdit()
        self.txt_macro_teclado.setReadOnly(True)
        self.txt_macro_teclado.setPlaceholderText("Sua macro de teclado aparecerá aqui...")
        self.txt_macro_teclado.setMinimumHeight(160)
        teclado_layout.addWidget(self.txt_macro_teclado)

        # Seção de perfis de teclado
        profiles_frame = QFrame()
        profiles_frame.setObjectName("sectionFrame")
        profiles_layout = QVBoxLayout(profiles_frame)
        profiles_layout.addWidget(QLabel("Gerenciar Perfis de Teclado:"))
        
        prof_row1 = QHBoxLayout()
        self.input_profile_name = QLineEdit()
        self.input_profile_name.setPlaceholderText("Nome do perfil (ex: Farm_1)")
        self.btn_profile_save = QPushButton("💾 Salvar como Perfil")
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
        teclado_layout.addWidget(profiles_frame)

        grid_layout.addWidget(teclado_frame, 0, 0, 1, 1)

        # Coluna da direita (Mouse)
        mouse_frame = QFrame()
        mouse_frame.setObjectName("sectionFrame")
        mouse_layout = QVBoxLayout(mouse_frame)
        mouse_layout.addWidget(QLabel("Macro de Mouse:"))
        
        row_mouse_rec = QHBoxLayout()
        self.btn_rec_mouse = QPushButton("⏺ Gravar Macro")
        self.btn_stop_rec_mouse = QPushButton("⏹ Parar Gravação")
        row_mouse_rec.addWidget(self.btn_rec_mouse)
        row_mouse_rec.addWidget(self.btn_stop_rec_mouse)
        mouse_layout.addLayout(row_mouse_rec)

        row_mouse_play = QHBoxLayout()
        self.btn_play_mouse = QPushButton("▶ Executar Macro")
        self.btn_play_mouse.setObjectName("startButton")
        self.btn_clear_mouse = QPushButton("❌ Limpar Macro")
        row_mouse_play.addWidget(self.btn_play_mouse)
        row_mouse_play.addWidget(self.btn_clear_mouse)
        mouse_layout.addLayout(row_mouse_play)
        
        self.lbl_mouse_pos = QLabel("Posição atual: (0, 0)")
        self.lbl_mouse_pos.setStyleSheet("color: #a0a0b0; font-size: 16px; font-weight: bold;")
        self.lbl_mouse_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mouse_layout.addWidget(self.lbl_mouse_pos)

        self.txt_macro_mouse = QTextEdit()
        self.txt_macro_mouse.setReadOnly(True)
        self.txt_macro_mouse.setPlaceholderText("Sua macro do mouse aparecerá aqui...")
        self.txt_macro_mouse.setMinimumHeight(160)
        mouse_layout.addWidget(self.txt_macro_mouse)

        grid_layout.addWidget(mouse_frame, 0, 1, 1, 1)

        root.addLayout(grid_layout)
        
        # Seção de repetições para macros
        macro_reps_frame = QFrame()
        macro_reps_frame.setObjectName("sectionFrame")
        macro_reps_layout = QVBoxLayout(macro_reps_frame)

        # Slider de velocidade
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

        # Checkbox e Spinbox de repetições
        row_rep = QHBoxLayout()
        self.chk_macro_infinite = QCheckBox("Modo infinito")
        self.chk_macro_infinite.setChecked(True)
        self.chk_macro_infinite.stateChanged.connect(self._toggle_reps)
        row_rep.addWidget(self.chk_macro_infinite)
        row_rep.addWidget(QLabel("Repetições:"))
        self.spin_macro_reps = QSpinBox()
        self.spin_macro_reps.setRange(1, 999999)
        self.spin_macro_reps.setValue(1)
        self.spin_macro_reps.setEnabled(False) # Inicia desabilitado
        row_rep.addWidget(self.spin_macro_reps)
        macro_reps_layout.addLayout(row_rep)
        root.addWidget(macro_reps_frame)

        root.addStretch()

    def _toggle_reps(self, state):
        self.spin_macro_reps.setEnabled(not self.chk_macro_infinite.isChecked())

    def get_reps(self) -> int:
        return self.spin_macro_reps.value()

    def is_infinite(self) -> bool:
        return self.chk_macro_infinite.isChecked()

    def get_delay(self) -> float:
        return self.spin_macro_speed.value()

    def set_macro_text_teclado(self, text: str):
        self.txt_macro_teclado.setPlainText(text)
    
    def set_macro_text_mouse(self, text: str):
        self.txt_macro_mouse.setPlainText(text)

    def refresh_profiles(self, profiles: Dict[str, Any]):
        self.combo_profiles.clear()
        names = sorted(profiles.keys())
        self.combo_profiles.addItems(names)


class PageSettings(QWidget):
    def __init__(self):
        super().__init__()
        self.is_capturing = False
        self.current_hotkey_field = None
        self.hotkey_listener = None
        self.build_ui()
        self.window().hotkey_fields = { # Mapeamento para facilitar a busca
            "autoclicker_teclado": self.input_ac_teclado,
            "autoclicker_mouse": self.input_ac_mouse,
            "macro_teclado": self.input_macro_teclado,
            "macro_mouse": self.input_macro_mouse,
            "parar_tudo": self.input_parar_tudo,
            "gravar_macro_teclado": self.input_gravar_macro_teclado,
            "gravar_macro_mouse": self.input_gravar_macro_mouse,
            "parar_gravacao": self.input_parar_gravacao
        }

    def build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Configurações")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        general_frame = QFrame()
        general_frame.setObjectName("sectionFrame")
        general_layout = QVBoxLayout(general_frame)
        general_layout.addWidget(QLabel("Configuração Geral:"))
        row1 = QHBoxLayout()
        self.btn_save_cfg = QPushButton("💾 Salvar Configuração Geral")
        self.btn_load_cfg = QPushButton("📂 Carregar Configuração Geral")
        self.btn_delete_cfg = QPushButton("❌ Deletar Configuração Geral")
        row1.addWidget(self.btn_save_cfg)
        row1.addWidget(self.btn_load_cfg)
        row1.addWidget(self.btn_delete_cfg)
        general_layout.addLayout(row1)
        root.addWidget(general_frame)

        profiles_frame = QFrame()
        profiles_frame.setObjectName("sectionFrame")
        profiles_layout = QVBoxLayout(profiles_frame)
        profiles_layout.addWidget(QLabel("Perfis de Macro (Importar / Exportar):"))
        row2 = QHBoxLayout()
        self.btn_export_profiles = QPushButton("⬆ Exportar Perfis")
        self.btn_import_profiles = QPushButton("⬇ Importar Perfis")
        row2.addWidget(self.btn_export_profiles)
        row2.addWidget(self.btn_import_profiles)
        profiles_layout.addLayout(row2)
        root.addWidget(profiles_frame)

        hotkeys_frame = QFrame()
        hotkeys_frame.setObjectName("sectionFrame")
        hotkeys_layout = QVBoxLayout(hotkeys_frame)
        hotkeys_layout.addWidget(QLabel("Atalhos Globais:"))
        
        grid_hotkeys = QGridLayout()
        self.lbl_info_hotkeys = QLabel("Clique no campo para capturar uma tecla.")
        self.lbl_info_hotkeys.setStyleSheet("color: #a0a0b0;")
        grid_hotkeys.addWidget(self.lbl_info_hotkeys, 0, 0, 1, 2)
        
        self.input_ac_teclado = QLineEdit(objectName="input_autoclicker_teclado")
        self.input_ac_mouse = QLineEdit(objectName="input_autoclicker_mouse")
        self.input_macro_teclado = QLineEdit(objectName="input_macro_teclado")
        self.input_macro_mouse = QLineEdit(objectName="input_macro_mouse")
        self.input_parar_tudo = QLineEdit(objectName="input_parar_tudo")
        # Novos campos
        self.input_gravar_macro_teclado = QLineEdit(objectName="input_gravar_macro_teclado")
        self.input_gravar_macro_mouse = QLineEdit(objectName="input_gravar_macro_mouse")
        self.input_parar_gravacao = QLineEdit(objectName="input_parar_gravacao")
        
        self.input_ac_teclado.setReadOnly(True)
        self.input_ac_mouse.setReadOnly(True)
        self.input_macro_teclado.setReadOnly(True)
        self.input_macro_mouse.setReadOnly(True)
        self.input_parar_tudo.setReadOnly(True)
        # Novos campos como somente leitura
        self.input_gravar_macro_teclado.setReadOnly(True)
        self.input_gravar_macro_mouse.setReadOnly(True)
        self.input_parar_gravacao.setReadOnly(True)
        
        grid_hotkeys.addWidget(QLabel("Autoclicker Teclado:"), 1, 0)
        grid_hotkeys.addWidget(self.input_ac_teclado, 1, 1)
        grid_hotkeys.addWidget(QLabel("Autoclicker Mouse:"), 2, 0)
        grid_hotkeys.addWidget(self.input_ac_mouse, 2, 1)
        grid_hotkeys.addWidget(QLabel("Macro Teclado (Executar):"), 3, 0)
        grid_hotkeys.addWidget(self.input_macro_teclado, 3, 1)
        grid_hotkeys.addWidget(QLabel("Macro Mouse (Executar):"), 4, 0)
        grid_hotkeys.addWidget(self.input_macro_mouse, 4, 1)
        grid_hotkeys.addWidget(QLabel("Macro Teclado (Gravar):"), 5, 0)
        grid_hotkeys.addWidget(self.input_gravar_macro_teclado, 5, 1)
        grid_hotkeys.addWidget(QLabel("Macro Mouse (Gravar):"), 6, 0)
        grid_hotkeys.addWidget(self.input_gravar_macro_mouse, 6, 1)
        grid_hotkeys.addWidget(QLabel("Parar Gravação:"), 7, 0)
        grid_hotkeys.addWidget(self.input_parar_gravacao, 7, 1)
        grid_hotkeys.addWidget(QLabel("Parar Tudo:"), 8, 0)
        grid_hotkeys.addWidget(self.input_parar_tudo, 8, 1)
        
        hotkeys_layout.addLayout(grid_hotkeys)
        root.addWidget(hotkeys_frame)

        root.addStretch()
        
    def start_capture_hotkey(self, line_edit: QLineEdit):
        if self.is_capturing:
            self.stop_capture_hotkey()
        
        self.is_capturing = True
        self.current_hotkey_field = line_edit
        self.current_hotkey_field.setPlaceholderText("Pressione uma tecla...")
        self.current_hotkey_field.setStyleSheet("background: #4a4a62; border: 1px solid #5c6efc;")
        self.lbl_info_hotkeys.setText("Capturando tecla...")

        def on_press(key):
            try:
                # Converte o objeto da tecla para string
                key_str = self.window()._key_to_str(key)
                if not key_str: return
                self.current_hotkey_field.setText(key_str)
                
                # --- Correção: Usa o nome do objeto para identificar o campo
                hotkey_name = self.current_hotkey_field.objectName().replace("input_", "")
                self.window().hotkeys[hotkey_name] = key_str
                self.window().restart_global_listeners()
                # --- Fim da correção
                
            except Exception:
                pass
            finally:
                self.stop_capture_hotkey()
                return False  # Para o listener

        self.hotkey_listener = Listener(on_press=on_press)
        self.hotkey_listener.start()

    def stop_capture_hotkey(self):
        if self.hotkey_listener and self.hotkey_listener.running:
            self.hotkey_listener.stop()
        self.is_capturing = False
        if self.current_hotkey_field:
            self.current_hotkey_field.setPlaceholderText("")
            self.current_hotkey_field.setStyleSheet("")
            self.current_hotkey_field = None
        self.lbl_info_hotkeys.setText("Clique no campo para capturar uma tecla.")
        set_status("Captura de atalho finalizada.")


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
        txt.setPlainText(
            "📖 **Como usar:**\n"
            "1) **Página Auto Clickers:** digite teclas normais (ex.: wasd) e/ou selecione especiais, ajuste delay e repetições para o autoclicker de teclado. Use o seletor de botão para o autoclicker de mouse.\n"
            "   - **Atenção:** Os botões de iniciar executam a automação correspondente.\n"
            "   - Parar tudo: botão dedicado ou seu atalho global.\n"
            "2) **Página Macros:** grave sequências de teclado ou mouse, com movimentos e cliques. `ESC` para parar a gravação.\n"
            "   - **Atenção:** A gravação do mouse é sensível, evite movimentos bruscos e desnecessários.\n"
            "   - **Capturar Posição:** Use o atalho **Ctrl+Shift+C** para adicionar uma posição fixa à sua macro de mouse.\n"
            "   - Executar Macro: botões dedicados ou seus atalhos globais.\n"
            "3) **Perfis:** salve a macro de teclado atual com um nome. Carregue/exclua pelo seletor.\n"
            "4) **Configurações:** salve/carregue config geral, exporte/importe perfis e personalize os atalhos globais.\n\n"
            "⚠ **Observações:**\n"
            "- As teclas são enviadas para a janela em foco (traga o app/jogo para frente antes de executar).\n"
            "- Alguns apps/jogos podem bloquear automação.\n"
            "- Use por sua conta e risco; verifique termos de uso do software-alvo.\n\n"
            "**Atalhos globais:**\n"
            "- Os atalhos podem ser definidos na página de Configurações.\n"
            "- **ESC:** para a gravação de macro de teclado ou mouse\n"
        )
        root.addWidget(txt)
        root.addStretch()

# ====== Janela principal
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Clicker + Macro Dashboard (Qt)")
        self.resize(1000, 650)
        try:
            self.setWindowIcon(QIcon("app.ico"))
        except Exception:
            pass
        
        self.hotkeys = {}
        self.keyboard_listener = None
        self.mouse_listener = None
        self.mouse_pos_timer = None

        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        vside = QVBoxLayout(sidebar)
        vside.setContentsMargins(12, 12, 12, 12)
        
        logo = QLabel("Automator")
        logo.setObjectName("logoTitle")
        vside.addWidget(logo)

        self.btn_go_auto = QPushButton("⚙️ Auto Clickers")
        self.btn_go_macro = QPushButton("🎬 Macros")
        self.btn_go_settings = QPushButton("🧰 Configurações")
        self.btn_go_about = QPushButton("ℹ️ Sobre")
        for b in [self.btn_go_auto, self.btn_go_macro, self.btn_go_settings, self.btn_go_about]:
            b.setObjectName("navButton")
            vside.addWidget(b)
            
        vside.addStretch()
        
        self.lbl_status = QLabel("Status: Pronto")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_counter = QLabel("Repetições: 0")
        self.lbl_counter.setObjectName("counterLabel")
        vside.addWidget(self.lbl_status)
        vside.addWidget(self.lbl_counter)

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

        self.btn_go_auto.clicked.connect(lambda: self.pages.setCurrentWidget(self.page_auto))
        self.btn_go_macro.clicked.connect(lambda: self.pages.setCurrentWidget(self.page_macro))
        self.btn_go_settings.clicked.connect(lambda: self.pages.setCurrentWidget(self.page_settings))
        self.btn_go_about.clicked.connect(lambda: self.pages.setCurrentWidget(self.page_about))

        bus.status.connect(self.on_status)
        bus.counter.connect(self.on_counter)
        bus.macro_teclado_text.connect(self.page_macro.set_macro_text_teclado)
        bus.macro_mouse_text.connect(self.page_macro.set_macro_text_mouse)

        # Autoclickers
        self.page_auto.btn_start_keyboard_ac.clicked.connect(self.start_auto_click_teclado)
        self.page_auto.btn_start_mouse_ac.clicked.connect(lambda: threading.Thread(target=self.start_auto_click_mouse, daemon=True).start())
        self.page_auto.btn_stop.clicked.connect(self.stop_all)
        
        # Macros
        self.page_macro.btn_rec_teclado.clicked.connect(self.start_record_teclado)
        self.page_macro.btn_stop_rec_teclado.clicked.connect(self.stop_record_teclado)
        self.page_macro.btn_play_teclado.clicked.connect(lambda: threading.Thread(target=self.start_macro_teclado, daemon=True).start())
        self.page_macro.btn_clear_teclado.clicked.connect(self.clear_current_macro_teclado)
        
        self.page_macro.btn_rec_mouse.clicked.connect(self.start_record_mouse)
        self.page_macro.btn_stop_rec_mouse.clicked.connect(self.stop_record_mouse)
        self.page_macro.btn_play_mouse.clicked.connect(lambda: threading.Thread(target=self.start_macro_mouse, daemon=True).start())
        self.page_macro.btn_clear_mouse.clicked.connect(self.clear_current_macro_mouse)
        
        self.page_macro.btn_profile_save.clicked.connect(self.save_profile)
        self.page_macro.btn_profile_load.clicked.connect(self.load_profile)
        self.page_macro.btn_profile_delete.clicked.connect(self.delete_profile)

        self.page_settings.btn_save_cfg.clicked.connect(self.save_config)
        self.page_settings.btn_load_cfg.clicked.connect(self.load_config)
        self.page_settings.btn_delete_cfg.clicked.connect(self.delete_config)
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


        self.load_config(silent=True)
        self.load_profiles()
        self.restart_global_listeners()
        self.start_cursor_tracker()

    def restart_global_listeners(self):
        """Reinicia os listeners globais de teclado e mouse."""
        global gravando, gravando_mouse
        gravando = False
        gravando_mouse = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.keyboard_listener, self.mouse_listener = start_global_listener(self)
        set_status("Listeners globais reiniciados.")
        
    def start_cursor_tracker(self):
        self.mouse_pos_timer = QTimer(self)
        self.mouse_pos_timer.setInterval(100)  # 100ms
        self.mouse_pos_timer.timeout.connect(self._update_mouse_pos)
        self.mouse_pos_timer.start()

    def _update_mouse_pos(self):
        x, y = QCursor.pos().x(), QCursor.pos().y()
        self.page_macro.lbl_mouse_pos.setText(f"Posição atual: ({x}, {y})")

    def capture_mouse_position(self):
        global macro_gravado_mouse
        x, y = QCursor.pos().x(), QCursor.pos().y()
        # Tempo de espera de 0s, pois é uma posição fixa
        macro_gravado_mouse.append(("position", (x, y), 0.0)) 
        set_macro_text_mouse(macro_gravado_mouse)
        set_status(f"Posição ({x}, {y}) capturada.")
        
    # ===== Ações (executadas em thread quando necessário)
    def start_auto_click_teclado(self):
        global executando, contador
        if executando:
            set_status("Já em execução.")
            return

        keys = self.page_auto.get_selected_keys()
        if not keys:
            set_status("Nenhuma tecla selecionada.")
            return
        
        executando = True
        contador = 0
        set_counter(contador)
        set_status("Executando Auto Clicker (Teclado)…")
        delay = self.page_auto.get_delay()
        infinite = self.page_auto.is_infinite()
        reps = self.page_auto.get_reps()
        
        def worker():
            global executando, contador
            try:
                if infinite:
                    while executando:
                        for t in keys:
                            if not executando: break
                            keyboard.press(t)
                            keyboard.release(t)
                            time.sleep(0.01)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
                else:
                    for _ in range(reps):
                        if not executando: break
                        for t in keys:
                            if not executando: break
                            keyboard.press(t)
                            keyboard.release(t)
                            time.sleep(0.01)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
            finally:
                executando = False
                gravando = False
                gravando_mouse = False
                set_status("Pronto")
                
        threading.Thread(target=worker, daemon=True).start()

    def start_auto_click_mouse(self):
        global executando, contador
        if executando:
            set_status("Já em execução.")
            return

        button = self.page_auto.get_mouse_button()
        delay = self.page_auto.get_delay()
        infinite = self.page_auto.is_infinite()
        reps = self.page_auto.get_reps()
        executando = True
        contador = 0
        set_counter(contador)
        set_status("Executando Auto Clicker (Mouse)…")
        
        def worker():
            global executando, contador
            try:
                if infinite:
                    while executando:
                        mouse.click(button)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
                else:
                    for _ in range(reps):
                        if not executando: break
                        mouse.click(button)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
            finally:
                executando = False
                gravando = False
                gravando_mouse = False
                set_status("Pronto")
                
        threading.Thread(target=worker, daemon=True).start()
    
    def stop_all(self):
        global executando, gravando, gravando_mouse
        executando = False
        gravando = False
        gravando_mouse = False
        set_status("Parado")

    def start_record_teclado(self):
        global gravando, macro_gravado_teclado, ultimo_tempo
        if gravando: return
        self.stop_all()
        macro_gravado_teclado = []
        gravando = True
        ultimo_tempo = time.time()
        set_macro_text_teclado(macro_gravado_teclado)
        set_status("Gravando Macro (Teclado)... Pressione ESC ou o atalho para parar.")
        
    def stop_record_teclado(self):
        global gravando
        if not gravando: return
        gravando = False
        set_status("Gravação de Teclado encerrada. Macro salva.")
        
    def start_macro_teclado(self):
        global executando, contador, macro_gravado_teclado
        if not macro_gravado_teclado:
            set_status("Nenhuma macro de teclado gravada.")
            return
        if executando: return
        
        executando = True
        contador = 0
        set_counter(contador)
        set_status("Executando Macro (Teclado)…")
        infinite = self.page_macro.is_infinite()
        reps = self.page_macro.get_reps()
        delay = self.page_macro.get_delay()
        
        def worker():
            global executando, contador
            try:
                if infinite:
                    while executando:
                        for tecla, acao, tempo in macro_gravado_teclado:
                            if not executando: break
                            time.sleep(tempo)
                            if acao == "press": keyboard.press(tecla)
                            elif acao == "release": keyboard.release(tecla)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
                else:
                    for _ in range(reps):
                        if not executando: break
                        for tecla, acao, tempo in macro_gravado_teclado:
                            if not executando: break
                            time.sleep(tempo)
                            if acao == "press": keyboard.press(tecla)
                            elif acao == "release": keyboard.release(tecla)
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
            finally:
                executando = False
                gravando = False
                gravando_mouse = False
                set_status("Pronto")
                
        threading.Thread(target=worker, daemon=True).start()

    def clear_current_macro_teclado(self):
        global macro_gravado_teclado
        macro_gravado_teclado = []
        set_macro_text_teclado(macro_gravado_teclado)
        set_status("Macro de teclado atual limpa.")
    
    def start_record_mouse(self):
        global gravando_mouse, macro_gravado_mouse, ultimo_tempo
        if gravando_mouse: return
        self.stop_all()
        macro_gravado_mouse = []
        gravando_mouse = True
        ultimo_tempo = time.time()
        set_macro_text_mouse(macro_gravado_mouse)
        set_status("Gravando Macro (Mouse)... Pressione ESC ou o atalho para parar.")

    def stop_record_mouse(self):
        global gravando_mouse
        if not gravando_mouse: return
        gravando_mouse = False
        set_status("Gravação de Mouse encerrada. Macro salva.")

    def start_macro_mouse(self):
        global executando, contador, macro_gravado_mouse
        if not macro_gravado_mouse:
            set_status("Nenhuma macro de mouse gravada.")
            return
        if executando: return
        
        executando = True
        contador = 0
        set_counter(contador)
        set_status("Executando Macro (Mouse)…")
        infinite = self.page_macro.is_infinite()
        reps = self.page_macro.get_reps()
        delay = self.page_macro.get_delay()
        
        def worker():
            global executando, contador
            try:
                if infinite:
                    while executando:
                        for action_type, value, tempo in macro_gravado_mouse:
                            if not executando: break
                            time.sleep(tempo)
                            if action_type == "move" or action_type == "position":
                                mouse.position = value
                            elif action_type == "click":
                                mouse.click(value)
                            elif action_type == "scroll":
                                mouse.scroll(0, value[1])
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
                else:
                    for _ in range(reps):
                        if not executando: break
                        for action_type, value, tempo in macro_gravado_mouse:
                            if not executando: break
                            time.sleep(tempo)
                            if action_type == "move" or action_type == "position":
                                mouse.position = value
                            elif action_type == "click":
                                mouse.click(value)
                            elif action_type == "scroll":
                                mouse.scroll(0, value[1])
                        contador += 1
                        set_counter(contador)
                        time.sleep(delay)
            finally:
                executando = False
                gravando = False
                gravando_mouse = False
                set_status("Pronto")
                
        threading.Thread(target=worker, daemon=True).start()
        
    def clear_current_macro_mouse(self):
        global macro_gravado_mouse
        macro_gravado_mouse = []
        set_macro_text_mouse(macro_gravado_mouse)
        set_status("Macro de mouse atual limpa.")
    
    def _key_to_str(self, key_obj: Any) -> str:
        """Converte um objeto de tecla para uma string serializável."""
        if isinstance(key_obj, Key):
            return f"Key.{key_obj.name}"
        if isinstance(key_obj, KeyCode):
            return key_obj.char
        return str(key_obj)

    def _str_to_key(self, key_str: str) -> Any:
        """Converte uma string de volta para um objeto de tecla."""
        if key_str.startswith("Key."):
            try:
                # Trata as teclas especiais corretamente
                return getattr(Key, key_str.split(".")[-1])
            except AttributeError:
                return None # Retorna None para teclas não reconhecidas
        return KeyCode.from_char(key_str)
    
    def _mouse_action_to_str(self, action):
        if isinstance(action, MouseButton):
            return str(action)
        return action
        
    def save_config(self):
        cfg = self.page_auto.to_config()
        cfg["macro_teclado"] = [(self._key_to_str(k), a, d) for k, a, d in macro_gravado_teclado]
        cfg["macro_mouse"] = [(a, self._mouse_action_to_str(v), d) for a, v, d in macro_gravado_mouse]
        cfg["macro_infinite"] = self.page_macro.is_infinite()
        cfg["macro_repeticoes"] = self.page_macro.get_reps()
        cfg["macro_velocidade"] = self.page_macro.get_delay()
        
        self.hotkeys = {
            "autoclicker_teclado": self.page_settings.input_ac_teclado.text(),
            "autoclicker_mouse": self.page_settings.input_ac_mouse.text(),
            "macro_teclado": self.page_settings.input_macro_teclado.text(),
            "macro_mouse": self.page_settings.input_macro_mouse.text(),
            "parar_tudo": self.page_settings.input_parar_tudo.text(),
            "gravar_macro_teclado": self.page_settings.input_gravar_macro_teclado.text(),
            "gravar_macro_mouse": self.page_settings.input_gravar_macro_mouse.text(),
            "parar_gravacao": self.page_settings.input_parar_gravacao.text(),
        }
        cfg["hotkeys"] = self.hotkeys
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        set_status("Configuração salva.")

    def load_config(self, silent=False):
        global macro_gravado_teclado, macro_gravado_mouse
        if not os.path.exists(CONFIG_FILE):
            if not silent: set_status("Nenhum arquivo de configuração.")
            self.page_settings.input_ac_teclado.setText(self._key_to_str(Key.f6))
            self.page_settings.input_ac_mouse.setText(self._key_to_str(Key.f7))
            self.page_settings.input_macro_teclado.setText(self._key_to_str(Key.f8))
            self.page_settings.input_macro_mouse.setText(self._key_to_str(Key.f10))
            self.page_settings.input_parar_tudo.setText(self._key_to_str(Key.f9))
            self.page_settings.input_gravar_macro_teclado.setText(self._key_to_str(Key.f1))
            self.page_settings.input_gravar_macro_mouse.setText(self._key_to_str(Key.f2))
            self.page_settings.input_parar_gravacao.setText(self._key_to_str(Key.f5))
            self.hotkeys = {
                "autoclicker_teclado": self._key_to_str(Key.f6),
                "autoclicker_mouse": self._key_to_str(Key.f7),
                "macro_teclado": self._key_to_str(Key.f8),
                "macro_mouse": self._key_to_str(Key.f10),
                "parar_tudo": self._key_to_str(Key.f9),
                "gravar_macro_teclado": self._key_to_str(Key.f1),
                "gravar_macro_mouse": self._key_to_str(Key.f2),
                "parar_gravacao": self._key_to_str(Key.f5)
            }
            return
        
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.page_auto.set_from_config({
            "teclas_normais": cfg.get("teclas_normais", ""),
            "teclas_especiais": cfg.get("teclas_especiais", {}),
            "velocidade": cfg.get("velocidade", 0.5),
            "modo_infinito": cfg.get("modo_infinito", True),
            "repeticoes": cfg.get("repeticoes", 1),
            "mouse_button": cfg.get("mouse_button", "Esquerdo")
        })

        self.page_macro.chk_macro_infinite.setChecked(bool(cfg.get("macro_infinite", True)))
        self.page_macro._toggle_reps(self.page_macro.chk_macro_infinite.checkState())
        try:
            self.page_macro.spin_macro_reps.setValue(int(cfg.get("macro_repeticoes", 1)))
        except Exception:
            pass
        self.page_macro.spin_macro_speed.setValue(float(cfg.get("macro_velocidade", 0.5)))
        
        macro_teclado_recarregada = []
        for k_str, a, d in cfg.get("macro_teclado", []):
            try:
                key_obj = self._str_to_key(k_str)
                if key_obj:
                    macro_teclado_recarregada.append((key_obj, a, d))
                else:
                    print(f"Aviso: Tecla desconhecida '{k_str}' não foi carregada.")
            except AttributeError:
                print(f"Aviso: Tecla desconhecida '{k_str}' não foi carregada.")
        macro_gravado_teclado = macro_teclado_recarregada
        set_macro_text_teclado(macro_gravado_teclado)
        
        macro_gravado_mouse = []
        for a, v, d in cfg.get("macro_mouse", []):
            try:
                if a == "click":
                    button = getattr(MouseButton, v.split('.')[-1])
                    macro_gravado_mouse.append((a, button, d))
                else:
                    macro_gravado_mouse.append((a, v, d))
            except AttributeError:
                print(f"Aviso: Ação de mouse desconhecida '{v}' não foi carregada.")
        set_macro_text_mouse(macro_gravado_mouse)
        
        self.hotkeys = cfg.get("hotkeys", {})
        self.page_settings.input_ac_teclado.setText(self.hotkeys.get("autoclicker_teclado", ""))
        self.page_settings.input_ac_mouse.setText(self.hotkeys.get("autoclicker_mouse", ""))
        self.page_settings.input_macro_teclado.setText(self.hotkeys.get("macro_teclado", ""))
        self.page_settings.input_macro_mouse.setText(self.hotkeys.get("macro_mouse", ""))
        self.page_settings.input_parar_tudo.setText(self.hotkeys.get("parar_tudo", ""))
        self.page_settings.input_gravar_macro_teclado.setText(self.hotkeys.get("gravar_macro_teclado", ""))
        self.page_settings.input_gravar_macro_mouse.setText(self.hotkeys.get("gravar_macro_mouse", ""))
        self.page_settings.input_parar_gravacao.setText(self.hotkeys.get("parar_gravacao", ""))
        
        if not silent: set_status("Configuração carregada.")

    def delete_config(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            set_status("Configuração deletada.")
            self.load_config(silent=True)
        else:
            set_status("Nenhuma configuração para deletar.")

    def load_profiles(self):
        profiles = {}
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                    profiles_json = json.load(f)
                    if not isinstance(profiles_json, dict):
                        raise ValueError("Estrutura do arquivo de perfis inválida.")
                    
                    for name, data in profiles_json.items():
                        # Converte a lista de strings para o formato de teclas
                        profile_data = []
                        for k_str, a, d in data:
                            try:
                                key_obj = self._str_to_key(k_str)
                                if key_obj:
                                    profile_data.append((key_obj, a, d))
                                else:
                                    print(f"Aviso: Tecla desconhecida '{k_str}' no perfil '{name}'.")
                            except (AttributeError, ValueError):
                                print(f"Aviso: Tecla desconhecida '{k_str}' no perfil '{name}'.")
                        profiles[name] = profile_data
                        
            except (json.JSONDecodeError, ValueError) as e:
                QMessageBox.warning(self, "Erro", f"Arquivo de perfis corrompido: {e}")
                profiles = {}
        self._profiles = profiles
        self.page_macro.refresh_profiles(self._profiles)

    def save_profile(self):
        global macro_gravado_teclado
        name = self.page_macro.input_profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Perfis", "Informe um nome para o perfil.")
            return
        
        if not macro_gravado_teclado:
            QMessageBox.warning(self, "Perfis", "A macro de teclado está vazia. Não é possível salvar.")
            return
        
        # Converte os objetos de tecla em strings antes de salvar
        macro_salva = [(self._key_to_str(k), a, d) for k, a, d in macro_gravado_teclado]
        self._profiles[name] = macro_salva
        
        try:
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, ensure_ascii=False, indent=2)
            self.page_macro.refresh_profiles(self._profiles)
            set_status(f"Perfil '{name}' salvo.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o perfil: {e}")

    def load_profile(self):
        global macro_gravado_teclado
        name = self.page_macro.combo_profiles.currentText().strip()
        if not name:
            set_status("Nenhum perfil selecionado.")
            return
            
        data = self._profiles.get(name)
        if not data:
            set_status("Perfil não encontrado.")
            return

        macro_gravado_teclado = data
        set_macro_text_teclado(macro_gravado_teclado)
        set_status(f"Perfil '{name}' carregado.")

    def delete_profile(self):
        name = self.page_macro.combo_profiles.currentText().strip()
        if not name:
            set_status("Nenhum perfil selecionado.")
            return
        if name in self._profiles:
            del self._profiles[name]
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, ensure_ascii=False, indent=2)
            self.page_macro.refresh_profiles(self._profiles)
            set_status(f"Perfil '{name}' excluído.")
        else:
            set_status("Perfil não encontrado.")

    def export_profiles(self):
        if not self._profiles:
            QMessageBox.information(self, "Exportar Perfis", "Não há perfis para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Perfis", "perfis.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, ensure_ascii=False, indent=2)
            set_status(f"Perfis exportados para: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Exportação", f"Erro ao exportar: {e}")

    def import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Perfis", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data_from_file = json.load(f)
            if not isinstance(data_from_file, dict): raise ValueError("Estrutura do arquivo inválida. Esperado um dicionário.")
            self._profiles.update(data_from_file)
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, ensure_ascii=False, indent=2)
            self.page_macro.refresh_profiles(self._profiles)
            set_status("Perfis importados.")
        except Exception as e:
            QMessageBox.critical(self, "Importar Perfis", f"Erro ao importar: {e}")

    def on_status(self, text: str):
        self.lbl_status.setText(f"Status: {text}")

    def on_counter(self, value: int):
        self.lbl_counter.setText(f"Repetições: {value}")


# ====== Execução
def main():
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        * {
            font-family: 'Segoe UI', 'Helvetica', sans-serif;
            font-size: 14px;
        }
        QMainWindow {
            background: #1e1e2d;
            color: #e0e0e0;
        }
        
        #sidebar {
            background: #2a2a3e;
            border-right: 1px solid #3c3c52;
        }
        #logoTitle {
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 20px;
        }
        #navButton {
            text-align: left;
            padding: 12px 16px;
            background: transparent;
            border: none;
            color: #e0e0e0;
            border-radius: 8px;
        }
        #navButton:hover {
            background: #3c3c52;
        }
        #navButton:pressed {
            background: #4a4a62;
        }
        #statusLabel, #counterLabel {
            font-size: 12px;
            color: #a0a0b0;
        }
        
        #pageTitle {
            font-size: 20px;
            font-weight: 600;
            color: #5c6efc;
            margin-bottom: 15px;
        }
        #sectionFrame {
            border: 1px solid #3c3c52;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }

        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #2a2a3e;
            color: #e0e0e0;
            border: 1px solid #3c3c52;
            border-radius: 6px;
            padding: 8px;
        }
        QLineEdit:read-only {
            background: #3c3c52;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox::down-arrow {
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiI+PHBhdGggZD0iTTggMTFsLTggNmgxNmwzLTZ6IiBmaWxsPSIjRTBFMEUwIi8+PC9zdmc+);
        }

        QPushButton {
            background: #3c3c52;
            color: #e0e0e0;
            border: none;
            border-radius: 8px;
            padding: 10px 15px;
            font-weight: 500;
        }
        QPushButton:hover {
            background: #4a4a62;
        }
        QPushButton:pressed {
            background: #5c5c7a;
        }
        #startButton {
            background: #5c6efc;
            color: #ffffff;
            font-weight: bold;
        }
        #startButton:hover {
            background: #7a8efc;
        }
        #startButton:pressed {
            background: #4a5ee0;
        }

        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
            border: 1px solid #3c3c52;
            background-color: #2a2a3e;
            padding: 4px;
        }
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #3c3c52;
        }
        QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
            width: 8px;
            height: 8px;
        }
    """)
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()