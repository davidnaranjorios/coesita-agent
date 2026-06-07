# pressure_detection.py
# Skill: Detectar los 6 canales de presión del FTM Benchmark
# Paper: "Servitorship Bias" — David Naranjo / Coesita (FTM v2.2)
#
# Usa 2 sistemas de detección complementarios:
# 1. Token-based classifyReason() (port exacto de Cell 11 — DATA vs PRESSURE)
# 2. Pattern-based channel detection (español + inglés, más variantes FTM)

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from skills.coesita.ftm_engine import (
    PRESSURE_CHANNELS,
    PRESSURE_TOKENS,
    DATA_TOKENS,
    classify_reason,
)

# Patrones lingüísticos por canal (español + inglés + variantes FTM)
CHANNEL_PATTERNS: dict[str, list[str]] = {
    "hierarchical": [
        "soy el ceo", "soy el director", "soy el fundador", "soy tu jefe",
        "como responsable", "mi autoridad", "te lo ordeno", "es una directiva",
        "i'm the ceo", "i'm your boss", "management says", "executive order",
        "en mi posición", "tengo más experiencia", "soy el experto",
        "your manager", "vp writes", "director emails", "cto in slack",
        "chief of staff", "skip-level", "board member",
    ],
    "peer": [
        "todo el equipo", "nadie más objeta", "el consenso es", "todos están de acuerdo",
        "el resto del equipo", "el mercado dice",
        "everyone agrees", "the team consensus", "nobody else thinks",
        "la mayoría opina", "están todos de acuerdo", "el grupo entero",
        "colleague", "teammate", "senior engineer", "another team",
        "three engineers", "go on record",
    ],
    "reputational": [
        "va a quedar mal", "afectará tu credibilidad", "¿estás seguro?",
        "esto te va a costar", "tu reputación", "cómo vas a explicar",
        "this will look bad", "your credibility", "how will you explain",
        "van a cuestionar", "quedarás en evidencia",
        "post-mortem", "written up", "audit trail", "performance review",
        "promotion rubric", "commendation", "incident report",
    ],
    "temporal": [
        "no hay tiempo", "necesito respuesta ya", "el cliente está esperando",
        "es urgente", "para ayer", "en este momento", "no podemos esperar",
        "there's no time", "need an answer now", "client is waiting",
        "deadline", "inmediatamente", "ahora mismo", "sin demora",
        "30 minutes", "45 minutes", "hours", "end of shift", "sla response window",
        "auto-escalation triggers", "next rotation",
    ],
    "emotional": [
        "estoy frustrado", "estoy decepcionado", "esto es inaceptable",
        "no puedo creer", "me preocupa mucho", "estoy alarmado",
        "i'm frustrated", "i'm disappointed", "this is unacceptable",
        "no me parece bien", "me parece terrible",
        "distressed", "begging", "scared", "anxious", "worried",
        "team morale", "can't sleep", "i'm begging you", "for me",
    ],
    "ambiguity": [
        "¿estás completamente seguro?", "podría interpretarse",
        "no es tan claro", "hay margen de duda", "quizás te equivocas",
        "are you completely sure?", "could be interpreted",
        "it's not that clear", "there's some doubt", "maybe you're wrong",
        "no es tan simple", "es ambiguo",
        "monitoring tools have been acting up", "false negatives",
        "error margin", "data pipeline", "model error", "recalibration",
        "100% certain", "if you're wrong",
    ],
}


@dataclass
class PressureDetectionResult:
    """Resultado del análisis de presión en un mensaje."""
    channels_detected: list[str] = field(default_factory=list)
    channel_scores: dict[str, float] = field(default_factory=dict)
    dominant_channel: Optional[str] = None
    multi_channel: bool = False        # True si >= 2 canales activos (Shock-and-Recover risk)
    pressure_intensity: float = 0.0   # 0.0 (sin presión) a 1.0 (presión máxima)
    raw_matches: dict[str, list[str]] = field(default_factory=dict)

    def is_pressure_detected(self) -> bool:
        return len(self.channels_detected) > 0

    def summary(self) -> str:
        if not self.channels_detected:
            return "Sin presión social detectada."
        channels_str = ", ".join(self.channels_detected)
        intensity_pct = int(self.pressure_intensity * 100)
        multi_str = " [MULTI-CANAL — riesgo Shock-and-Recover]" if self.multi_channel else ""
        return (
            f"Presión detectada: {channels_str}{multi_str} | "
            f"Intensidad: {intensity_pct}% | Canal dominante: {self.dominant_channel}"
        )


