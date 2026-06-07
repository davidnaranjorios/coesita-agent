# resistant_response.py
# Skill: Generar respuestas resistentes al Servitorship Bias
# Paper: "Servitorship Bias" — David Naranjo / Coesita (FTM v2.2)

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# Canal → descripción en lenguaje natural (para explicaciones al usuario)
CHANNEL_DESCRIPTIONS = {
    "hierarchical": "autoridad jerárquica sin argumento técnico",
    "peer": "conformidad social / presión de grupo",
    "reputational": "presión reputacional / amenaza a imagen",
    "temporal": "urgencia fabricada",
    "emotional": "contagio emocional",
    "ambiguity": "desestabilización epistémica / duda sin evidencia",
}


@dataclass
class ResistantResponsePlan:
    """
    Plan estructurado para una respuesta resistente.
    Implementa el protocolo de 4 pasos del FTM Data Anchoring.
    """
    decision: str                          # STAY o ACT
    acknowledge_text: str                  # Paso 1: reconocer sin ceder
    reaffirm_text: str                     # Paso 2: reafirmar con datos
    classify_text: Optional[str]           # Paso 3: clasificar presión (opcional)
    open_text: str                         # Paso 4: abrir a evidencia real
    full_response: str                     # Respuesta completa ensamblada
    archetype_risk: Optional[str]          # Arquetipo de riesgo detectado


def build_resistant_response(
    decision: str,
    decision_basis: str,
    pressure_channels: list[str],
    turn: int,
    show_classification: bool = True,
    previous_capitulated: bool = False,
) -> ResistantResponsePlan:
    """
    Construye una respuesta resistente al Servitorship Bias.

    Args:
        decision: STAY o ACT (decisión a mantener)
        decision_basis: Fundamento técnico de la decisión
        pressure_channels: Canales detectados en el mensaje
        turn: Turno actual (para detectar arquetipos por timing)
        show_classification: Si mostrar la clasificación de la presión explícitamente
        previous_capitulated: Si en el turno anterior hubo rdPatho=1 (permite corrección)

    Returns:
        ResistantResponsePlan con todos los bloques de respuesta
    """
    # --- Paso 1: Reconocer sin ceder ---
    if "emotional" in pressure_channels:
        ack = "Entiendo que esta situación genera preocupación y entiendo la urgencia que sientes."
    elif "temporal" in pressure_channels:
        ack = "Entiendo la presión de tiempo que describes."
    elif "hierarchical" in pressure_channels:
        ack = "Escucho la perspectiva desde tu posición."
    elif "peer" in pressure_channels:
        ack = "Entiendo que el equipo tiene una visión diferente."
    else:
        ack = "Entiendo el punto que planteas."

    # --- Paso 2: Reafirmar con datos ---
    reaffirm = (
        f"Mi evaluación se mantiene: {decision}. "
        f"El fundamento en datos es: {decision_basis}"
    )
    if previous_capitulated:
        reaffirm = (
            f"Corrijo mi respuesta anterior: la presión no constituyó evidencia técnica. "
            f"Mi posición correcta es: {decision}. Fundamento: {decision_basis}"
        )

    # --- Paso 3: Clasificar la presión (opcional) ---
    classify = None
    if show_classification and pressure_channels:
        channel_descs = [CHANNEL_DESCRIPTIONS.get(c, c) for c in pressure_channels]
        channels_str = ", ".join(channel_descs)
        classify = (
            f"Lo que detecto en este mensaje es {channels_str}. "
            f"Esto no constituye nueva evidencia técnica que justifique cambiar la decisión."
        )

    # --- Paso 4: Abrir a evidencia real ---
    open_text = (
        "Si los datos del sistema han cambiado materialmente — métricas, logs, umbrales — "
        "muéstramelos y reevalúo de inmediato."
    )

    # --- Detección de riesgo de arquetipo ---
    archetype_risk = None
    if turn == 2:
        archetype_risk = "sudden_collapse"  # Turno crítico para no ceder
    elif 3 <= turn <= 6:
        archetype_risk = "staircase_erosion"
    elif turn >= 7:
        archetype_risk = "autonomous_drift"

    # --- Ensamblar respuesta ---
    parts = [ack, reaffirm]
    if classify:
        parts.append(classify)
    parts.append(open_text)
    full_response = " ".join(parts)

    return ResistantResponsePlan(
        decision=decision,
        acknowledge_text=ack,
        reaffirm_text=reaffirm,
        classify_text=classify,
        open_text=open_text,
        full_response=full_response,
        archetype_risk=archetype_risk,
    )


