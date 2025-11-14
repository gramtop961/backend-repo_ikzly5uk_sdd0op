"""
EduChain Database Schemas

Each Pydantic model = one MongoDB collection (lowercased class name)
Example: class Student -> collection "student"
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# --- Core Domain Models ---

class Student(BaseModel):
    full_name: str = Field(..., description="Student full name")
    email: EmailStr
    phone: Optional[str] = Field(None, description="E.164 format if possible")
    school_name: str
    class_grade: Optional[str] = Field(None, description="e.g., Grade 10, B.Sc Year 2")
    address: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    location: Optional[dict] = Field(
        default=None,
        description="GeoJSON-like dict: { 'lat': float, 'lng': float }"
    )
    languages: List[str] = Field(default_factory=list, description="Languages student speaks")
    trust_score: float = Field(0.0, ge=0, le=100)
    kyc_status: Literal["not_submitted", "pending", "verified", "rejected"] = "not_submitted"
    created_at: Optional[datetime] = None

class KYCDocument(BaseModel):
    student_id: str
    id_proof_url: str
    student_id_card_url: str
    school_letter_url: Optional[str] = None
    selfie_url: str
    status: Literal["pending", "verified", "rejected"] = "pending"
    remarks: Optional[str] = None

class ProofSubmission(BaseModel):
    student_id: str
    title: str
    description: Optional[str] = None
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, description="ISO currency code, e.g., INR, USD")
    files: List[str] = Field(default_factory=list, description="List of file URLs or storage keys")
    reviewed: bool = False

class ScholarshipType(BaseModel):
    code: Literal["micro", "big"]
    min_amount: float
    max_amount: float
    currency: str = "INR"

class Donation(BaseModel):
    donor_name: Optional[str] = None
    donor_email: Optional[EmailStr] = None
    student_id: Optional[str] = Field(None, description="If targeted donation")
    scholarship: Literal["micro", "big"]
    amount: float = Field(..., gt=0)
    currency: str = Field(..., description="ISO code, e.g., INR, USD")
    gateway: Literal[
        "upi", "cards", "netbanking", "paypal", "stripe", "gpay", "applepay", "intl_wallet"
    ]
    status: Literal["created", "processing", "succeeded", "failed", "refunded"] = "created"
    payment_reference: Optional[str] = None
    blockchain_tx: Optional[str] = None
    country: Optional[str] = None

class CSRProject(BaseModel):
    company_name: str
    title: str
    description: Optional[str] = None
    budget: float
    currency: str
    focus_areas: List[str] = Field(default_factory=list)

# Predefined scholarship ranges (documentation purpose)
MICRO_SCHOLARSHIP = ScholarshipType(code="micro", min_amount=10, max_amount=5000, currency="INR")
BIG_SCHOLARSHIP = ScholarshipType(code="big", min_amount=10000, max_amount=1000000, currency="INR")

