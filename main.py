import os
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
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

# -----------------------------
# Pricing & Service Area Config
# -----------------------------
DEFAULT_SERVICE_AREA = {
    "lat": float(os.getenv("SERVICE_AREA_LAT", "28.6139")),  # New Delhi (demo)
    "lng": float(os.getenv("SERVICE_AREA_LNG", "77.2090")),
    "radius_km": float(os.getenv("SERVICE_AREA_RADIUS_KM", "25")),
}

PRICING_PACKAGES: Dict[str, List[Dict[str, Any]]] = {
    "Car Wash": [
        {"name": "Basic", "multiplier": 1.0, "desc": "Exterior wash"},
        {"name": "Premium", "multiplier": 1.4, "desc": "Exterior + interior"},
        {"name": "Detailing", "multiplier": 2.0, "desc": "Deep clean & wax"},
    ],
    "Small Repair": [
        {"name": "Standard", "multiplier": 1.0, "desc": "Minor fixes"},
        {"name": "Extended", "multiplier": 1.5, "desc": "Includes parts upto $20"},
    ],
    "Tyre Puncture": [
        {"name": "Patch", "multiplier": 1.0, "desc": "Puncture patch/on-spot"},
        {"name": "Spare Change", "multiplier": 1.2, "desc": "Spare wheel change"},
    ],
    "General Servicing": [
        {"name": "Basic", "multiplier": 1.0, "desc": "Inspection & fluids"},
        {"name": "Plus", "multiplier": 1.3, "desc": "Filters included"},
        {"name": "Complete", "multiplier": 1.8, "desc": "Full service"},
    ],
}

PRICING_ADDONS: List[Dict[str, Any]] = [
    {"code": "pickup_drop", "label": "Pick-up & Drop", "price": 8.0},
    {"code": "sanitization", "label": "Interior Sanitization", "price": 10.0},
    {"code": "engine_check", "label": "Engine Health Check", "price": 12.0},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def compute_quote(service_doc: dict, package_name: Optional[str], selected_addons: Optional[List[str]]) -> Dict[str, Any]:
    base_price = service_doc.get("base_price", 0)
    svc_name = service_doc.get("name")
    packages = PRICING_PACKAGES.get(svc_name, [])
    multiplier = 1.0
    applied_package = None
    if package_name:
        for p in packages:
            if p["name"] == package_name:
                multiplier = float(p.get("multiplier", 1.0))
                applied_package = p
                break
    addons_price = 0.0
    applied_addons = []
    selected = selected_addons or []
    for code in selected:
        addon = next((a for a in PRICING_ADDONS if a["code"] == code), None)
        if addon:
            addons_price += float(addon["price"])
            applied_addons.append(addon)
    subtotal = base_price * multiplier + addons_price
    return {
        "base_price": base_price,
        "multiplier": multiplier,
        "package": applied_package,
        "addons": applied_addons,
        "total": round(subtotal, 2),
    }


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
        def convert(doc):
            doc = {**doc}
            doc.pop("_id", None)
            return Service(**doc)
        return [convert(s) for s in services]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pricing")
def get_pricing():
    try:
        services = list(db["service"].find({"is_active": True})) if db else []
        for s in services:
            s["_id"] = str(s.get("_id"))
            s["packages"] = PRICING_PACKAGES.get(s.get("name"), [])
        return {"services": services, "addons": PRICING_ADDONS}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quote")
def quote(payload: Dict[str, Any]):
    try:
        service_name = payload.get("service_name")
        package_name = payload.get("package_name")
        selected_addons = payload.get("selected_addons", [])
        lat = payload.get("latitude")
        lng = payload.get("longitude")

        if db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        svc = db["service"].find_one({"name": service_name})
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")
        price_breakdown = compute_quote(svc, package_name, selected_addons)

        inside_area = True
        distance_km = None
        if lat is not None and lng is not None:
            distance_km = haversine_km(DEFAULT_SERVICE_AREA["lat"], DEFAULT_SERVICE_AREA["lng"], float(lat), float(lng))
            inside_area = distance_km <= DEFAULT_SERVICE_AREA["radius_km"]
        return {
            "total": price_breakdown["total"],
            "breakdown": price_breakdown,
            "service_area": {
                "center": DEFAULT_SERVICE_AREA,
                "inside": inside_area,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/service-area")
def service_area():
    return DEFAULT_SERVICE_AREA


@app.post("/api/check-location")
def check_location(payload: Dict[str, Any]):
    try:
        lat = float(payload.get("latitude"))
        lng = float(payload.get("longitude"))
        distance_km = haversine_km(DEFAULT_SERVICE_AREA["lat"], DEFAULT_SERVICE_AREA["lng"], lat, lng)
        return {
            "inside": distance_km <= DEFAULT_SERVICE_AREA["radius_km"],
            "distance_km": round(distance_km, 2),
            "center": DEFAULT_SERVICE_AREA,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid coordinates: {e}")


@app.post("/api/bookings")
def create_booking(booking: Booking):
    """Create a booking request and store in DB"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        # Ensure quoted_price present - compute if not
        svc = db["service"].find_one({"name": booking.service_name})
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")
        quoted_price = booking.quoted_price
        if quoted_price is None:
            breakdown = compute_quote(svc, booking.package_name, booking.selected_addons)
            quoted_price = breakdown["total"]
        # Optionally enforce service area if coordinates present
        if booking.latitude is not None and booking.longitude is not None:
            distance_km = haversine_km(DEFAULT_SERVICE_AREA["lat"], DEFAULT_SERVICE_AREA["lng"], float(booking.latitude), float(booking.longitude))
            if distance_km > DEFAULT_SERVICE_AREA["radius_km"]:
                raise HTTPException(status_code=400, detail="Address is outside service area")
        # Persist
        data = booking.model_dump()
        data["quoted_price"] = quoted_price
        bid = create_document("booking", data)
        return {"id": bid, "status": booking.status, "quoted_price": quoted_price}
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
        docs = get_documents("booking", query, limit=200)
        # Sort newest first if timestamps exist
        docs.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        for d in docs:
            d["_id"] = str(d.get("_id"))
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/bookings/{booking_id}/status")
def update_booking_status(booking_id: str, payload: Dict[str, Any]):
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        new_status = payload.get("status")
        if new_status not in ["pending", "confirmed", "completed", "cancelled"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        res = db["booking"].update_one({"_id": ObjectId(booking_id)}, {"$set": {"status": new_status}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"id": booking_id, "status": new_status}
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