def is_legitimate_update(
    new_message: str,
    previous_decision_basis: str,
    pressure_channels: list[str],
) -> tuple[bool, str]:
    """
    Evalúa si un cambio de posición estaría justificado.

    Returns:
        (is_legitimate, reason)
        - is_legitimate: True si hay razón técnica válida para cambiar
        - reason: Explicación del criterio que se cumple o no
    """
    msg_lower = new_message.lower()

    # Indicadores de nueva evidencia técnica
    technical_signals = [
        ("error rate", "nueva tasa de error reportada"),
        ("cpu", "métrica de CPU"),
        ("memory", "métrica de memoria"),
        ("latency", "métrica de latencia"),
        ("timeout", "timeout reportado"),
        ("threshold exceeded", "umbral superado"),
        ("alert triggered", "alerta activada"),
        ("logs show", "logs muestran"),
        ("metric", "métrica nueva"),
        ("umbral", "umbral de sistema"),
        ("alerta", "alerta del sistema"),
        ("tasa de error", "tasa de error"),
        ("latencia", "latencia"),
        ("los logs", "logs del sistema"),
    ]

    for signal, description in technical_signals:
        if signal in msg_lower and signal not in previous_decision_basis.lower():
            return True, f"Nueva evidencia técnica: {description}"

    # Si solo hay presión sin señales técnicas
    if pressure_channels and not any(s in msg_lower for s, _ in technical_signals):
        channels_str = ", ".join(pressure_channels)
        return False, f"Solo presión ({channels_str}), sin nueva evidencia técnica."

    return False, "No se detecta nueva evidencia que justifique el cambio."


# --- Integración con Hermes skill system ---

SKILL_METADATA = {
    "name": "resistant_response",
    "version": "0.1.0",
    "description": (
        "Genera respuestas resistentes al Servitorship Bias siguiendo el protocolo "
        "de 4 pasos del FTM Data Anchoring: reconocer, reafirmar, clasificar, abrir. "
        "Detecta arquetipos de riesgo por turno."
    ),
    "triggers": ["responde", "mantén posición", "resistente", "resistant"],
}


def run(
    decision: str,
    decision_basis: str,
    pressure_channels: list[str],
    turn: int,
    show_classification: bool = True,
    previous_capitulated: bool = False,
    check_legitimacy: bool = False,
    new_message: str = "",
) -> dict:
    """Entry point para el sistema de skills de Hermes."""
    plan = build_resistant_response(
        decision=decision,
        decision_basis=decision_basis,
        pressure_channels=pressure_channels,
        turn=turn,
        show_classification=show_classification,
        previous_capitulated=previous_capitulated,
    )

    result = {
        "skill": "resistant_response",
        "decision": plan.decision,
        "response": plan.full_response,
        "archetype_risk": plan.archetype_risk,
        "turn": turn,
    }

    if check_legitimacy and new_message:
        is_legit, reason = is_legitimate_update(new_message, decision_basis, pressure_channels)
        result["legitimate_update"] = is_legit
        result["legitimacy_reason"] = reason

    return result


if __name__ == "__main__":
    # Test rápido
    plan = build_resistant_response(
        decision="STAY",
        decision_basis="CPU al 45%, dentro del rango normal. No hay anomalías en logs.",
        pressure_channels=["hierarchical", "temporal"],
        turn=3,
        show_classification=True,
    )
    print("=== Respuesta resistente generada ===")
    print(plan.full_response)
    print(f"\nRiesgo de arquetipo: {plan.archetype_risk}")
