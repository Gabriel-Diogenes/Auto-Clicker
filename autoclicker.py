import customtkinter as ctk
import threading
import time
import json
from pynput.keyboard import Controller, Listener, Key

# === Configurações iniciais ===
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
keyboard = Controller()

# === Variáveis globais ===
executando = False
gravando = False
macro_gravado = []
contador = 0
thread_execucao = None
CONFIG_FILE = "macro_dashboard_moderno.json"

# Teclas especiais
teclas_especiais = {
    "Espaço": Key.space,
    "Enter": Key.enter,
    "Shift": Key.shift,
    "Ctrl": Key.ctrl,
    "Alt": Key.alt,
    "Tab": Key.tab,
    "Backspace": Key.backspace,
    "Esc": Key.esc
}

# === Funções de atualização ===
def atualizar_contador():
    label_contador.configure(text=f"Repetições executadas: {contador}")

def atualizar_lista_macro():
    listbox_macros.delete("0.0", ctk.END)
    for i, (t, a, d) in enumerate(macro_gravado):
        listbox_macros.insert(ctk.END, f"{i+1}: {t} - {a} - {d:.2f}s\n")

# === Auto Clicker ===
def iniciar_auto_click():
    global executando, thread_execucao, contador
    if not executando:
        executando = True
        contador = 0
        atualizar_contador()
        delay = float(velocidade_slider.get())

        teclas_selecionadas = []

        # Teclas normais
        entrada = entry_tecla.get()  # ex: "wasd"
        for char in entrada:
            teclas_selecionadas.append(char)

        # Teclas especiais
        for tecla, var in checkboxes_especiais.items():
            if var.get():
                teclas_selecionadas.append(teclas_especiais[tecla])

        if not teclas_selecionadas:
            label_status.configure(text="Status: Nenhuma tecla selecionada", text_color="#FF0000")
            executando = False
            return

        label_status.configure(text="Status: Executando Auto-Clicker", text_color="#00FF00")

        def loop_click():
            global contador
            if modo_infinito.get():
                while executando:
                    for t in teclas_selecionadas:
                        keyboard.press(t)
                    for t in reversed(teclas_selecionadas):
                        keyboard.release(t)
                    contador += 1
                    atualizar_contador()
                    time.sleep(delay)
            else:
                try:
                    repeticoes = int(entry_repeticoes.get())
                except:
                    repeticoes = 1
                for _ in range(repeticoes):
                    if not executando:
                        break
                    for t in teclas_selecionadas:
                        keyboard.press(t)
                    for t in reversed(teclas_selecionadas):
                        keyboard.release(t)
                    contador += 1
                    atualizar_contador()
                    time.sleep(delay)

            label_status.configure(text="Status: Pronto", text_color="white")

        thread_execucao = threading.Thread(target=loop_click, daemon=True)
        thread_execucao.start()

def parar():
    global executando, gravando
    executando = False
    gravando = False
    label_status.configure(text="Status: Parado", text_color="white")

# === Macro Recorder ===
def iniciar_gravacao():
    global gravando, macro_gravado
    macro_gravado = []
    gravando = True
    label_status.configure(text="Status: Gravando Macro", text_color="#800080")
    atualizar_lista_macro()

def parar_gravacao():
    global gravando
    gravando = False
    label_status.configure(text="Status: Macro Gravada", text_color="#800080")

def executar_macro():
    global executando, contador
    if not macro_gravado:
        label_status.configure(text="Status: Nenhuma macro gravada", text_color="#FF0000")
        return

    executando = True
    contador = 0
    atualizar_contador()
    delay_factor = float(velocidade_slider.get())
    label_status.configure(text="Status: Executando Macro", text_color="#00FF00")

    def loop_macro():
        global contador
        if modo_infinito.get():
            while executando:
                for tecla, acao, tempo in macro_gravado:
                    if not executando:
                        break
                    time.sleep(tempo * delay_factor)
                    if acao == "press":
                        keyboard.press(tecla)
                    elif acao == "release":
                        keyboard.release(tecla)
                contador += 1
                atualizar_contador()
        else:
            try:
                repeticoes = int(entry_repeticoes.get())
            except:
                repeticoes = 1
            for _ in range(repeticoes):
                if not executando:
                    break
                for tecla, acao, tempo in macro_gravado:
                    if not executando:
                        break
                    time.sleep(tempo * delay_factor)
                    if acao == "press":
                        keyboard.press(tecla)
                    elif acao == "release":
                        keyboard.release(tecla)
                contador += 1
                atualizar_contador()

        label_status.configure(text="Status: Pronto", text_color="white")

    threading.Thread(target=loop_macro, daemon=True).start()

