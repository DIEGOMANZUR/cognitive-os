from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MailClassificationResult:
    classification: str
    importance_score: float
    rationale: str
    proposed_reply: str | None


IMPORTANT_TERMS = {
    "cita",
    "paciente",
    "consulta",
    "urgente",
    "importante",
    "reunion",
    "factura",
    "pago",
    "contrato",
    "dominio",
    "doctormanzur",
    "doctor",
    "clinic",
    "meeting",
    "invoice",
    "payment",
    "urgent",
    "important",
}
PROMO_TERMS = {"unsubscribe", "newsletter", "promotion", "descuento", "oferta", "sale"}


def classify_and_propose(
    *,
    folder: str,
    sender: str,
    subject: str | None,
    snippet: str | None,
    body_text: str | None,
) -> MailClassificationResult:
    haystack = " ".join(x for x in (sender, subject or "", snippet or "", body_text or "") if x)
    lowered = haystack.lower()
    folder_lower = folder.lower()
    score = 0.2
    reasons: list[str] = []

    hits = sorted(term for term in IMPORTANT_TERMS if term in lowered)
    if hits:
        score += min(0.55, 0.12 * len(hits))
        reasons.append("terminos importantes: " + ", ".join(hits[:5]))
    if any(term in lowered for term in PROMO_TERMS):
        score -= 0.25
        reasons.append("senales promocionales")
    if "spam" in folder_lower or "junk" in folder_lower or "bulk" in folder_lower:
        score -= 0.05
        reasons.append("origen carpeta spam/junk revisada explicitamente")
    if "doctormanzur.com" in lowered:
        score += 0.2
        reasons.append("menciona dominio/cuenta principal")
    score = max(0.0, min(1.0, score))

    if score >= 0.62:
        classification = "important"
    elif any(term in lowered for term in PROMO_TERMS):
        classification = "promo"
    elif "spam" in folder_lower or "junk" in folder_lower or "bulk" in folder_lower:
        classification = "spam"
    else:
        classification = "normal"

    proposed = None
    if classification == "important":
        proposed = _reply_template(sender=sender, subject=subject, snippet=snippet)
    rationale = "; ".join(reasons) if reasons else "clasificacion conservadora por heuristica"
    return MailClassificationResult(classification, score, rationale, proposed)


def _reply_template(*, sender: str, subject: str | None, snippet: str | None) -> str:
    del snippet
    greeting_name = sender.split("<", 1)[0].strip().strip('"') or "hola"
    subject_line = subject or "tu mensaje"
    return (
        f"Hola {greeting_name},\n\n"
        f"Gracias por escribirme sobre {subject_line}. Confirmo recibido.\n\n"
        "Lo reviso y te respondo con más detalle a la brevedad.\n\n"
        "Saludos,\n"
        "Diego"
    )
