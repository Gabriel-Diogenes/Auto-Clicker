# app/ui/dialogs/rule_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QDialogButtonBox, QWidget, QFrame, QCheckBox,
    QSpinBox, QDoubleSpinBox, QSlider, QGridLayout  # <--- CORRIGIDO AQUI
)
from PySide6.QtCore import Qt

# Importamos as constantes para ter acesso às teclas especiais
from app.utils.constants import SPECIAL_KEYS

class RuleDialog(QDialog):
    """Uma janela de diálogo aprimorada para criar regras complexas para o bot."""
    def __init__(self, targets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar ou Editar Regra")
        self.setMinimumWidth(550)

        self.targets = targets
        self.rule_data = None

        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self):
        # --- Layout Principal ---
        layout = QVBoxLayout(self)

        # --- Seção 1: Gatilho (Trigger) ---
        trigger_frame = QFrame()
        trigger_frame.setObjectName("sectionFrame")
        trigger_layout = QVBoxLayout(trigger_frame)
        trigger_title = QLabel("Gatilho (Quando...)")
        trigger_title.setObjectName("sectionTitle")
        
        trigger_form = QHBoxLayout()
        trigger_form.addWidget(QLabel("QUANDO o alvo"))
        self.target_combo = QComboBox()
        target_names = [t['name'] for t in self.targets]
        self.target_combo.addItems(target_names)
        trigger_form.addWidget(self.target_combo, 1)
        trigger_form.addWidget(QLabel("for encontrado..."))
        
        trigger_layout.addWidget(trigger_title)
        trigger_layout.addLayout(trigger_form)
        
        # --- Seção 2: Ação (Faça...) ---
        action_frame = QFrame()
        action_frame.setObjectName("sectionFrame")
        action_layout = QVBoxLayout(action_frame)
        action_title = QLabel("Ação (Faça...)")
        action_title.setObjectName("sectionTitle")

        action_form = QHBoxLayout()
        action_form.addWidget(QLabel("...EXECUTE a ação"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(["Clique Esquerdo", "Clique Direito", "Pressionar Tecla"])
        action_form.addWidget(self.action_combo, 1)

        # Container para os detalhes da ação de Teclado
        self.key_details_widget = QWidget()
        key_details_layout = QVBoxLayout(self.key_details_widget)
        key_details_layout.setContentsMargins(0, 10, 0, 0)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Digite teclas normais (ex: 'w', '123')")
        
        self.chk_specials: dict[str, QCheckBox] = {}
        specials_grid = QGridLayout() # Esta linha agora funciona
        col, row = 0, 0
        for name in SPECIAL_KEYS.keys():
            chk = QCheckBox(name)
            self.chk_specials[name] = chk
            specials_grid.addWidget(chk, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

        key_details_layout.addWidget(self.key_input)
        key_details_layout.addWidget(QLabel("...e/ou selecione teclas especiais:"))
        key_details_layout.addLayout(specials_grid)
        self.key_details_widget.hide()

        action_layout.addWidget(action_title)
        action_layout.addLayout(action_form)
        action_layout.addWidget(self.key_details_widget)

        # --- Seção 3: Configuração de Execução ---
        exec_frame = QFrame()
        exec_frame.setObjectName("sectionFrame")
        exec_layout = QVBoxLayout(exec_frame)
        exec_title = QLabel("Configuração de Execução")
        exec_title.setObjectName("sectionTitle")
        
        self.chk_infinite = QCheckBox("Executar continuamente (enquanto o alvo estiver visível)")
        self.chk_infinite.setChecked(True)
        
        row_reps = QHBoxLayout()
        lbl_reps = QLabel("Número de repetições:")
        self.spin_reps = QSpinBox()
        self.spin_reps.setRange(1, 999999); self.spin_reps.setValue(1); self.spin_reps.setEnabled(False)
        row_reps.addWidget(lbl_reps); row_reps.addWidget(self.spin_reps, 1)
        
        row_delay = QHBoxLayout()
        row_delay.addWidget(QLabel("Delay entre ciclos (s):"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.0, 100.0); self.spin_delay.setDecimals(3); self.spin_delay.setValue(0.100)
        row_delay.addWidget(self.spin_delay, 1)

        row_random = QHBoxLayout()
        self.chk_random_delay = QCheckBox("Delay Aleatório até (s):")
        self.spin_delay_max = QDoubleSpinBox()
        self.spin_delay_max.setRange(0.0, 100.0); self.spin_delay_max.setDecimals(3); self.spin_delay_max.setValue(0.500); self.spin_delay_max.setEnabled(False)
        row_random.addWidget(self.chk_random_delay)
        row_random.addWidget(self.spin_delay_max, 1)

        exec_layout.addWidget(exec_title)
        exec_layout.addWidget(self.chk_infinite)
        exec_layout.addLayout(row_reps)
        exec_layout.addLayout(row_delay)
        exec_layout.addLayout(row_random)

        # --- Botões OK e Cancelar ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        layout.addWidget(trigger_frame)
        layout.addWidget(action_frame)
        layout.addWidget(exec_frame)
        layout.addWidget(self.button_box)

    def _connect_signals(self):
        self.action_combo.currentTextChanged.connect(self.on_action_change)
        self.chk_infinite.stateChanged.connect(lambda state: self.spin_reps.setEnabled(not bool(state)))
        self.chk_random_delay.stateChanged.connect(lambda state: self.spin_delay_max.setEnabled(bool(state)))
        
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
    
    def on_action_change(self, text):
        """Mostra ou esconde os detalhes da ação de Teclado."""
        self.key_details_widget.setVisible(text == "Pressionar Tecla")

    def accept(self):
        """Chamado quando o usuário clica em OK para validar e coletar os dados."""
        action_value = None
        if self.action_combo.currentText() == "Pressionar Tecla":
            keys = list(self.key_input.text().strip())
            special_keys_names = [name for name, chk in self.chk_specials.items() if chk.isChecked()]
            
            action_value = {"normal": keys, "special": special_keys_names}
            if not keys and not special_keys_names:
                # Mostra um erro em vez de simplesmente fechar
                QMessageBox.warning(self, "Ação Inválida", "Você deve digitar ou selecionar pelo menos uma tecla.")
                return 

        execution_config = {
            "reps": -1 if self.chk_infinite.isChecked() else self.spin_reps.value(),
            "delay": self.spin_delay.value(),
            "random_delay": self.chk_random_delay.isChecked(),
            "delay_max": self.spin_delay_max.value()
        }

        self.rule_data = {
            "target_name": self.target_combo.currentText(),
            "action_name": self.action_combo.currentText(),
            "action_value": action_value,
            "execution": execution_config
        }
        super().accept()

    def get_rule_data(self):
        """Retorna os dados da regra que o usuário configurou."""
        return self.rule_data