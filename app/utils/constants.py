from pynput.keyboard import Key

PROFILES_FILE = "macro_profiles.json"

SPECIAL_KEYS = {
    "Espaço": Key.space, "Enter": Key.enter, "Shift": Key.shift,
    "Ctrl": Key.ctrl, "Alt": Key.alt, "Tab": Key.tab,
    "Backspace": Key.backspace, "Esc": Key.esc,
}

# Mapeamentos para salvar/carregar perfis
KEY_MAP_SAVE = {v: f"Key.{k.capitalize()}" for k, v in SPECIAL_KEYS.items()}
KEY_MAP_LOAD = {v: k for k, v in KEY_MAP_SAVE.items()}