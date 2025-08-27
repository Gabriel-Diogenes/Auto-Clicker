"""
Módulo para a PageMacros, a página da UI responsável pela gravação,
visualização e execução de macros de teclado e mouse.
"""
import os
from pynput.keyboard import Key, KeyCode

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QDoubleSpinBox, QSpinBox,
    QFrame, QGridLayout, QListWidget
)

# Verifica a disponibilidade da biblioteca pywin32 para a função de janela relativa
try:
    import win32gui
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


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
        
        # --- Macro de Teclado ---
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

        # --- Macro de Mouse ---
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
        
        # --- Configurações de Execução de Macro ---
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