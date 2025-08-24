import customtkinter as ctk
import threading
import time
import json
import os
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
        entrada = entry_tecla.get()
        for char in entrada:
            teclas_selecionadas.append(char)

        for tecla, var in checkboxes_especiais.items():
            if var.get():
                teclas_selecionadas.append(teclas_especiais[tecla])

        if not teclas_selecionadas:
            label_status.configure(text="Status: Nenhuma tecla selecionada", text_color="#FF0000")
            executando = False
            return

        label_status.configure(text="Status: Executando Auto-Clicker", text_color="#127812")

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
    label_status.configure(text="Status: Executando Macro", text_color="#127812")

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

# === Deletar Macro e Configuração ===
def deletar_macro():
    global macro_gravado
    macro_gravado = []
    atualizar_lista_macro()
    label_status.configure(text="Status: Macro deletada", text_color="#FF6347")

def deletar_config():
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        label_status.configure(text="Status: Configuração deletada", text_color="#FF6347")
    else:
        label_status.configure(text="Status: Nenhum arquivo de configuração encontrado", text_color="#FF6347")

# === Captura de teclas para macro ===
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
        elif key == Key.f8:
            threading.Thread(target=executar_macro, daemon=True).start()
        elif key == Key.f9:
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

# === Interface com Scroll ===
app = ctk.CTk()
app.title("Auto Clicker + Macro Dashboard Profissional")
app.geometry("800x600")

frame_principal = ctk.CTkScrollableFrame(app, width=780, height=580)
frame_principal.pack(padx=10, pady=10, fill="both", expand=True)

# Título e instruções
titulo = ctk.CTkLabel(frame_principal, text="🚀 Auto Clicker Foda", font=("Arial", 22, "bold"))
titulo.pack(pady=10)

frame_instrucao = ctk.CTkFrame(frame_principal, fg_color="#2C2F33")
frame_instrucao.pack(padx=10, pady=5, fill="x")
ctk.CTkLabel(frame_instrucao, text="📖 Instruções de Uso:", font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
ctk.CTkLabel(frame_instrucao, text="""
1. Digite as teclas normais ou selecione as especiais.
2. Ajuste a velocidade e número de repetições.
3. Use os botões ou teclas F6/F7 para iniciar/parar Auto Clicker.
4. Use F8/F9 para executar/parar macros gravadas.
5. Salve sua configuração para reutilizar depois.
""", justify="left").pack(anchor="w", pady=5)

# --- Painel Auto Clicker ---
frame_autoclick = ctk.CTkFrame(frame_principal, fg_color="#3A3F44")
frame_autoclick.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_autoclick, text="Auto Clicker", font=("Arial", 16, "bold")).pack(pady=5)
entry_tecla = ctk.CTkEntry(frame_autoclick)
entry_tecla.pack(pady=2)
frame_check = ctk.CTkFrame(frame_autoclick)
frame_check.pack(pady=2)
checkboxes_especiais = {}
for tecla in teclas_especiais.keys():
    var = ctk.BooleanVar(value=False)
    chk = ctk.CTkCheckBox(frame_check, text=tecla, variable=var)
    chk.pack(anchor="center")
    checkboxes_especiais[tecla] = var

# --- Aqui continuam os sliders, botões, macro, configs etc. ---
# Velocidade, modo infinito, repetições
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
frame_macro = ctk.CTkFrame(frame_principal, fg_color="#3A3F44")
frame_macro.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_macro, text="Macro Recorder", font=("Arial", 16, "bold")).pack(pady=5)
frame_macro_btn = ctk.CTkFrame(frame_macro)
frame_macro_btn.pack(pady=5)
ctk.CTkButton(frame_macro_btn, text="⏺ Gravar Macro", command=iniciar_gravacao, fg_color="#8A2BE2", hover_color="#4B0082").grid(row=0, column=0, padx=5, pady=5)
ctk.CTkButton(frame_macro_btn, text="⏹ Parar Gravação", command=parar_gravacao, fg_color="#6A0DAD", hover_color="#301934").grid(row=0, column=1, padx=5, pady=5)
ctk.CTkButton(frame_macro_btn, text="▶ Executar Macro", command=lambda: threading.Thread(target=executar_macro, daemon=True).start(),
              fg_color="#32CD32", hover_color="#228B22").grid(row=0, column=2, padx=5, pady=5)
ctk.CTkButton(frame_macro_btn, text="❌ Deletar Macro", command=deletar_macro, fg_color="#FF6347", hover_color="#B22222").grid(row=0, column=3, padx=5, pady=5)

listbox_macros = ctk.CTkTextbox(frame_macro, height=150)
listbox_macros.pack(pady=5, fill="x")

# --- Painel Configurações ---
frame_config = ctk.CTkFrame(frame_principal, fg_color="#3A3F44")
frame_config.pack(pady=5, padx=10, fill="x")
ctk.CTkLabel(frame_config, text="Configurações", font=("Arial", 16, "bold")).pack(pady=5)
frame_config_btn = ctk.CTkFrame(frame_config)
frame_config_btn.pack(pady=5)
ctk.CTkButton(frame_config_btn, text="💾 Salvar Config", command=salvar_config, fg_color="#1E90FF", hover_color="#104E8B").grid(row=0, column=0, padx=5, pady=5)
ctk.CTkButton(frame_config_btn, text="📂 Carregar Config", command=carregar_config, fg_color="#FFA500", hover_color="#FF8C00").grid(row=0, column=1, padx=5, pady=5)
ctk.CTkButton(frame_config_btn, text="❌ Deletar Configuração", command=deletar_config, fg_color="#FF6347", hover_color="#B22222").grid(row=0, column=2, padx=5, pady=5)

# --- Status e contador ---
label_status = ctk.CTkLabel(frame_principal, text="Status: Pronto", font=("Arial", 14))
label_status.pack(pady=5)
label_contador = ctk.CTkLabel(frame_principal, text="Repetições executadas: 0")
label_contador.pack(pady=5)

# Carrega configuração inicial
carregar_config()

# Rodar interface
app.mainloop()
