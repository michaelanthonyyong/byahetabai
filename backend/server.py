from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone

from core.db import get_client, get_db
from core.init_db import init_db
from routers.auth import router as auth_router
from routers.admin_users import router as admin_agents_router
from routers.admin_dashboard import router as admin_dashboard_router
from routers.admin_bookings import router as admin_bookings_router
from routers.admin_destinations import router as admin_destinations_router
from routers.admin_packages import router as admin_packages_router
from routers.admin_fund_requests import router as admin_fund_requests_router
from routers.admin_transactions import router as admin_transactions_router
from routers.admin_contacts import router as admin_contacts_router
from routers.admin_settings import router as admin_settings_router
from routers.admin_audit_logs import router as admin_audit_logs_router
from routers.public import router as public_router
from routers.agent import router as agent_router


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (single shared client from core.db).
client = get_client()
db = get_db()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_agents_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_bookings_router)
app.include_router(admin_destinations_router)
app.include_router(admin_packages_router)
app.include_router(admin_fund_requests_router)
app.include_router(admin_transactions_router)
app.include_router(admin_contacts_router)
app.include_router(admin_settings_router)
app.include_router(admin_audit_logs_router)
app.include_router(public_router)
app.include_router(agent_router)

# CORS — for credentialed cookies, "*" cannot coexist with allow_credentials.
# Same-origin here (frontend and /api share the preview domain), but we still
# whitelist explicit origins or fall back to a preview-domain regex.
_cors = os.environ.get("CORS_ORIGINS", "*").strip()
if _cors and _cors != "*":
    _origins = [o.strip() for o in _cors.split(",") if o.strip()]
    _origin_regex = None
else:
    _origins = []
    _origin_regex = r"https?://(localhost(:\d+)?|.*\.preview\.emergentagent\.com)"
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_origins,
    allow_origin_regex=_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_init_db():
    """Idempotent bootstrap of collections, indexes and default settings."""
    await init_db()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()