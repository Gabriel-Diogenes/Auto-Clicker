import customtkinter as ctk
import threading
import time
import json
from pynput.keyboard import Controller, Listener, Key

# Inicializa tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Controlador do teclado
keyboard = Controller()

# Variáveis globais
executando = False
thread_autoclick = None
contador = 0

# Dicionário de teclas especiais
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

CONFIG_FILE = "config_autoclicker.json"

# ===== FUNÇÕES =====
def iniciar():
    global executando, thread_autoclick, contador
    if not executando:
        executando = True
        contador = 0
        atualizar_contador()
        thread_autoclick = threading.Thread(target=auto_click)
        thread_autoclick.daemon = True
        thread_autoclick.start()

def parar():
    global executando
    executando = False

def atualizar_contador():
    label_contador.configure(text=f"Repetições executadas: {contador}")
    if executando:
        app.after(100, atualizar_contador)

def auto_click():
    global executando, contador
    delay = velocidade_slider.get()

    # Construir lista de teclas selecionadas
    teclas_selecionadas = []

    # Teclas normais
    normal = entry_tecla.get()
    if normal:
        teclas_selecionadas.append(normal)

    # Teclas especiais
    for tecla, var in checkboxes_especiais.items():
        if var.get():
            teclas_selecionadas.append(teclas_especiais[tecla])

    if not teclas_selecionadas:
        return

    # Modo infinito ou limitado
    if modo_infinito.get():
        while executando:
            for t in teclas_selecionadas:
                keyboard.press(t)
            for t in reversed(teclas_selecionadas):
                keyboard.release(t)
            contador += 1
            time.sleep(delay)
    else:
        try:
            repeticoes = int(entry_repeticoes.get())
        except ValueError:
            repeticoes = 1
        for _ in range(repeticoes):
            if not executando:
                break
            for t in teclas_selecionadas:
                keyboard.press(t)
            for t in reversed(teclas_selecionadas):
                keyboard.release(t)
            contador += 1
            time.sleep(delay)
        parar()

# Atalhos globais
def on_press(key):
    try:
        if key == Key.f6:
            iniciar()
        elif key == Key.f7:
            parar()
    except AttributeError:
        pass

listener = Listener(on_press=on_press)
listener.daemon = True
listener.start()

# Funções de configuração
def salvar_config():
    config = {
        "tecla_normal": entry_tecla.get(),
        "teclas_especiais": {k: var.get() for k, var in checkboxes_especiais.items()},
        "velocidade": velocidade_slider.get(),
        "modo_infinito": modo_infinito.get(),
        "repeticoes": entry_repeticoes.get()
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def carregar_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        entry_tecla.delete(0, ctk.END)
        entry_tecla.insert(0, config.get("tecla_normal", ""))
        for k, v in config.get("teclas_especiais", {}).items():
            if k in checkboxes_especiais:
                checkboxes_especiais[k].set(v)
        velocidade_slider.set(config.get("velocidade", 0.5))
        modo_infinito.set(config.get("modo_infinito", True))
        entry_repeticoes.delete(0, ctk.END)
        entry_repeticoes.insert(0, config.get("repeticoes", ""))
        atualizar_valor(velocidade_slider.get())
    except FileNotFoundError:
        pass

# ===== INTERFACE =====
app = ctk.CTk()
app.title("Auto Clicker Profissional - Multi-Teclas")
app.geometry("600x600")

# Título
titulo = ctk.CTkLabel(app, text="Auto Clicker Foda", font=("Arial", 22, "bold"))
titulo.pack(pady=10)

# Instruções
instrucao = ctk.CTkLabel(app, 
    text="Instruções:\n1. Digite teclas normais OU selecione múltiplas teclas especiais (Shift, Ctrl, etc.).\n2. Use o slider para definir a velocidade.\n3. Modo infinito ou repetições definidas.\n4. Atalhos globais: F6 → Iniciar | F7 → Parar\n5. Você pode salvar e carregar suas configurações.",
    justify="center"
)
instrucao.pack(pady=10)

# Entrada de tecla normal
label_tecla = ctk.CTkLabel(app, text="Digite teclas normais:")
label_tecla.pack(pady=5)
entry_tecla = ctk.CTkEntry(app)
entry_tecla.pack(pady=5)

# Teclas especiais com checkboxes
label_especial = ctk.CTkLabel(app, text="Selecione teclas especiais:")
label_especial.pack(pady=5)
checkboxes_especiais = {}
frame_check = ctk.CTkFrame(app)
frame_check.pack(pady=5)
for tecla in teclas_especiais.keys():
    var = ctk.BooleanVar(value=False)
    chk = ctk.CTkCheckBox(frame_check, text=tecla, variable=var)
    chk.pack(anchor="w")
    checkboxes_especiais[tecla] = var

# Slider de velocidade
label_vel = ctk.CTkLabel(app, text="Velocidade (intervalo em segundos):")
label_vel.pack(pady=5)
velocidade_slider = ctk.CTkSlider(app, from_=0.001, to=1.0, number_of_steps=1000)
velocidade_slider.set(0.5)
velocidade_slider.pack(pady=10)
valor_label = ctk.CTkLabel(app, text="0.500s")
valor_label.pack(pady=5)
def atualizar_valor(value):
    valor_label.configure(text=f"{float(value):.3f}s")
velocidade_slider.configure(command=atualizar_valor)

# Modo infinito ou número de repetições
modo_infinito = ctk.BooleanVar(value=True)
checkbox_infinito = ctk.CTkCheckBox(app, text="Modo infinito", variable=modo_infinito)
checkbox_infinito.pack(pady=5)
label_repeticoes = ctk.CTkLabel(app, text="Número de repetições (se não infinito):")
label_repeticoes.pack(pady=5)
entry_repeticoes = ctk.CTkEntry(app)
entry_repeticoes.pack(pady=5)

# Contador
label_contador = ctk.CTkLabel(app, text="Repetições executadas: 0")
label_contador.pack(pady=5)

# Botões
frame_btn = ctk.CTkFrame(app)
frame_btn.pack(pady=20)
btn_iniciar = ctk.CTkButton(frame_btn, text="▶ Iniciar", command=iniciar, fg_color="green", hover_color="darkgreen")
btn_iniciar.grid(row=0, column=0, padx=10)
btn_parar = ctk.CTkButton(frame_btn, text="⏹ Parar", command=parar, fg_color="red", hover_color="darkred")
btn_parar.grid(row=0, column=1, padx=10)
btn_salvar = ctk.CTkButton(frame_btn, text="💾 Salvar Config", command=salvar_config, fg_color="blue", hover_color="darkblue")
btn_salvar.grid(row=1, column=0, padx=10, pady=5)
btn_carregar = ctk.CTkButton(frame_btn, text="📂 Carregar Config", command=carregar_config, fg_color="orange", hover_color="darkorange")
btn_carregar.grid(row=1, column=1, padx=10, pady=5)

# Carrega configuração inicial se existir
carregar_config()

# Rodando interface
app.mainloop()
