from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QListWidget
)

class PageBotCreator(QWidget):
    # Sinais que esta página emitirá para a MainWindow
    roi_request = Signal()
    add_image_target_request = Signal()
    add_color_target_request = Signal()

    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        # ANTES, os layouts eram criados com (self), o que os definia imediatamente.
        # AGORA, criamos sem um "pai" e definimos no final.
        main_layout = QHBoxLayout() # <--- MUDANÇA AQUI
        main_layout.setSpacing(20)

        # --- PAINEL DE CONFIGURAÇÃO (ESQUERDA) ---
        config_frame = QFrame()
        config_frame.setObjectName("sectionFrame")
        config_layout = QVBoxLayout(config_frame)
        config_frame.setMaximumWidth(400)

        # ... (o resto da criação de botões e labels continua igual) ...
        roi_title = QLabel("1. Área de Busca (ROI)")
        roi_title.setObjectName("sectionTitle")
        self.btn_definir_area = QPushButton("Definir Área na Tela")
        self.lbl_roi_coords = QLabel("Área não definida.")
        self.lbl_roi_coords.setStyleSheet("color: #a0a0b0;")
        config_layout.addWidget(roi_title)
        config_layout.addWidget(self.btn_definir_area)
        config_layout.addWidget(self.lbl_roi_coords)
        config_layout.addSpacing(20)
        alvos_title = QLabel("2. Alvos (O que procurar)")
        alvos_title.setObjectName("sectionTitle")
        self.list_alvos = QListWidget()
        self.list_alvos.setToolTip("Lista de imagens ou cores que o bot deve procurar.")
        alvos_buttons_layout = QHBoxLayout()
        self.btn_add_alvo_img = QPushButton("Add Imagem")
        self.btn_add_alvo_cor = QPushButton("Add Cor")
        self.btn_remover_alvo = QPushButton("Remover")
        alvos_buttons_layout.addWidget(self.btn_add_alvo_img)
        alvos_buttons_layout.addWidget(self.btn_add_alvo_cor)
        alvos_buttons_layout.addWidget(self.btn_remover_alvo)
        config_layout.addWidget(alvos_title)
        config_layout.addWidget(self.list_alvos)
        config_layout.addLayout(alvos_buttons_layout)
        config_layout.addStretch()

        # --- PAINEL DE REGRAS E EXECUÇÃO (DIREITA) ---
        rules_frame = QFrame()
        rules_frame.setObjectName("sectionFrame")
        rules_layout = QVBoxLayout(rules_frame)

        regras_title = QLabel("3. Regras (O que fazer)")
        regras_title.setObjectName("sectionTitle")
        self.list_regras = QListWidget()
        self.list_regras.setToolTip("QUANDO um alvo for encontrado, EXECUTE uma ação.")
        regras_buttons_layout = QHBoxLayout()
        self.btn_add_regra = QPushButton("Adicionar Nova Regra")
        self.btn_remover_regra = QPushButton("Remover Regra")
        regras_buttons_layout.addWidget(self.btn_add_regra)
        regras_buttons_layout.addWidget(self.btn_remover_regra)
        controle_title = QLabel("4. Controle do Bot")
        controle_title.setObjectName("sectionTitle")
        controle_buttons_layout = QHBoxLayout()
        self.btn_iniciar_bot = QPushButton("▶ Iniciar Bot")
        self.btn_iniciar_bot.setObjectName("startButton")
        self.btn_parar_bot = QPushButton("⏹ Parar Bot")
        controle_buttons_layout.addWidget(self.btn_iniciar_bot)
        controle_buttons_layout.addWidget(self.btn_parar_bot)
        rules_layout.addWidget(regras_title)
        rules_layout.addWidget(self.list_regras)
        rules_layout.addLayout(regras_buttons_layout)
        rules_layout.addSpacing(30)
        rules_layout.addWidget(controle_title)
        rules_layout.addLayout(controle_buttons_layout)

        main_layout.addWidget(config_frame)
        main_layout.addWidget(rules_frame, 1)

        root_layout = QVBoxLayout() # <--- MUDANÇA AQUI
        title = QLabel("Criador de Bots")
        title.setObjectName("pageTitle")
        root_layout.addWidget(title)
        root_layout.addLayout(main_layout)
        
        # Define o layout principal da página UMA ÚNICA VEZ
        self.setLayout(root_layout)