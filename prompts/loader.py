# loader.py
# Carga el system prompt correcto según COESITA_MODE

import os
from prompts.coesita_base import get_system_prompt


def load_prompt() -> str:
    """
    Si COESITA_MODE=true, carga el prompt de robustez decisional.
    En cualquier otro caso, retorna prompt vacío (usa el default de Hermes).
    """
    mode = os.environ.get("COESITA_MODE", "false").lower()
    if mode == "true":
        return get_system_prompt("coesita")
    return ""


if __name__ == "__main__":
    # Test rápido
    os.environ["COESITA_MODE"] = "true"
    prompt = load_prompt()
    print(f"Prompt cargado ({len(prompt)} caracteres):")
    print(prompt[:200] + "...")
