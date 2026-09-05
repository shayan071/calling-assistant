"""
webhook.py — Vapi event handler

Vapi sends a POST to /webhook whenever the LLM decides to call a tool.
We handle two tools:
  - save_patient    → validate + insert new patient record
  - lookup_patient  → check if phone number already exists (duplicate detection)

Vapi expects a response of:
  { "results": [{ "toolCallId": "...", "result": "<string>" }] }

The "result" string is read aloud to the caller by the TTS engine, so keep
it conversational and concise.
"""

import logging
from datetime import date
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from database import Patient, get_db
from schemas import PatientCreate

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Main webhook entry point
# ---------------------------------------------------------------------------
@router.post("/webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    logger.info("Vapi webhook received: %s", body)

    message = body.get("message", {})
    msg_type = message.get("type")

    # Vapi sends different event types; we only care about tool-call events
    if msg_type != "tool-calls":
        return {"status": "ignored"}

    tool_calls = message.get("toolCalls", [])
    results = []

    for call in tool_calls:
        tool_name = call.get("function", {}).get("name")
        arguments = call.get("function", {}).get("arguments", {})
        call_id   = call.get("id")

        if tool_name == "save_patient":
            result_text = handle_save_patient(arguments, db)
        elif tool_name == "lookup_patient":
            result_text = handle_lookup_patient(arguments, db)
        else:
            result_text = "I'm sorry, something went wrong on my end. Please try again."

        results.append({"toolCallId": call_id, "result": result_text})
        logger.info("Tool '%s' result: %s", tool_name, result_text)

    return {"results": results}


# ---------------------------------------------------------------------------
# Tool: save_patient
# Called after the agent has confirmed all fields with the caller.
# ---------------------------------------------------------------------------
def handle_save_patient(args: dict, db: Session) -> str:
    try:
        # Validate incoming data with Pydantic
        data = PatientCreate(**args)
    except Exception as e:
        logger.error("Validation error in save_patient: %s", e)
        return (
            "I'm sorry, there was a problem with some of the information provided. "
            "Could you please confirm your details again?"
        )

    # Duplicate detection — check by phone number
    existing = db.query(Patient).filter(
        Patient.phone_number == data.phone_number,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if existing:
        return (
            f"It looks like we already have a record on file for "
            f"{existing.first_name} {existing.last_name} with that phone number. "
            f"Would you like to update your information instead?"
        )

    # Create and persist the new patient
    try:
        patient = Patient(
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            sex=data.sex,
            phone_number=data.phone_number,
            email=data.email,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            state=data.state,
            zip_code=data.zip_code,
            insurance_provider=data.insurance_provider,
            insurance_member_id=data.insurance_member_id,
            preferred_language=data.preferred_language or "English",
            emergency_contact_name=data.emergency_contact_name,
            emergency_contact_phone=data.emergency_contact_phone,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        logger.info("New patient saved: %s (ID: %s)", patient.first_name, patient.patient_id)

        return (
            f"You're all set, {patient.first_name}! "
            f"Your registration has been saved successfully. "
            f"Your patient ID is {patient.patient_id[:8]}. "
            f"Is there anything else I can help you with?"
        )

    except Exception as e:
        db.rollback()
        logger.error("DB write failed: %s", e)
        return (
            "I'm sorry, we encountered a technical issue saving your record. "
            "Please call back in a few minutes and we'll get you registered."
        )


# ---------------------------------------------------------------------------
# Tool: lookup_patient
# Called early in the conversation to detect returning callers.
# ---------------------------------------------------------------------------
def handle_lookup_patient(args: dict, db: Session) -> str:
    phone = args.get("phone_number", "")
    # Normalize to digits only
    digits = "".join(filter(str.isdigit, phone))

    if len(digits) != 10:
        return "not_found"

    existing = db.query(Patient).filter(
        Patient.phone_number == digits,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if existing:
        return (
            f"found:{existing.first_name}:{existing.last_name}:{existing.patient_id}"
        )

    return "not_found"
