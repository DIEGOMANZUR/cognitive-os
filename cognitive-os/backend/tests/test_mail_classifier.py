from __future__ import annotations

from cognitive_os.mail.classifier import classify_and_propose


def test_mail_classifier_does_not_trust_spam_folder_for_important_patient_mail() -> None:
    result = classify_and_propose(
        folder="Spam",
        sender="Paciente <patient@example.test>",
        subject="Consulta urgente",
        snippet="Doctor, necesito confirmar una cita importante.",
        body_text="Consulta paciente urgente doctormanzur",
    )

    assert result.classification == "important"
    assert result.proposed_reply is not None
    assert "sin confiar" in result.rationale


def test_mail_classifier_excludes_content_spam_even_from_normal_folder() -> None:
    result = classify_and_propose(
        folder="INBOX",
        sender="Casino <promo@example.test>",
        subject="Ganaste un premio casino",
        snippet="click here limited time",
        body_text="free money lottery winner",
    )

    assert result.classification == "spam"
    assert result.proposed_reply is None
    assert "senales de spam" in result.rationale


def test_mail_classifier_keeps_spam_folder_normal_when_content_is_not_spam() -> None:
    result = classify_and_propose(
        folder="Junk Email",
        sender="Colega <colleague@example.test>",
        subject="Seguimiento",
        snippet="Te mando la informacion que pediste.",
        body_text="Quedo atento.",
    )

    assert result.classification == "normal"
    assert result.proposed_reply is None
    assert "sin confiar" in result.rationale
