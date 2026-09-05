import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Date, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Get connection string from Railway environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback to local SQLite if DATABASE_URL is not set
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./patients.db"

# SQLAlchemy requires 'postgresql://' instead of 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure engine args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Set execution options for Supabase Transaction Pooler (Port 6543)
execution_options = {}
if "pooler.supabase.com" in DATABASE_URL and ":6543" in DATABASE_URL:
    execution_options["isolation_level"] = "AUTOCOMMIT"

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    execution_options=execution_options,
    pool_pre_ping=True,
    pool_recycle=300 if not DATABASE_URL.startswith("sqlite") else -1
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()




# ---------------------------------------------------------------------------
# Patient Model
# ---------------------------------------------------------------------------
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


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
