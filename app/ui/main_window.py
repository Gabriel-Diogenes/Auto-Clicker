import sys
import os
import json
import threading
import time
from typing import Any, List, Dict

# Tenta importar bibliotecas opcionais
try:
    import qtawesome as qta
except ImportError:
    qta = None
from pynput.keyboard import Key, KeyCode, Listener as KeyboardListener
from pynput.mouse import Button as MouseButton

# Imports do PySide6
from PySide6.QtCore import Qt, QSize, QUrl, QThread, QPropertyAnimation, QTimer
from PySide6.QtGui import QIcon, QCursor, QAction, QPixmap, QPainter, QColor, QScreen
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QMessageBox, QFileDialog, QProgressBar, QSizePolicy,
    QGraphicsOpacityEffect, QMenu, QSystemTrayIcon, QInputDialog, QLineEdit
)
from PIL import ImageGrab

# --- Imports da nossa arquitetura ---
from app.core.app_state import AppState
from app.core.bus import bus
from app.core.global_listener import GlobalListener
from app.core.workers import (
    KeyboardAutoClickerWorker, MouseAutoClickerWorker,
    KeyboardMacroWorker, MouseMacroWorker
)

from app.ui.pages.page_autoclickers import PageAutoClickers
from app.ui.pages.page_macros import PageMacros
from app.ui.pages.page_settings import PageSettings
from app.ui.pages.page_about import PageAbout
from app.ui.widgets.overlay_widget import OverlayWidget
from app.ui.widgets.capture_widget import CaptureWidget

from app.utils import constants, profile_manager