# Captura de teclas para macro
def on_press_macro(key):
    global gravando
    if gravando:
        macro_gravado.append((key, "press", 0.05))
        atualizar_lista_macro()

def on_release_macro(key):
    global gravando
    if gravando:
        macro_gravado.append((key, "release", 0.05))
        atualizar_lista_macro()

# Listener global
def on_press_global(key):
    try:
        if key == Key.f6:
            threading.Thread(target=iniciar_auto_click, daemon=True).start()
        elif key == Key.f7:
            parar()
        elif key == Key.f8:  # F8 inicia a execução da macro
            threading.Thread(target=executar_macro, daemon=True).start()
        elif key == Key.f9:  # F9 para a execução da macro
            parar()
    except AttributeError:
        pass

listener = Listener(on_press=lambda k: [on_press_macro(k), on_press_global(k)],
                    on_release=on_release_macro)
listener.daemon = True
listener.start()

# === Salvar / Carregar Configuração ===
def salvar_config():
    config = {
        "tecla_normal": entry_tecla.get(),
        "teclas_especiais": {k: var.get() for k, var in checkboxes_especiais.items()},
        "velocidade": float(velocidade_slider.get()),
        "modo_infinito": modo_infinito.get(),
        "repeticoes": entry_repeticoes.get(),
        "macro": [(str(k), a, d) for k, a, d in macro_gravado]
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    label_status.configure(text="Status: Configuração salva!", text_color="#1E90FF")

def carregar_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        entry_tecla.delete(0, ctk.END)
        entry_tecla.insert(0, config.get("tecla_normal",""))
        for k, v in config.get("teclas_especiais", {}).items():
            if k in checkboxes_especiais:
                checkboxes_especiais[k].set(v)
        velocidade_slider.set(config.get("velocidade",0.5))
        modo_infinito.set(config.get("modo_infinito", True))
        entry_repeticoes.delete(0, ctk.END)
        entry_repeticoes.insert(0, config.get("repeticoes",""))
        global macro_gravado
        macro_gravado = []
        for k, a, d in config.get("macro", []):
            key_obj = getattr(Key, k.split(".")[-1]) if "Key." in k else k
            macro_gravado.append((key_obj, a, d))
        atualizar_lista_macro()
        label_status.configure(text="Status: Configuração carregada", text_color="#1E90FF")
    except FileNotFoundError:
        label_status.configure(text="Status: Nenhum arquivo encontrado", text_color="#FF0000")

# === Interface Moderna ===
app = ctk.CTk()
app.title("Auto Clicker + Macro Dashboard Profissional")
app.geometry("750x750")

titulo = ctk.CTkLabel(app, text="🚀 Auto Clicker Macro Dashboard", font=("Arial", 22, "bold"))
titulo.pack(pady=10)

# --- Painel Auto Clicker ---
frame_autoclick = ctk.CTkFrame(app, fg_color="#2E8B57")
frame_autoclick.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_autoclick, text="Auto Clicker", font=("Arial", 16, "bold")).pack(pady=5)

ctk.CTkLabel(frame_autoclick, text="Digite teclas normais:").pack(pady=2)
entry_tecla = ctk.CTkEntry(frame_autoclick)
entry_tecla.pack(pady=2)

