from pynput.keyboard import Key

# Arquivo para salvar e carregar os perfis
PROFILES_FILE = "macro_profiles.json"

# Dicionário de teclas especiais para a UI e lógica
SPECIAL_KEYS = {
    "Espaço": Key.space, 
    "Enter": Key.enter, 
    "Shift": Key.shift,
    "Ctrl": Key.ctrl, 
    "Alt": Key.alt, 
    "Tab": Key.tab,
    "Backspace": Key.backspace, 
    "Esc": Key.esc,
}

# Mapeamentos usados para converter as teclas para texto (na hora de salvar em JSON) e vice-versa.
# Ex: O objeto Key.space vira a string "Key.Space"
KEY_MAP_SAVE = {
    Key.space: "Key.Espaço",
    Key.enter: "Key.Enter",
    Key.shift: "Key.Shift",
    Key.ctrl: "Key.Ctrl",
    Key.alt: "Key.Alt",
    Key.tab: "Key.Tab",
    Key.backspace: "Key.Backspace",
    Key.esc: "Key.Esc"
}
# Mapeamento inverso para carregar do JSON de volta para o objeto de tecla
KEY_MAP_LOAD = {v: k for k, v in KEY_MAP_SAVE.items()}