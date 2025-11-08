"""
Este módulo contém o GlobalListener, que é responsável por capturar
todos os eventos de teclado e mouse do sistema operacional usando pynput.
Ele roda em sua própria thread e comunica com o resto da aplicação
através de sinais Qt, nunca interagindo diretamente com a UI.
"""

from typing import Dict
from PySide6.QtCore import QObject, Signal

from pynput.keyboard import Listener as KeyboardListener, Key, KeyCode
from pynput.mouse import Listener as MouseListener, Controller as MouseController

from app.utils.constants import KEY_MAP_SAVE


class GlobalListener(QObject):
    """
    Objeto que roda em uma thread separada para escutar todos os inputs globais.
    Ele NUNCA interage com a UI diretamente, apenas emite sinais.
    """
    hotkey_pressed = Signal(str)
    key_pressed = Signal(object)
    key_released = Signal(object)
    mouse_event = Signal(str, tuple)

    def __init__(self, hotkeys: Dict[str, str]):
        super().__init__()
        self.hotkeys = hotkeys
        self.keyboard_listener = None
        self.mouse_listener = None
        self.ctrl_pressed = False
        self.shift_pressed = False
        
        ### CORREÇÃO AQUI ###
        # O nome do atributo foi corrigido de 'self.paused' para 'self.pause_requests'
        # e inicializado como um contador (0).
        self.pause_requests = 0

    def set_paused(self, paused_status: bool):
        """
        Gerencia os pedidos de pausa. O listener só funciona se o contador for 0.
        """
        if paused_status:
            self.pause_requests += 1
        else:
            self.pause_requests = max(0, self.pause_requests - 1)

    def run(self):
        """Inicia os listeners do pynput. Este método bloqueia até que os listeners parem."""
        # Adicionamos o parâmetro 'win32_event_filter' para detectar teclas injetadas
        self.keyboard_listener = KeyboardListener(on_press=self._on_press, on_release=self._on_release, win32_event_filter=self._win32_event_filter)
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

    def _win32_event_filter(self, msg, data):
        # Se a flag LLKHF_INJECTED estiver presente, a tecla foi simulada por um programa.
        # Não passamos o evento para o on_press/on_release para evitar loops.
        if data.flags & 0x10: # LLKHF_INJECTED
            return False # Bloqueia o evento
        return True # Permite que o evento continue

    # --- Callbacks do Pynput (Apenas emitem sinais) ---
    def _on_press(self, key):
        # A verificação de tecla injetada agora é feita pelo _win32_event_filter,
        # então o código aqui fica mais limpo.
        if self.pause_requests > 0:
            return
        
        if key in (Key.ctrl_l, Key.ctrl_r): self.ctrl_pressed = True
        if key in (Key.shift_l, Key.shift_r): self.shift_pressed = True
        
        key_name = self._key_to_str(key)
        for hotkey_name, hotkey_value in self.hotkeys.items():
            if key_name == hotkey_value:
                self.hotkey_pressed.emit(hotkey_name)
                return
        
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