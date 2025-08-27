"""
Este módulo contém as classes "Worker", responsáveis por executar as tarefas
de automação (autoclick, macros) em uma thread separada para não bloquear a UI.

Elas recebem as configurações necessárias em sua inicialização, executam um loop,
verificam constantemente por um evento de parada e comunicam o progresso e a
finalização através do Bus.
"""

import threading
import time
import random
import os

from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController, Button as MouseButton
from PIL import ImageGrab
import cv2
import numpy as np

# Importa o bus para comunicação
from app.core.bus import bus

# Import pywin32 de forma segura para evitar erros caso não esteja instalado
try:
    import win32gui
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


class BaseWorker(threading.Thread):
    """
    Classe base para todos os workers. Lida com a lógica comum de loop,
    repetições, delay, sinal de parada e comunicação de finalização.
    """
    def __init__(self, stop_event, reps, delay_min, delay_max, use_random):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        # Se reps for -1, consideramos como infinito
        self.reps = float('inf') if reps == -1 else reps
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.use_random = use_random

    def run(self):
        """O método principal da thread, que executa o loop de automação."""
        counter = 0
        try:
            while counter < self.reps:
                if self.stop_event.is_set():
                    break
                
                # O método que cada worker específico irá implementar
                self._execute_action()
                
                if self.stop_event.is_set():
                    break

                counter += 1
                bus.counter_updated.emit(counter)

                # Calcula o delay para a próxima iteração
                if self.use_random and self.delay_max > self.delay_min:
                    delay = random.uniform(self.delay_min, self.delay_max)
                else:
                    delay = self.delay_min
                
                if delay > 0:
                    time.sleep(delay)
        finally:
            # Garante que o sinal de finalização seja sempre emitido, não importa o que aconteça
            bus.execution_finished.emit()
            
    def _execute_action(self):
        """
        Método abstrato a ser implementado pelas classes filhas.
        Contém a lógica para uma única iteração da tarefa.
        """
        raise NotImplementedError("Cada worker deve implementar sua própria ação.")


class KeyboardAutoClickerWorker(BaseWorker):
    """Worker para o Auto Clicker de Teclado."""
    def __init__(self, keys_to_press, **kwargs):
        super().__init__(**kwargs)
        self.keys = keys_to_press
        self.keyboard = KeyboardController()

    def _execute_action(self):
        for key in self.keys:
            if self.stop_event.is_set():
                break
            self.keyboard.press(key)
            self.keyboard.release(key)
            time.sleep(0.01) # Pequeno delay entre as teclas dentro da mesma repetição


class MouseAutoClickerWorker(BaseWorker):
    """Worker para o Auto Clicker de Mouse."""
    def __init__(self, mouse_button, **kwargs):
        super().__init__(**kwargs)
        self.mouse_button = mouse_button
        self.mouse = MouseController()
    
    def _execute_action(self):
        self.mouse.click(self.mouse_button)


class KeyboardMacroWorker(BaseWorker):
    """Worker que executa uma macro de teclado gravada."""
    def __init__(self, macro_data, **kwargs):
        super().__init__(**kwargs)
        self.macro_data = macro_data
        self.keyboard = KeyboardController()

    def _execute_action(self):
        # Para macros, a "ação" é executar a sequência inteira de passos uma vez.
        for tecla, acao, tempo in self.macro_data:
            if self.stop_event.is_set():
                break
            
            # Pausa pelo tempo gravado entre as ações
            if tempo > 0:
                time.sleep(tempo)

            if self.stop_event.is_set():
                break

            if tecla == 'wait_pixel':
                target_x, target_y, target_color = acao
                timeout = 30
                start_time = time.time()
                bus.status_updated.emit(f"Aguardando pixel em ({target_x}, {target_y})...")
                pixel_found = False
                while time.time() - start_time < timeout:
                    if self.stop_event.is_set(): break
                    # Captura a tela e verifica a cor do pixel
                    if ImageGrab.grab().getpixel((target_x, target_y)) == tuple(target_color):
                        bus.status_updated.emit("Pixel encontrado!")
                        pixel_found = True
                        break
                    time.sleep(0.2)
                
                if not pixel_found:
                    bus.status_updated.emit("TIMEOUT: Pixel não encontrado. Parando.")
                    self.stop_event.set()
                continue # Pula para o próximo passo da macro

            # Executa a ação de pressionar ou soltar a tecla
            if acao == "press":
                self.keyboard.press(tecla)
            elif acao == "release":
                self.keyboard.release(tecla)


