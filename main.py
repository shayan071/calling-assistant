import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Patient, get_db, init_db
from schemas import PatientCreate, PatientUpdate, PatientResponse
from webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_patients()
    logger.info("Database initialized. Server ready.")
    yield


def seed_demo_patients():
    from database import SessionLocal
    from datetime import date

    db = SessionLocal()
    try:
        if db.query(Patient).count() == 0:
            demos = [
                Patient(
                    first_name="Jane", last_name="Doe",
                    date_of_birth=date(1985, 6, 15), sex="Female",
                    phone_number="5550001234",
                    address_line_1="123 Main St", city="Austin",
                    state="TX", zip_code="78701",
                    email="jane.doe@example.com",
                    preferred_language="English",
                ),
                Patient(
                    first_name="Carlos", last_name="Rivera",
                    date_of_birth=date(1990, 3, 22), sex="Male",
                    phone_number="5550005678",
                    address_line_1="456 Oak Ave", city="Miami",
                    state="FL", zip_code="33101",
                    preferred_language="Spanish",
                ),
            ]
            db.add_all(demos)
            db.commit()
            logger.info("Seeded 2 demo patient records.")
    finally:
        db.close()


app = FastAPI(
    title="Patient Registration Voice Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


def ok(data):
    return {"data": data, "error": None}

def err(msg: str):
    return {"data": None, "error": msg}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/patients")
def list_patients(
    last_name:     str = Query(None),
    date_of_birth: str = Query(None),
    phone_number:  str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Patient).filter(Patient.deleted_at == None)  # noqa: E711

    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if date_of_birth:
        query = query.filter(Patient.date_of_birth == date_of_birth)
    if phone_number:
        digits = "".join(filter(str.isdigit, phone_number))
        query = query.filter(Patient.phone_number == digits)

    patients = query.order_by(Patient.created_at.desc()).all()
    return ok([PatientResponse.model_validate(p).model_dump(mode="json") for p in patients])


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail=err("Patient not found"))

    return ok(PatientResponse.model_validate(patient).model_dump(mode="json"))


@app.post("/patients", status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(
        Patient.phone_number == payload.phone_number,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if existing:
        raise HTTPException(
            status_code=422,
            detail=err(f"A patient with phone {payload.phone_number} already exists "
                       f"(ID: {existing.patient_id}). Use PUT to update.")
        )

    patient = Patient(**payload.model_dump(exclude_none=False))
    db.add(patient)
    db.commit()
    db.refresh(patient)

    logger.info("Created patient: %s %s (ID: %s)",
                patient.first_name, patient.last_name, patient.patient_id)

    return ok(PatientResponse.model_validate(patient).model_dump(mode="json"))


@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail=err("Patient not found"))

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)

    patient.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)

    logger.info("Updated patient ID: %s", patient_id)
    return ok(PatientResponse.model_validate(patient).model_dump(mode="json"))


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at == None  # noqa: E711
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail=err("Patient not found"))

    patient.deleted_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Soft-deleted patient ID: %s", patient_id)
    return ok({"message": f"Patient {patient_id} has been deleted."})
