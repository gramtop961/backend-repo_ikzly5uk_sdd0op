import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Student, KYCDocument, ProofSubmission, Donation

app = FastAPI(title="EduChain API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helpers ---

def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


def compute_trust_score(student_id: str) -> float:
    # Heuristic trust scoring: KYC + proofs count
    sid = oid(student_id)
    student = db["student"].find_one({"_id": sid})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    kyc = db["kycdocument"].find_one({"student_id": student_id})
    proofs_count = db["proofsubmission"].count_documents({"student_id": student_id})

    score = 10.0
    if kyc:
        score += 30
        if kyc.get("status") == "verified":
            score += 30
        elif kyc.get("status") == "pending":
            score += 10
    score += min(30, proofs_count * 5)
    return float(max(0, min(100, score)))


# --- Core Endpoints ---

@app.get("/")
def root():
    return {"app": "EduChain API", "status": "ok"}


@app.get("/test")
def test_database():
    try:
        collections = db.list_collection_names() if db else []
        return {
            "backend": "running",
            "database": "connected" if db else "not_configured",
            "collections": collections,
        }
    except Exception as e:
        return {"backend": "running", "database": f"error: {str(e)[:80]}"}


# Students
@app.post("/students")
def create_student(student: Student):
    data = student.model_dump()
    _id = create_document("student", data)
    # initialize trust score
    db["student"].update_one({"_id": ObjectId(_id)}, {"$set": {"trust_score": 0.0}})
    return {"id": _id}


@app.get("/students")
def list_students(limit: int = Query(50, ge=1, le=200)):
    docs = get_documents("student", {}, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


# KYC
@app.post("/kyc")
def submit_kyc(payload: KYCDocument):
    # Save/Update KYC
    existing = db["kycdocument"].find_one({"student_id": payload.student_id})
    if existing:
        db["kycdocument"].update_one({"_id": existing["_id"]}, {"$set": payload.model_dump()})
        kyc_id = str(existing["_id"]) 
    else:
        kyc_id = create_document("kycdocument", payload)

    # Update student status
    db["student"].update_one({"_id": oid(payload.student_id)}, {"$set": {"kyc_status": payload.status}})
    # Auto trust score refresh
    ts = compute_trust_score(payload.student_id)
    db["student"].update_one({"_id": oid(payload.student_id)}, {"$set": {"trust_score": ts}})
    return {"id": kyc_id, "trust_score": ts}


# Proofs
@app.post("/proofs")
def submit_proof(proof: ProofSubmission):
    _id = create_document("proofsubmission", proof)
    # Recompute trust score when proofs submitted
    try:
        ts = compute_trust_score(proof.student_id)
        db["student"].update_one({"_id": oid(proof.student_id)}, {"$set": {"trust_score": ts}})
    except Exception:
        ts = None
    return {"id": _id, "trust_score": ts}


# Donations / Payments (Unified Intent)
class PaymentIntentResponse(BaseModel):
    reference: str
    redirect_url: Optional[str] = None
    status: str


@app.post("/donations/initiate", response_model=PaymentIntentResponse)
def initiate_donation(donation: Donation):
    # Validate scholarship range for INR as per brief (if currency is INR)
    amt = donation.amount
    if donation.scholarship == "micro" and donation.currency == "INR" and not (10 <= amt <= 5000):
        raise HTTPException(400, detail="Micro scholarship must be between ₹10–₹5,000")
    if donation.scholarship == "big" and donation.currency == "INR" and not (10000 <= amt <= 1000000):
        raise HTTPException(400, detail="Big scholarship must be between ₹10,000–₹10,00,000")

    # Create internal record
    donation_id = create_document("donation", donation)
    payment_reference = f"EDC-{donation.gateway}-{donation_id}"

    # Placeholder: In production, create real gateway intents here (Stripe, PayPal, UPI, etc.)
    redirect_url = None
    status = "created"

    db["donation"].update_one({"_id": oid(donation_id)}, {"$set": {"payment_reference": payment_reference, "status": status}})
    return PaymentIntentResponse(reference=payment_reference, redirect_url=redirect_url, status=status)


class WebhookUpdate(BaseModel):
    reference: str
    status: str
    gateway_tx: Optional[str] = None
    blockchain_tx: Optional[str] = None


@app.post("/donations/webhook")
def donation_webhook(update: WebhookUpdate):
    # Update donation based on payment provider notification
    d = db["donation"].find_one({"payment_reference": update.reference})
    if not d:
        raise HTTPException(404, detail="Donation not found")
    db["donation"].update_one({"_id": d["_id"]}, {"$set": update.model_dump(exclude_none=True)})
    return {"ok": True}


# Blockchain tracker (stub storing tx hash)
@app.post("/blockchain/record/{donation_id}")
def record_blockchain_tx(donation_id: str, tx_hash: str):
    db["donation"].update_one({"_id": oid(donation_id)}, {"$set": {"blockchain_tx": tx_hash}})
    return {"ok": True, "tx_hash": tx_hash}


# Discovery & Heatmap
@app.get("/discover")
def discover_students(lat: Optional[float] = None, lng: Optional[float] = None, radius_km: float = Query(50, gt=0), limit: int = Query(100, le=200)):
    # Simple filter: if lat/lng provided, return those with location set; real geo search would use 2dsphere index
    query = {}
    if lat is not None and lng is not None:
        query = {"location": {"$ne": None}}
    docs = list(db["student"].find(query).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.get("/heatmap")
def heatmap():
    pipeline = [
        {"$match": {"location": {"$ne": None}}},
        {"$group": {"_id": {"city": "$city", "country": "$country"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    agg = list(db["student"].aggregate(pipeline))
    points = [
        {
            "city": (a["_id"].get("city") or "Unknown"),
            "country": (a["_id"].get("country") or "Unknown"),
            "count": a["count"],
        }
        for a in agg
    ]
    return {"points": points}


# Trust score endpoint
@app.get("/trust/{student_id}")
def get_trust(student_id: str):
    ts = compute_trust_score(student_id)
    db["student"].update_one({"_id": oid(student_id)}, {"$set": {"trust_score": ts}})
    return {"trust_score": ts}


# Schemas info (lightweight description for admin tools)
@app.get("/schema")
def schema_info():
    return {
        "collections": [
            "student",
            "kycdocument",
            "proofsubmission",
            "donation",
            "csrproject",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