class MouseMacroWorker(BaseWorker):
    """Worker que executa uma macro de mouse gravada."""
    def __init__(self, macro_data, **kwargs):
        super().__init__(**kwargs)
        self.macro_data = macro_data
        self.mouse = MouseController()
        self.playback_origin = (0, 0) # Ponto (0,0) da tela por padrão

    def _execute_action(self):
        # Assim como na macro de teclado, a "ação" é a sequência completa de passos.
        for action_type, value, tempo in self.macro_data:
            if self.stop_event.is_set():
                break
            
            if tempo > 0:
                time.sleep(tempo)

            if self.stop_event.is_set(): break

            if action_type == 'set_relative_origin':
                self._handle_relative_origin(value)
            elif action_type in ("move", "position"):
                origin_x, origin_y = self.playback_origin
                rel_x, rel_y = value
                self.mouse.position = (origin_x + rel_x, origin_y + rel_y)
            elif action_type == "click":
                self.mouse.click(value)
            elif action_type == "scroll":
                self.mouse.scroll(0, value[1]) # value[1] é o dy (rolagem vertical)
            elif action_type == 'wait_pixel':
                self._handle_wait_pixel(value)
            elif action_type in ("wait_image", "click_image"):
                self._handle_image_action(action_type, value)
    
    def _handle_relative_origin(self, window_title):
        if not PYWIN32_AVAILABLE:
            bus.status_updated.emit("Erro: pywin32 não instalado para janela relativa.")
            self.stop_event.set()
            return

        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd == 0:
                bus.status_updated.emit(f"ERRO: Janela '{window_title}' não encontrada.")
                self.stop_event.set()
            else:
                rect = win32gui.GetWindowRect(hwnd)
                self.playback_origin = (rect[0], rect[1]) # (left, top)
                bus.status_updated.emit(f"Origem definida para '{window_title}'.")
        except Exception as e:
            bus.status_updated.emit(f"Erro na janela relativa: {e}")
            self.stop_event.set()

    def _handle_wait_pixel(self, value):
        target_x, target_y, target_color = value
        timeout = 30
        start_time = time.time()
        bus.status_updated.emit(f"Aguardando pixel em ({target_x}, {target_y})...")
        pixel_found = False
        while time.time() - start_time < timeout:
            if self.stop_event.is_set(): break
            if ImageGrab.grab().getpixel((target_x, target_y)) == tuple(target_color):
                bus.status_updated.emit("Pixel encontrado!")
                pixel_found = True
                break
            time.sleep(0.2)
        if not pixel_found:
            bus.status_updated.emit("TIMEOUT: Pixel não encontrado. Parando.")
            self.stop_event.set()
    
    def _handle_image_action(self, action_type, image_path):
        try:
            if not os.path.exists(image_path):
                bus.status_updated.emit(f"Erro: Imagem não encontrada em '{image_path}'")
                self.stop_event.set()
                return

            template = cv2.imread(image_path, 0) # Carrega em escala de cinza
            w, h = template.shape[::-1]
            timeout = 30
            start_time = time.time()
            found = False
            bus.status_updated.emit(f"Procurando por imagem '{os.path.basename(image_path)}'...")
            
            while time.time() - start_time < timeout:
                if self.stop_event.is_set(): break
                
                # Tira um screenshot e converte para o formato do OpenCV
                screen_pil = ImageGrab.grab()
                screen_np = np.array(screen_pil)
                screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_BGR2GRAY)
                
                # Procura pela imagem (template) na tela
                res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                # Se a similaridade for alta o suficiente...
                if max_val >= 0.8:
                    found = True
                    bus.status_updated.emit("Imagem encontrada!")
                    if action_type == "click_image":
                        # Calcula o centro da imagem encontrada
                        center_x = max_loc[0] + w // 2
                        center_y = max_loc[1] + h // 2
                        self.mouse.position = (center_x, center_y)
                        time.sleep(0.1) # Pequena pausa antes de clicar
                        self.mouse.click(MouseButton.left)
                    break # Sai do loop de procura
                time.sleep(0.5) # Pausa antes de tentar novamente
            
            if not found:
                bus.status_updated.emit(f"TIMEOUT: Imagem não encontrada ({os.path.basename(image_path)}).")
                self.stop_event.set()
        except Exception as e:
            bus.status_updated.emit(f"Erro no processamento de imagem: {e}")
            self.stop_event.set()