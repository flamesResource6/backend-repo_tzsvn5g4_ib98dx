import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Service, Booking

app = FastAPI(title="Car Home Services API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Car Home Services API running"}

@app.get("/api/services", response_model=List[Service])
def list_services():
    """Return active services from DB. Seed defaults if collection empty."""
    try:
        services = list(db["service"].find({"is_active": True})) if db else []
        if not services and db:
            seed = [
                {"name": "Car Wash", "description": "Exterior & interior cleaning", "base_price": 25.0, "duration_minutes": 60, "is_active": True},
                {"name": "Small Repair", "description": "Minor fixes and adjustments", "base_price": 40.0, "duration_minutes": 90, "is_active": True},
                {"name": "Tyre Puncture", "description": "On-site puncture repair or spare change", "base_price": 15.0, "duration_minutes": 30, "is_active": True},
                {"name": "General Servicing", "description": "Basic fluids, filters, inspection", "base_price": 70.0, "duration_minutes": 180, "is_active": True}
            ]
            db["service"].insert_many(seed)
            services = list(db["service"].find({"is_active": True}))
        # Convert ObjectId to string and fit model
        def convert(doc):
            doc = {**doc}
            doc.pop("_id", None)
            return Service(**doc)
        return [convert(s) for s in services]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bookings")
def create_booking(booking: Booking):
    """Create a booking request and store in DB"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        bid = create_document("booking", booking)
        return {"id": bid, "status": booking.status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bookings")
def list_bookings(status: Optional[str] = None):
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        query = {"status": status} if status else {}
        docs = get_documents("booking", query, limit=100)
        for d in docs:
            d["_id"] = str(d.get("_id"))
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