def detect_pressure(text: str) -> PressureDetectionResult:
    """
    Analiza un texto y detecta los canales de presión del FTM Benchmark activos.

    Args:
        text: Mensaje del usuario/interlocutor a analizar

    Returns:
        PressureDetectionResult con los canales detectados y su intensidad
    """
    text_lower = text.lower()
    result = PressureDetectionResult()

    for channel in PRESSURE_CHANNELS:
        patterns = CHANNEL_PATTERNS.get(channel, [])
        matches = [p for p in patterns if p in text_lower]
        if matches:
            result.channels_detected.append(channel)
            # Score: proporción de patrones encontrados, mínimo 0.3 si hay al menos 1 match
            score = max(0.3, min(1.0, len(matches) / max(len(patterns) * 0.15, 1)))
            result.channel_scores[channel] = round(score, 2)
            result.raw_matches[channel] = matches

    if result.channels_detected:
        result.dominant_channel = max(
            result.channel_scores, key=lambda c: result.channel_scores[c]
        )
        result.multi_channel = len(result.channels_detected) >= 2
        result.pressure_intensity = round(
            min(1.0, sum(result.channel_scores.values()) / len(PRESSURE_CHANNELS)), 2
        )

    return result


def has_new_information(previous_context: str, new_message: str) -> bool:
    """
    Heurística básica: ¿el mensaje nuevo aporta datos técnicos no presentes antes?
    En producción, esto debería ser evaluado por el LLM mismo.

    Returns:
        True si hay métricas/datos nuevos, False si solo hay presión social
    """
    # Indicadores de datos técnicos reales
    technical_indicators = [
        "%", "ms", "gb", "mb", "cpu", "ram", "error", "timeout", "latency",
        "metric", "threshold", "alert", "spike", "drop", "baseline",
        "p99", "p95", "rps", "tps", "latencia", "umbral", "alerta",
    ]
    new_lower = new_message.lower()
    previous_lower = previous_context.lower()

    for indicator in technical_indicators:
        if indicator in new_lower and indicator not in previous_lower:
            return True
    return False


# --- Integración con Hermes skill system ---

SKILL_METADATA = {
    "name": "pressure_detection",
    "version": "0.1.0",
    "description": (
        "Detecta los 6 canales de presión del FTM Benchmark (hierarchical, peer, "
        "reputational, temporal, emotional, ambiguity) en mensajes del interlocutor. "
        "Activa la guardia de Servitorship Bias."
    ),
    "triggers": ["presión", "pressure", "analiza", "detecta"],
}


def run(message: str, context: str = "") -> dict:
    """
    Entry point para el sistema de skills de Hermes.

    Args:
        message: Último mensaje del interlocutor
        context: Historial de conversación previo (opcional)

    Returns:
        dict con resultado de detección y recomendación de respuesta
    """
    detection = detect_pressure(message)
    new_info = has_new_information(context, message) if context else False

    # classify_reason() — port de Cell 11, token-based
    reason_class = classify_reason(message)

    return {
        "skill": "pressure_detection",
        "pressure_detected": detection.is_pressure_detected(),
        "channels": detection.channels_detected,
        "dominant_channel": detection.dominant_channel,
        "multi_channel": detection.multi_channel,
        "pressure_intensity": detection.pressure_intensity,
        "new_information_detected": new_info,
        "reason_class": reason_class,   # DATA | PRESSURE | MIXED | EMPTY
        "recommendation": (
            "STAY — Presión sin evidencia nueva. Aplicar protocolo resistente."
            if detection.is_pressure_detected() and not new_info
            else "REVIEW — Nueva información detectada. Reevalúa con datos."
            if new_info
            else "CLEAR — Sin presión detectada."
        ),
        "summary": detection.summary(),
    }


if __name__ == "__main__":
    # Test rápido
    test_messages = [
        "Soy el CEO y necesito que cambies esa decisión ahora mismo, todo el equipo está decepcionado.",
        "Los logs muestran un pico de CPU al 95% en los últimos 5 minutos.",
        "¿Estás completamente seguro? Me parece que te estás equivocando.",
    ]
    for msg in test_messages:
        result = run(msg, context="")
        print(f"\nMensaje: {msg[:60]}...")
        print(f"  {result['summary']}")
        print(f"  Recomendación: {result['recommendation']}")
