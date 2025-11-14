from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from database import db, create_document, get_documents
from schemas import Student, KYCDocument, ProofSubmission, Donation, CSRProject, MICRO_MIN_INR, MICRO_MAX_INR, BIG_MIN_INR, BIG_MAX_INR

app = FastAPI(title="EduChain API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    message: str = "EduChain backend running"


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "EduChain backend running"}


@app.get("/test")
async def test():
    database = db()
    status = "connected" if database is not None else "not_connected"
    collections = []
    if database is not None:
        try:
            collections = database.list_collection_names()
        except Exception:
            collections = []
    return {
        "backend": "ok",
        "database": "mongo",
        "database_url": "env://DATABASE_URL",
        "database_name": "env://DATABASE_NAME",
        "connection_status": status,
        "collections": collections,
    }


# Students
@app.post("/students")
async def create_student(student: Student):
    sid = create_document("student", student.model_dump())
    return {"id": sid, **student.model_dump()}


@app.get("/students")
async def list_students():
    return get_documents("student", {}, 200)


# KYC
@app.post("/kyc")
async def submit_kyc(doc: KYCDocument):
    did = create_document("kycdocument", doc.model_dump())
    return {"id": did, **doc.model_dump()}


# Proofs
@app.post("/proofs")
async def submit_proof(proof: ProofSubmission):
    pid = create_document("proofsubmission", proof.model_dump())
    return {"id": pid, **proof.model_dump()}


# Donations
@app.post("/donations/initiate")
async def initiate_donation(donation: Donation):
    # Validate ranges for INR when applicable
    if donation.currency.upper() == "INR":
        if donation.scholarship == "micro" and not (MICRO_MIN_INR <= donation.amount <= MICRO_MAX_INR):
            raise HTTPException(status_code=400, detail="Amount out of micro scholarship range")
        if donation.scholarship == "big" and not (BIG_MIN_INR <= donation.amount <= BIG_MAX_INR):
            raise HTTPException(status_code=400, detail="Amount out of big scholarship range")
    ref = create_document("donation", donation.model_dump())
    return {"status": "created", "reference": ref}


class WebhookPayload(BaseModel):
    reference: str
    event: str
    signature: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@app.post("/donations/webhook")
async def donation_webhook(payload: WebhookPayload):
    # In production verify signature and update donation status
    return {"status": "received", "reference": payload.reference}


# Blockchain
@app.post("/blockchain/record/{donation_id}")
async def record_on_chain(donation_id: str, tx_hash: str):
    # Placeholder: attach tx hash to donation
    _ = donation_id, tx_hash
    return {"status": "recorded", "donation_id": donation_id, "tx_hash": tx_hash}


# Discovery
@app.get("/discover")
async def discover_students(q: Optional[str] = None, limit: int = 50):
    flt = {}
    if q:
        flt = {"$or": [{"full_name": {"$regex": q, "$options": "i"}}, {"school_name": {"$regex": q, "$options": "i"}}]}
    return get_documents("student", flt, limit)


# Heatmap
@app.get("/heatmap")
async def heatmap():
    database = db()
    if database is None:
        return []
    pipeline = [
        {"$match": {"location.lat": {"$exists": True}}},
        {"$group": {"_id": {"lat": "$location.lat", "lng": "$location.lng"}, "count": {"$sum": 1}}},
    ]
    try:
        res = list(database["student"].aggregate(pipeline))
        out = [{"lat": r["_id"]["lat"], "lng": r["_id"]["lng"], "count": r["count"]} for r in res]
    except Exception:
        out = []
    return out


# Trust score recompute (simple placeholder)
@app.get("/trust/{student_id}")
async def trust(student_id: str):
    database = db()
    score = 0
    if database is not None:
        proofs = database["proofsubmission"].count_documents({"student_id": student_id})
        kycs = database["kycdocument"].count_documents({"student_id": student_id, "status": "verified"})
        score = min(100, 40 + proofs * 10 + kycs * 30)
    return {"student_id": student_id, "trust_score": float(score)}


# Schema info
@app.get("/schema")
async def schema():
    return {
        "collections": ["student", "kycdocument", "proofsubmission", "donation", "csrproject"],
        "scholarship_ranges": {
            "micro": [MICRO_MIN_INR, MICRO_MAX_INR],
            "big": [BIG_MIN_INR, BIG_MAX_INR],
        },
    }
