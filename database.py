import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Date, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Engine — uses DATABASE_URL from environment (Supabase Postgres in production)
# Falls back to local SQLite so you can still run without a .env file
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Disable prepared statements for Supabase PgBouncer pooler (port 6543)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"prepared_statement_cache_size": 0} if "pooler.supabase.com" in (DATABASE_URL or "") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Patient(Base):
    __tablename__ = "patients"

    # Auto-generated fields
    patient_id   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    deleted_at   = Column(DateTime, nullable=True, default=None)  # soft-delete

    # Required demographic fields
    first_name       = Column(String(50),  nullable=False)
    last_name        = Column(String(50),  nullable=False)
    date_of_birth    = Column(Date,        nullable=False)
    sex              = Column(SAEnum("Male", "Female", "Other", "Decline to Answer",
                                    name="sex_enum"), nullable=False)
    phone_number     = Column(String(10),  nullable=False)
    address_line_1   = Column(String(200), nullable=False)
    city             = Column(String(100), nullable=False)
    state            = Column(String(2),   nullable=False)
    zip_code         = Column(String(10),  nullable=False)

    # Optional demographic fields
    email                  = Column(String(254), nullable=True)
    address_line_2         = Column(String(200), nullable=True)
    insurance_provider     = Column(String(100), nullable=True)
    insurance_member_id    = Column(String(50),  nullable=True)
    preferred_language     = Column(String(50),  nullable=True, default="English")
    emergency_contact_name  = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(10),  nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

