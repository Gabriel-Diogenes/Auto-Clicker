import json
import os
from typing import Dict, Any

def load_profiles_from_file(filepath: str) -> Dict[str, Any]:
    """Carrega perfis de um arquivo JSON."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_profiles_to_file(filepath: str, profiles: Dict[str, Any]):
    """Salva o dicionário de perfis em um arquivo JSON."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=4)
    except IOError as e:
        # Idealmente, você logaria este erro ou o notificaria ao usuário
        print(f"Erro ao salvar perfis: {e}")