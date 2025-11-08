# page_settings.py

from typing import Dict, Any
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFrame, QGridLayout,
    QScrollArea, QComboBox, QMessageBox # <--- ADICIONE QMessageBox AQUI
)
from pynput.keyboard import Listener as KeyboardListener, Key, KeyCode
from app.utils.constants import KEY_MAP_SAVE

# --- NOVA LISTA DE TECLAS RESTRITAS ---
# Estas teclas só serão permitidas se um modificador (Ctrl, Alt, Shift) for pressionado junto.
RESTRICTED_KEYS = {
    Key.space, Key.enter, Key.tab, Key.backspace
}

class PageSettings(QWidget):
    hotkey_updated = Signal(QLineEdit)

    def __init__(self):
        super().__init__()
        self.is_capturing = False
        self.current_hotkey_field = None
        self.hotkey_listener = None
        
        # --- NOVOS ATRIBUTOS PARA CAPTURA INTELIGENTE ---
        self._capture_modifiers = set() # Armazena os modificadores pressionados (Ctrl, Alt, Shift)
        self._captured_key_obj = None   # Armazena a tecla principal capturada
        
        self.build_ui()

    def build_ui(self):
        # ... (O seu método build_ui continua exatamente igual)
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
        self.input_iniciar_bot = QLineEdit(objectName="input_iniciar_bot")
        
        hotkey_inputs = [
            self.input_ac_teclado, self.input_ac_mouse, self.input_macro_teclado,
            self.input_macro_mouse, self.input_parar_tudo, self.input_gravar_macro_teclado,
            self.input_gravar_macro_mouse, self.input_parar_gravacao,
            self.input_iniciar_bot
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
        grid_hotkeys.addWidget(QLabel("Iniciar/Parar Bot:"), 9, 0)
        grid_hotkeys.addWidget(self.input_iniciar_bot, 9, 1)
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

    ### SUBSTITUA TODA A LÓGICA DE CAPTURA DE ATALHO POR ESTA VERSÃO ###
    def start_capture_hotkey(self, field: QLineEdit):
        """Inicia o modo de captura para um campo de atalho específico."""
        if self.is_capturing:
            return
        
        self.is_capturing = True
        self.current_hotkey_field = field
        self._capture_modifiers.clear()
        self._captured_key_obj = None

        self.lbl_info_hotkeys.setText("Capturando... Pressione a combinação de teclas (ESC para cancelar).")
        self.current_hotkey_field.setText("...")
        self.current_hotkey_field.setStyleSheet("color: #f0f0f0; background-color: #555;")

        self.hotkey_listener = KeyboardListener(
            on_press=self._on_capture_press, 
            on_release=self._on_capture_release
        )
        self.hotkey_listener.start()

    def _on_capture_press(self, key):
        """Callback chamado a cada tecla pressionada durante a captura."""
        modifier_map = {
            Key.ctrl_l: "Ctrl", Key.ctrl_r: "Ctrl",
            Key.shift_l: "Shift", Key.shift_r: "Shift",
            Key.alt_l: "Alt", Key.alt_r: "Alt"
        }
        
        if key in modifier_map:
            self._capture_modifiers.add(modifier_map[key])
            return

        # Tecla ESC sempre cancela
        if key == Key.esc:
            self.hotkey_listener.stop()
            self._finalize_capture(cancelled=True)
            return

        # Validação da tecla pressionada
        is_typing_key = isinstance(key, KeyCode) or key in RESTRICTED_KEYS
        
        if is_typing_key and not self._capture_modifiers:
            # REJEITA: É uma tecla de digitação sem modificadores
            QMessageBox.warning(self, "Atalho Inválido",
                                "Teclas de digitação (letras, números, espaço, etc.) "
                                "só podem ser usadas como atalhos em combinação com "
                                "Ctrl, Alt ou Shift.")
            self.hotkey_listener.stop()
            self._finalize_capture(cancelled=True)
            return

        # ACEITA: A tecla é válida. Para o listener e finaliza a captura.
        self._captured_key_obj = key
        self.hotkey_listener.stop()
        self._finalize_capture()
        return False # Redundante, mas boa prática

    def _on_capture_release(self, key):
        """Callback para limpar os modificadores quando são soltos."""
        modifier_map = {
            Key.ctrl_l: "Ctrl", Key.ctrl_r: "Ctrl",
            Key.shift_l: "Shift", Key.shift_r: "Shift",
            Key.alt_l: "Alt", Key.alt_r: "Alt"
        }
        if key in modifier_map and modifier_map[key] in self._capture_modifiers:
            self._capture_modifiers.remove(modifier_map[key])
    
    def _finalize_capture(self, cancelled=False):
        """
        Finaliza o processo de captura, atualiza a UI e emite o sinal.
        Chamado tanto em caso de sucesso quanto de cancelamento.
        """
        field_to_update = self.current_hotkey_field
        key_str = "" # String final a ser exibida

        if cancelled:
            # Se cancelado, não precisamos de lógica complexa, o on_hotkey_changed tratará o campo vazio.
            field_to_update.setText("")
        else:
            # Constrói a string do atalho (ex: "Ctrl + T")
            main_key_str = self._key_to_str(self._captured_key_obj)
            if self._capture_modifiers:
                # Ordena para consistência (ex: Ctrl + Shift + T e não Shift + Ctrl + T)
                mods = sorted(list(self._capture_modifiers))
                key_str = " + ".join(mods) + " + " + main_key_str
            else:
                key_str = main_key_str
            field_to_update.setText(key_str)

        # Restaura a UI
        self.lbl_info_hotkeys.setText("Clique no campo para capturar uma tecla de atalho.")
        field_to_update.setStyleSheet("")
        
        # Emite o sinal para a MainWindow
        self.hotkey_updated.emit(field_to_update)
        
        # Limpa o estado de captura
        self.is_capturing = False
        self.current_hotkey_field = None
        self._capture_modifiers.clear()
        self._captured_key_obj = None

    def _key_to_str(self, key):
        """Converte um objeto de tecla do pynput para uma string legível."""
        if isinstance(key, Key):
            return KEY_MAP_SAVE.get(key, f"Key.{key.name}")
        if isinstance(key, KeyCode):
            return key.char if key.char is not None else str(key)
        return str(key)
        
    def refresh_profiles(self, profiles: Dict[str, Any]):
        # ... (O seu método refresh_profiles continua exatamente igual)
        current_selection = self.combo_profiles.currentText()
        self.combo_profiles.clear()
        names = sorted(profiles.keys())
        self.combo_profiles.addItems(names)
        if current_selection in names:
            self.combo_profiles.setCurrentText(current_selection)