"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

# Example schemas (you can keep or ignore in your app flows)
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Car Home Services app schemas
# --------------------------------------------------

ServiceType = Literal[
    "Car Wash",
    "Small Repair",
    "Tyre Puncture",
    "General Servicing"
]

class Service(BaseModel):
    """
    Services catalog schema
    Collection: "service"
    """
    name: ServiceType = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="What this service covers")
    base_price: float = Field(..., ge=0, description="Starting price")
    duration_minutes: int = Field(..., ge=15, le=480, description="Typical duration")
    is_active: bool = Field(True, description="Whether service is currently offered")

class Booking(BaseModel):
    """
    Customer booking requests
    Collection: "booking"
    """
    customer_name: str = Field(..., description="Customer full name")
    phone: str = Field(..., min_length=6, max_length=20, description="Contact number")
    address: str = Field(..., description="Service address")
    vehicle_make: str = Field(..., description="Vehicle make")
    vehicle_model: str = Field(..., description="Vehicle model")
    service_name: ServiceType = Field(..., description="Selected service")
    preferred_date: str = Field(..., description="Preferred date (YYYY-MM-DD)")
    preferred_time: str = Field(..., description="Preferred time (HH:MM)")
    notes: Optional[str] = Field(None, description="Additional details")
    status: Literal["pending", "confirmed", "completed", "cancelled"] = Field(
        "pending", description="Booking status"
    )
