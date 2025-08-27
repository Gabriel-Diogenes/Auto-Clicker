"""
Módulo para a PageAutoClickers, a página da UI responsável pelas
configurações e controle dos auto clickers de teclado e mouse.
"""
from typing import List, Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSlider, QDoubleSpinBox, QSpinBox,
    QFrame, QGridLayout, QComboBox
)
from pynput.mouse import Button as MouseButton

# Importa as constantes do nosso módulo de utilitários
from app.utils.constants import SPECIAL_KEYS


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
        
        # --- Auto Clicker de Teclado ---
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

        # --- Auto Clicker de Mouse ---
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

        # --- Configurações de Execução ---
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
        return {"Esquerdo": MouseButton.left, "Direito": MouseButton.right, "Meio": MouseButton.middle}.get(
            self.combo_mouse_button.currentText(), MouseButton.left)

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