# ====== Janela principal (integra tudo)
class MainWindow(QMainWindow):
    # --- PROPRIEDADES PRINCIPAIS ---
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Clicker + Macro Dashboard (v3 - Refatorado)")
        self.setMinimumSize(QSize(1200, 700))
        self.resize(1200, 700)
        self._profiles = {}
        try:
            self.setWindowIcon(QIcon("app/assets/app.ico"))
        except Exception:
            pass
        
        # --- ARQUITETURA REFEITA: INICIALIZAÇÃO ---
        self.app_state = AppState.IDLE
        self.hotkeys = {}
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.macro_keyboard_data: List[tuple] = []
        self.macro_mouse_data: List[tuple] = []
        self.ultimo_tempo = 0.0
        self._profiles = {}
        self.macro_keyboard_data: List[tuple] = []
        self.macro_mouse_data: List[tuple] = []
        self.ultimo_tempo = 0.0
        self._profiles = {}

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
                self.macro_keyboard_data, start, end, row
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
                self.macro_mouse_data, start, end, row, is_mouse=True
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
        self.start_sound.setSource(QUrl.fromLocalFile("app/assets/start.wav"))
        self.start_sound.setVolume(0.8)
        self.stop_sound = QSoundEffect()
        self.stop_sound.setSource(QUrl.fromLocalFile("app/assets/stop.wav"))
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
        self.macro_keyboard_data
        if self.app_state != AppState.RECORDING_KEYBOARD:
            return
        if key == Key.esc:
            self.stop_record_teclado()
            return
        agora = time.time()
        atraso = agora - self.ultimo_tempo if self.ultimo_tempo != 0 else 0.0
        self.macro_keyboard_data.append((key, "press", atraso))
        self.ultimo_tempo = agora
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)

    def on_key_released_for_macro(self, key):
        self.macro_keyboard_data
        if self.app_state != AppState.RECORDING_KEYBOARD:
            return
        if key == Key.esc: return
        agora = time.time()
        atraso = agora - self.ultimo_tempo
        self.macro_keyboard_data.append((key, "release", atraso))
        self.ultimo_tempo = agora
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
    
    def on_mouse_event_for_macro(self, event_type, data):
        self.macro_mouse_data
        
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
             self.macro_mouse_data.append(("position", (x, y), 0.0))
             bus.macro_mouse_updated.emit(self.macro_mouse_data)
             bus.status_updated.emit(f"Posição ({x}, {y}) capturada.")
             return

        # Lógica de gravação de macro
        if self.app_state != AppState.RECORDING_MOUSE:
            return
        
        agora = time.time()
        atraso = agora - self.ultimo_tempo if self.ultimo_tempo != 0 else 0.0
        
        if event_type == "move":
            x, y = data
            if self.recording_origin:
                origin_x, origin_y = self.recording_origin
                record_x, record_y = x - origin_x, y - origin_y
            else:
                record_x, record_y = x, y
            self.macro_mouse_data.append(("move", (record_x, record_y), atraso))
        
        elif event_type == "click":
            x, y, button = data
            self.macro_mouse_data.append(("click", button, atraso))

        elif event_type == "scroll":
            x, y, dx, dy = data
            direction = "para cima" if dy > 0 else "para baixo"
            self.macro_mouse_data.append(("scroll", (direction, dy), atraso))

        self.ultimo_tempo = agora
        bus.macro_mouse_updated.emit(self.macro_mouse_data)

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
        bus.status_updated.emit("Atalhos padrão carregados.")

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
            icon = QIcon("app/assets/app.ico")
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
        self.is_capturing_pixel = True; self.hide(); bus.status_updated.emit("MODO DE CAPTURA (MOUSE): Clique no pixel desejado...")

    def start_pixel_capture_teclado(self):
        self.is_capturing_pixel_teclado = True; self.hide(); bus.status_updated.emit("MODO DE CAPTURA (TECLADO): Clique no pixel desejado...")
        
    def start_image_capture(self):
        self.hide()
        self.capture_widget = CaptureWidget()
        self.capture_widget.area_selecionada.connect(self.add_image_macro_step)
        QTimer.singleShot(50, self.capture_widget.show)
        bus.status_updated.emit("MODO DE CAPTURA: Clique e arraste para selecionar uma área.")

    def add_image_macro_step(self, rect_coords):
        """Captura a imagem da área selecionada e a adiciona na macro."""
        x_log, y_log, w_log, h_log = rect_coords

        if w_log == 0 or h_log == 0:
            self.showNormal()
            self.activateWindow()
            bus.status_updated.emit("Captura cancelada (área inválida).")
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
            self.macro_mouse_data.append((action_type, image_path, 0.0))
            bus.macro_mouse_updated.emit(self.macro_mouse_data)
            bus.status_updated.emit(f"Passo '{item}' adicionado com a imagem '{os.path.basename(image_path)}'.")

        self.showNormal()
        self.activateWindow()

    def add_pixel_wait_step(self, x, y, is_keyboard_macro: bool = False):
        self.macro_keyboard_data
        pixel_color = ImageGrab.grab().getpixel((x, y))
        if is_keyboard_macro:
            self.macro_keyboard_data.append(('wait_pixel', (x, y, pixel_color), 0.0))
            bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
            self.is_capturing_pixel_teclado = False
        else:
            self.macro_mouse_data.append(('wait_pixel', (x, y, pixel_color), 0.0))
            bus.macro_mouse_updated.emit(self.macro_mouse_data)
            self.is_capturing_pixel = False
        self.showNormal(); self.activateWindow(); bus.status_updated.emit(f"Passo 'Aguardar por Pixel' adicionado.")
        
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
        
        bus.counter_updated.emit(0)  # Corrigido de set_counter para bus.emit
        self.stop_event.clear()
        self.app_state = AppState.EXECUTING
        self.play_start_sound()

    def start_auto_click_teclado(self):
        if self.app_state != AppState.IDLE: return
        keys = self.page_auto.get_selected_keys()
        if not keys:
            bus.status_updated.emit("Nenhuma tecla selecionada.")
            return
        
        self._prepare_execution()
        bus.status_updated.emit("Executando Auto Clicker (Teclado)…")
        self.show_overlay_message("Executando Auto Clicker...")
        
        # A MÁGICA ACONTECE AQUI:
        # Em vez de uma função 'worker', nós instanciamos a classe de worker!
        self.worker_thread = KeyboardAutoClickerWorker(
            keys_to_press=keys,
            stop_event=self.stop_event,
            reps=-1 if self.page_auto.is_infinite() else self.page_auto.get_reps(),
            delay_min=self.page_auto.get_delay(),
            delay_max=self.page_auto.spin_speed_max.value(),
            use_random=self.page_auto.chk_random_delay.isChecked()
        )
        self.worker_thread.start()

    def start_auto_click_mouse(self):
        if self.app_state != AppState.IDLE: return
        self._prepare_execution()
        bus.status_updated.emit("Executando Auto Clicker (Mouse)…")
        self.show_overlay_message("Executando Auto Clicker...")
        
        self.worker_thread = MouseAutoClickerWorker(
            mouse_button=self.page_auto.get_mouse_button(),
            stop_event=self.stop_event,
            reps=-1 if self.page_auto.is_infinite() else self.page_auto.get_reps(),
            delay_min=self.page_auto.get_delay(),
            delay_max=self.page_auto.spin_speed_max.value(),
            use_random=self.page_auto.chk_random_delay.isChecked()
        )
        self.worker_thread.start()
    
    def stop_all(self):
        if self.app_state != AppState.IDLE:
            bus.status_updated.emit("Parando...")
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
        bus.status_updated.emit("Pronto")

    def start_record_teclado(self):
        if self.app_state != AppState.IDLE: return
        self.app_state = AppState.RECORDING_KEYBOARD
        self.play_start_sound()
        self.ultimo_tempo = time.time()
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
        self.show_overlay_message("Gravando Macro de Teclado...")
        bus.status_updated.emit("Gravando Macro (Teclado)...")
        
    def stop_record_teclado(self):
        if self.app_state != AppState.RECORDING_KEYBOARD: return
        self.app_state = AppState.IDLE # Transição de estado
        bus.execution_finished.emit() # Usa o mesmo sinal para limpar a UI
        bus.status_updated.emit("Gravação de Teclado encerrada.")
        
    def start_macro_teclado(self):
        if self.app_state != AppState.IDLE: return
        if not self.macro_keyboard_data:
            bus.status_updated.emit("Nenhuma macro de teclado gravada.")
            return
            
        self._prepare_execution(is_macro=True)
        bus.status_updated.emit("Executando Macro (Teclado)…")
        self.show_overlay_message("Executando Macro de Teclado...")
        
        self.worker_thread = KeyboardMacroWorker(
            macro_data=self.macro_keyboard_data,
            stop_event=self.stop_event,
            reps=-1 if self.page_macro.is_infinite() else self.page_macro.get_reps(),
            delay_min=self.page_macro.get_delay(),
            delay_max=self.page_macro.spin_macro_speed_max.value(),
            use_random=self.page_macro.chk_macro_random_delay.isChecked()
        )
        self.worker_thread.start()

    def clear_current_macro_teclado(self):
        self.macro_keyboard_data.clear(); bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
        bus.status_updated.emit("Macro de teclado atual limpa.")
    
    def delete_keyboard_macro_step(self):
        current_row = self.page_macro.list_macro_teclado.currentRow()
        if current_row == -1: setbus.status_updated.emit_status("Nenhum passo selecionado para deletar."); return
        del self.macro_keyboard_data[current_row]
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
        bus.status_updated.emit(f"Passo {current_row + 1} deletado.")

    def duplicate_keyboard_macro_step(self):
        current_row = self.page_macro.list_macro_teclado.currentRow()
        if current_row == -1: bus.status_updated.emit("Nenhum passo selecionado para duplicar."); return
        item_to_duplicate = self.macro_keyboard_data[current_row]
        self.macro_keyboard_data.insert(current_row + 1, item_to_duplicate)
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)
        bus.status_updated.emit(f"Passo {current_row + 1} duplicado.")

    def _edit_step_delay(self, macro_list, row, is_mouse=False):
        action_type, value, old_delay = macro_list[row]
        new_delay, ok = QInputDialog.getDouble(self, "Editar Delay", "Novo delay (em segundos):", old_delay, 0, 100, 4)
        if ok and new_delay >= 0:
            macro_list[row] = (action_type, value, new_delay)
            if is_mouse: bus.macro_mouse_updated.emit(macro_list)
            else: bus.macro_keyboard_updated.emit(macro_list)
            bus.status_updated.emit(f"Delay do passo {row + 1} alterado para {new_delay:.4f}s.")

    def edit_keyboard_macro_step(self, item):
        row = self.page_macro.list_macro_teclado.row(item)
        if row == -1: return
        key_obj, action, old_delay = self.macro_keyboard_data[row]
        if isinstance(key_obj, (Key, KeyCode)): self._edit_step_delay(self.macro_keyboard_data, row, is_mouse=False)
        else: QMessageBox.information(self, "Edição Não Suportada", "A edição de detalhes para este tipo de passo ainda não foi implementada.")

    def edit_mouse_macro_step(self, item):
        row = self.page_macro.list_macro_mouse.row(item);
        if row == -1: return
        action_type, value, delay = self.macro_mouse_data[row]
        if action_type in ("move", "position"): self._edit_mouse_coords(row, (action_type, value, delay))
        elif action_type == "click": self._edit_mouse_click(row, (action_type, value, delay))
        elif action_type == "scroll": self._edit_mouse_scroll(row, (action_type, value, delay))
        elif action_type in ("wait_image", "click_image"): self._edit_step_delay(self.macro_mouse_data, row, is_mouse=True)
        else: QMessageBox.information(self, "Edição Não Suportada", "A edição deste tipo de passo não é suportada.")

    def _edit_mouse_coords(self, row, data):
        action_type, (old_x, old_y), old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Movimento", "O que você deseja editar?", ["Coordenadas", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(self.macro_mouse_data, row, is_mouse=True)
        elif choice == "Coordenadas":
            new_coords_str, ok = QInputDialog.getText(self, "Editar Coordenadas", "Novas coordenadas (x, y):", QLineEdit.EchoMode.Normal, f"{old_x}, {old_y}")
            if ok and new_coords_str:
                try:
                    parts = new_coords_str.split(','); new_x = int(parts[0].strip()); new_y = int(parts[1].strip())
                    self.macro_mouse_data[row] = (action_type, (new_x, new_y), old_delay)
                    bus.macro_mouse_updated.emit(self.macro_mouse_data); bus.status_updated.emit(f"Coordenadas do passo {row + 1} alteradas.")
                except: QMessageBox.warning(self, "Erro de Formato", "Insira no formato 'x, y'")

    def _edit_mouse_click(self, row, data):
        action_type, old_button, old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Clique", "O que você deseja editar?", ["Botão do Mouse", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(self.macro_mouse_data, row, is_mouse=True)
        elif choice == "Botão do Mouse":
            items = ["Esquerdo", "Direito", "Meio"]; current_item = "Esquerdo"
            if old_button == MouseButton.right: current_item = "Direito"
            if old_button == MouseButton.middle: current_item = "Meio"
            new_button_str, ok = QInputDialog.getItem(self, "Editar Botão", "Selecione o novo botão:", items, items.index(current_item), False)
            if ok and new_button_str:
                button_map = {"Esquerdo": MouseButton.left, "Direito": MouseButton.right, "Meio": MouseButton.middle}
                self.macro_mouse_data[row] = (action_type, button_map[new_button_str], old_delay)
                bus.macro_mouse_updated.emit(self.macro_mouse_data); bus.status_updated.emit(f"Botão do passo {row + 1} alterado.")

    def _edit_mouse_scroll(self, row, data):
        action_type, (old_direction, old_dy), old_delay = data
        choice, ok = QInputDialog.getItem(self, "Editar Passo de Rolagem", "O que você deseja editar?", ["Direção/Força", "Delay"], 0, False)
        if not ok: return
        if choice == "Delay": self._edit_step_delay(self.macro_mouse_data, row, is_mouse=True)
        elif choice == "Direção/Força":
            new_dy, ok = QInputDialog.getInt(self, "Editar Força da Rolagem", "Força (positivo=cima, negativo=baixo):", old_dy, -100, 100, 1)
            if ok:
                new_direction = "para cima" if new_dy > 0 else "para baixo"
                self.macro_mouse_data[row] = (action_type, (new_direction, new_dy), old_delay)
                bus.macro_mouse_updated.emit(self.macro_mouse_data); bus.status_updated.emit(f"Rolagem do passo {row + 1} alterada.")

    def handle_macro_reorder(self, macro_list: list, source_start: int, source_end: int, dest_row: int, is_mouse: bool = False):
        count = source_end - source_start + 1
        if source_start <= dest_row <= source_end + 1: return
        moved_items = [macro_list[i] for i in range(source_start, source_end + 1)]
        for i in sorted(range(source_start, source_end + 1), reverse=True): del macro_list[i]
        if dest_row > source_start: dest_row -= count
        for i, item in enumerate(moved_items): macro_list.insert(dest_row + i, item)
        if is_mouse: bus.macro_mouse_updated.emit(macro_list)
        else: bus.macro_keyboard_updated.emit(macro_list)
        bus.status_updated.emit("Ordem da macro atualizada.")

    def start_record_mouse(self):
        if self.app_state != AppState.IDLE: return
        self.app_state = AppState.RECORDING_MOUSE
        self.play_start_sound()
        
        self.recording_origin = None
        if self.page_macro.chk_relative_mouse.isChecked():
            if not PYWIN32_AVAILABLE: bus.status_updated.emit("ERRO: pywin32 não instalado.")
            else:
                try:
                    hwnd = win32gui.GetForegroundWindow(); title = win32gui.GetWindowText(hwnd); rect = win32gui.GetWindowRect(hwnd)
                    if not title: bus.status_updated.emit("AVISO: Janela sem título. Gravando em modo absoluto.")
                    else:
                        self.macro_mouse_data.append(('set_relative_origin', title, 0.0))
                        self.recording_origin = (rect[0], rect[1])
                        bus.status_updated.emit(f"Gravação relativa à janela '{title}' iniciada.")
                except Exception as e: bus.status_updated.emit(f"Erro ao obter janela: {e}. Gravando em modo absoluto.")

        self.ultimo_tempo = time.time()
        bus.macro_mouse_updated.emit(self.macro_mouse_data)
        self.show_overlay_message("Gravando Macro de Mouse...")
        if not self.recording_origin: bus.status_updated.emit("Gravando Macro (Mouse)...")

    def stop_record_mouse(self):
        if self.app_state != AppState.RECORDING_MOUSE: return
        self.app_state = AppState.IDLE
        bus.execution_finished.emit()
        bus.status_updated.emit("Gravação de Mouse encerrada.")

    def start_macro_mouse(self):
        if self.app_state != AppState.IDLE: return
        if not self.macro_mouse_data:
            bus.status_updated.emit("Nenhuma macro de mouse gravada.")
            return

        self._prepare_execution(is_macro=True)
        bus.status_updated.emit("Executando Macro (Mouse)…")
        self.show_overlay_message("Executando Macro de Mouse...")
        
        self.worker_thread = MouseMacroWorker(
            macro_data=self.macro_mouse_data,
            stop_event=self.stop_event,
            reps=-1 if self.page_macro.is_infinite() else self.page_macro.get_reps(),
            delay_min=self.page_macro.get_delay(),
            delay_max=self.page_macro.spin_macro_speed_max.value(),
            use_random=self.page_macro.chk_macro_random_delay.isChecked()
        )
        self.worker_thread.start()
        
    def clear_current_macro_mouse(self):
        self.macro_mouse_data.clear(); bus.macro_mouse_updated.emit(self.macro_mouse_data)
        bus.status_updated.emit("Macro de mouse atual limpa.")

    def delete_mouse_macro_step(self):
        current_row = self.page_macro.list_macro_mouse.currentRow()
        if current_row == -1: bus.status_updated.emit("Nenhum passo selecionado para deletar."); return
        del self.macro_mouse_data[current_row]
        bus.macro_mouse_updated.emit(self.macro_mouse_data)
        bus.status_updated.emit(f"Passo {current_row + 1} da macro de mouse deletado.")
        
    def duplicate_mouse_macro_step(self):
        current_row = self.page_macro.list_macro_mouse.currentRow()
        if current_row == -1: bus.status_updated.emit("Nenhum passo selecionado para duplicar."); return
        item_to_duplicate = self.macro_mouse_data[current_row]
        self.macro_mouse_data.insert(current_row + 1, item_to_duplicate)
        bus.macro_mouse_updated.emit(self.macro_mouse_data)
        bus.status_updated.emit(f"Passo {current_row + 1} da macro de mouse duplicado.")
    
    def _key_to_str(self, key_obj: Any) -> str:
        if isinstance(key_obj, Key): return constants.KEY_MAP_SAVE.get(key_obj, f"Key.{key_obj.name}")
        if isinstance(key_obj, KeyCode): return key_obj.char if key_obj.char is not None else str(key_obj)
        return str(key_obj)

    def _str_to_key(self, key_str: str) -> Any:
        if not isinstance(key_str, str): return key_str # Já é um objeto de tecla
        if key_str.startswith("Key."):
            try:
                if mapped_key := constants.KEY_MAP_LOAD.get(key_str): return mapped_key
                return getattr(Key, key_str.split(".")[-1].lower())
            except AttributeError: return None
        try: return KeyCode.from_char(key_str)
        except Exception: return None
    
    def _mouse_action_to_str(self, action):
        return str(action) if isinstance(action, MouseButton) else action
        
    def get_all_settings_as_dict(self) -> Dict[str, Any]:
        return {
            "autoclicker": self.page_auto.to_config(),
            "macro_keyboard": [(self._key_to_str(k), a, d) if k != 'wait_pixel' else (k, a, d) for k, a, d in self.macro_keyboard_data],
            "macro_mouse": [(a, self._mouse_action_to_str(v), d) for a, v, d in self.macro_mouse_data],
            "macro_settings": {
                "infinite": self.page_macro.is_infinite(), "reps": self.page_macro.get_reps(),
                "delay": self.page_macro.get_delay(), "random_delay": self.page_macro.chk_macro_random_delay.isChecked(),
                "random_delay_max": self.page_macro.spin_macro_speed_max.value()
            },
            "hotkeys": self.hotkeys,
            "enable_sounds": self.page_settings.chk_enable_sounds.isChecked()
        }

    def set_all_settings_from_dict(self, data: Dict[str, Any]):
        self.page_auto.set_from_config(data.get("autoclicker", {}))
        
        self.macro_keyboard_data = []
        for k_str, a, d in data.get("macro_keyboard", []):
            if k_str == 'wait_pixel': self.macro_keyboard_data.append((k_str, a, d))
            else: k_obj = self._str_to_key(k_str); self.macro_keyboard_data.append((k_obj, a, d))
        bus.macro_keyboard_updated.emit(self.macro_keyboard_data)

        self.macro_mouse_data = []
        for a, v, d in data.get("macro_mouse", []):
            val = v
            if a == "click":
                try: val = getattr(MouseButton, v.split('.')[-1])
                except Exception: pass
            self.macro_mouse_data.append((a, val, d))
        bus.macro_mouse_updated.emit(self.macro_mouse_data)

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
        if os.path.exists(constants.PROFILES_FILE):
            try:
                with open(constants.PROFILES_FILE, "r", encoding="utf-8") as f: self._profiles = json.load(f)
            except: self._profiles = {}
        else: self._profiles = {}
        self.page_settings.refresh_profiles(self._profiles)

    def save_profile(self):
        name = self.page_settings.input_profile_name.text().strip()
        if not name: QMessageBox.warning(self, "Salvar Perfil", "Informe um nome."); return
        self._profiles[name] = self.get_all_settings_as_dict()
        try:
            with open(constants.PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            bus.status_updated.emit(f"Perfil '{name}' salvo."); self.page_settings.refresh_profiles(self._profiles)
        except Exception as e: QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar: {e}")

    def load_profile(self):
        name = self.page_settings.combo_profiles.currentText()
        if not name or name not in self._profiles: bus.status_updated.emit("Nenhum perfil válido selecionado."); return
        self.set_all_settings_from_dict(self._profiles[name])
        bus.status_updated.emit(f"Perfil '{name}' carregado.")

    def delete_profile(self):
        name = self.page_settings.combo_profiles.currentText()
        if not name or name not in self._profiles: bus.status_updated.emit("Nenhum perfil para excluir."); return
        reply = QMessageBox.question(self, "Excluir Perfil", f"Tem certeza que deseja excluir '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self._profiles[name]
            try:
                with open(constants.PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
                bus.status_updated.emit(f"Perfil '{name}' excluído."); self.page_settings.refresh_profiles(self._profiles)
            except Exception as e: QMessageBox.critical(self, "Erro ao Excluir", f"Não foi possível salvar: {e}")

    def export_profiles(self):
        if not self._profiles: QMessageBox.information(self, "Exportar", "Não há perfis para exportar."); return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Perfis", "perfis.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            bus.status_updated.emit(f"Perfis exportados para: {path}")
        except Exception as e: QMessageBox.critical(self, "Erro de Exportação", f"Erro: {e}")

    def import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Perfis", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f: data_from_file = json.load(f)
            if not isinstance(data_from_file, dict): raise ValueError("Estrutura inválida.")
            self._profiles.update(data_from_file)
            with open(constants.PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(self._profiles, f, ensure_ascii=False, indent=4)
            self.page_settings.refresh_profiles(self._profiles); bus.status_updated.emit("Perfis importados.")
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