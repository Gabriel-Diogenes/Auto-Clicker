"""
Módulo para a PageSettings, a página da UI onde o usuário gerencia
perfis, hotkeys globais e outras configurações da aplicação.
"""
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFrame, QGridLayout,
    QScrollArea, QComboBox
)
from pynput.keyboard import Listener as KeyboardListener


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
        
        # --- Gerenciar Perfis ---
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
        
        # --- Importar / Exportar ---
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
        
        # --- Atalhos Globais ---
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
        
        hotkey_inputs = [
            self.input_ac_teclado, self.input_ac_mouse, self.input_macro_teclado,
            self.input_macro_mouse, self.input_parar_tudo, self.input_gravar_macro_teclado,
            self.input_gravar_macro_mouse, self.input_parar_gravacao
        ]
        for inp in hotkey_inputs:
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

        # --- Outras Configurações ---
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
        
    def refresh_profiles(self, profiles: Dict[str, Any]):
        current_selection = self.combo_profiles.currentText()
        self.combo_profiles.clear()
        names = sorted(profiles.keys())
        self.combo_profiles.addItems(names)
        # Tenta manter a seleção atual se ela ainda existir
        if current_selection in names:
            self.combo_profiles.setCurrentText(current_selection)