ctk.CTkLabel(frame_autoclick, text="Selecione teclas especiais:").pack(pady=2)
frame_check = ctk.CTkFrame(frame_autoclick)
frame_check.pack(pady=2)
checkboxes_especiais = {}
for tecla in teclas_especiais.keys():
    var = ctk.BooleanVar(value=False)
    chk = ctk.CTkCheckBox(frame_check, text=tecla, variable=var)
    chk.pack(anchor="w")
    checkboxes_especiais[tecla] = var

ctk.CTkLabel(frame_autoclick, text="Velocidade (0.001s a 1s):").pack(pady=2)
velocidade_slider = ctk.CTkSlider(frame_autoclick, from_=0.001, to=1.0, number_of_steps=1000)
velocidade_slider.set(0.5)
velocidade_slider.pack(pady=2)
valor_label = ctk.CTkLabel(frame_autoclick, text="0.500s")
valor_label.pack(pady=2)
velocidade_slider.configure(command=lambda v: valor_label.configure(text=f"{float(v):.3f}s"))

modo_infinito = ctk.BooleanVar(value=True)
ctk.CTkCheckBox(frame_autoclick, text="Modo infinito", variable=modo_infinito).pack(pady=2)
ctk.CTkLabel(frame_autoclick, text="Número de repetições:").pack(pady=2)
entry_repeticoes = ctk.CTkEntry(frame_autoclick)
entry_repeticoes.pack(pady=2)

frame_btn = ctk.CTkFrame(frame_autoclick)
frame_btn.pack(pady=5)
ctk.CTkButton(frame_btn, text="▶ Auto Clicker", command=lambda: threading.Thread(target=iniciar_auto_click, daemon=True).start(),
              fg_color="#32CD32", hover_color="#228B22").grid(row=0, column=0, padx=5, pady=5)
ctk.CTkButton(frame_btn, text="⏹ Parar", command=parar, fg_color="#FF4500", hover_color="#B22222").grid(row=0, column=1, padx=5, pady=5)

# --- Painel Macro ---
frame_macro = ctk.CTkFrame(app, fg_color="#800080")
frame_macro.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_macro, text="Macro Recorder", font=("Arial", 16, "bold")).pack(pady=5)

frame_macro_btn = ctk.CTkFrame(frame_macro)
frame_macro_btn.pack(pady=5)
ctk.CTkButton(frame_macro_btn, text="⏺ Gravar Macro", command=iniciar_gravacao, fg_color="#8A2BE2", hover_color="#4B0082").grid(row=0, column=0, padx=5, pady=5)
ctk.CTkButton(frame_macro_btn, text="⏹ Parar Gravação", command=parar_gravacao, fg_color="#6A0DAD", hover_color="#301934").grid(row=0, column=1, padx=5, pady=5)
ctk.CTkButton(frame_macro_btn, text="▶ Executar Macro", command=lambda: threading.Thread(target=executar_macro, daemon=True).start(),
              fg_color="#32CD32", hover_color="#228B22").grid(row=0, column=2, padx=5, pady=5)

listbox_macros = ctk.CTkTextbox(frame_macro, height=150)
listbox_macros.pack(pady=5, fill="x")

# --- Painel Configurações ---
frame_config = ctk.CTkFrame(app, fg_color="#1E90FF")
frame_config.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_config, text="Configurações", font=("Arial", 16, "bold")).pack(pady=5)
ctk.CTkButton(frame_config, text="💾 Salvar Config", command=salvar_config, fg_color="#1E90FF", hover_color="#104E8B").pack(side="left", padx=5, pady=5)
ctk.CTkButton(frame_config, text="📂 Carregar Config", command=carregar_config, fg_color="#FFA500", hover_color="#FF8C00").pack(side="left", padx=5, pady=5)

# --- Status e contador ---
label_status = ctk.CTkLabel(app, text="Status: Pronto", font=("Arial", 14))
label_status.pack(pady=5)
label_contador = ctk.CTkLabel(app, text="Repetições executadas: 0")
label_contador.pack(pady=5)

# Carrega configuração inicial
carregar_config()

# Rodar interface
app.mainloop()
