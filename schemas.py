import re
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator

# ---------------------------------------------------------------------------
# Valid U.S. state abbreviations
# ---------------------------------------------------------------------------
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC"
}

SexEnum = Literal["Male", "Female", "Other", "Decline to Answer"]


# ---------------------------------------------------------------------------
# Base schema — shared validators used by Create and Update
# ---------------------------------------------------------------------------
class PatientBase(BaseModel):
    first_name:    Optional[str] = None
    last_name:     Optional[str] = None
    date_of_birth: Optional[str] = None  # accepts MM/DD/YYYY from voice agent
    sex:           Optional[SexEnum] = None
    phone_number:  Optional[str] = None
    email:         Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city:           Optional[str] = None
    state:          Optional[str] = None
    zip_code:       Optional[str] = None
    insurance_provider:      Optional[str] = None
    insurance_member_id:     Optional[str] = None
    preferred_language:      Optional[str] = "English"
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not (1 <= len(v) <= 50):
            raise ValueError("Name must be 1–50 characters")
        if not re.match(r"^[A-Za-z\-']+$", v):
            raise ValueError("Name may only contain letters, hyphens, or apostrophes")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v is None:
            return v
        # Accept MM/DD/YYYY format from voice agent
        if isinstance(v, str):
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                try:
                    parsed = datetime.strptime(v, fmt).date()
                    if parsed >= date.today():
                        raise ValueError("Date of birth cannot be today or in the future")
                    return parsed
                except ValueError as e:
                    if "future" in str(e):
                        raise
                    continue
            raise ValueError("Date of birth must be in MM/DD/YYYY format (e.g. 01/15/1990)")
        if isinstance(v, date):
            if v >= date.today():
                raise ValueError("Date of birth cannot be today or in the future")
            return v
        raise ValueError("Invalid date format")

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return digits  # store normalized (digits only)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is None:
            return v
        v = v.upper().strip()
        if v not in US_STATES:
            raise ValueError(f"'{v}' is not a valid 2-letter U.S. state abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v):
        if v is None:
            return v
        if not re.match(r"^\d{5}(-\d{4})?$", v.strip()):
            raise ValueError("ZIP code must be 5 digits or ZIP+4 format (e.g. 90210 or 90210-1234)")
        return v.strip()

    @field_validator("city")
    @classmethod
    def validate_city(cls, v):
        if v and not (1 <= len(v.strip()) <= 100):
            raise ValueError("City must be 1–100 characters")
        return v.strip() if v else v


# ---------------------------------------------------------------------------
# Create schema — required fields enforced here
# ---------------------------------------------------------------------------
class PatientCreate(PatientBase):
    first_name:    str
    last_name:     str
    date_of_birth: str   # MM/DD/YYYY — validated and converted by validate_dob
    sex:           SexEnum
    phone_number:  str
    address_line_1: str
    city:           str
    state:          str
    zip_code:       str

    @model_validator(mode="after")
    def required_fields_present(self):
        required = ["first_name", "last_name", "date_of_birth", "sex",
                    "phone_number", "address_line_1", "city", "state", "zip_code"]
        for field in required:
            if not getattr(self, field):
                raise ValueError(f"'{field}' is required")
        return self


# ---------------------------------------------------------------------------
# Update schema — all fields optional (partial updates allowed)
# ---------------------------------------------------------------------------
class PatientUpdate(PatientBase):
    pass  # everything optional via PatientBase


# ---------------------------------------------------------------------------
# Response schema — what the API returns
# ---------------------------------------------------------------------------
class PatientResponse(PatientBase):
    patient_id:   str
    created_at:   datetime
    updated_at:   datetime
    deleted_at:   Optional[datetime] = None

    # Required fields are non-optional in responses
    first_name:    str
    last_name:     str
    date_of_birth: Optional[str] = None
    sex:           SexEnum
    phone_number:  str
    address_line_1: str
    city:           str
    state:          str
    zip_code:       str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Standard API envelope
# ---------------------------------------------------------------------------
class APIResponse(BaseModel):
    data:  Optional[dict | list] = None
    error: Optional[str] = None