from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

# Scholarship ranges
MICRO_MIN_INR = 10
MICRO_MAX_INR = 5000
BIG_MIN_INR = 10000
BIG_MAX_INR = 1000000

class Student(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    country: Optional[str] = None

    # Education
    school_name: Optional[str] = None
    grade: Optional[str] = None

    # Discovery
    languages: Optional[List[str]] = None
    location: Optional[dict] = None  # {lat, lng, city, state}

    # Scores
    trust_score: Optional[float] = Field(default=0.0, ge=0, le=100)

class KYCDocument(BaseModel):
    student_id: str
    id_proof_url: str
    student_id_card_url: str
    school_letter_url: Optional[str] = None
    selfie_url: str
    status: str = Field(default="pending")  # pending, verified, rejected

class ProofSubmission(BaseModel):
    student_id: str
    title: str
    description: Optional[str] = None
    amount: Optional[float] = None
    files: List[str] = []

class Donation(BaseModel):
    student_id: Optional[str] = None
    scholarship: str  # micro | big
    amount: float
    currency: str = "INR"  # multi-currency support
    gateway: str  # upi, cards, netbanking, paypal, stripe, gpay, applepay, intl_wallet

class CSRProject(BaseModel):
    name: str
    description: Optional[str] = None
    budget: Optional[float] = None

