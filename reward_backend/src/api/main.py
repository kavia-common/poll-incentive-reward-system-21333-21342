"""
reward_backend: FastAPI app for poll incentive/reward system.

Provides:
- SSO authentication and role-based access (User/Admin)
- User endpoints: poll listing, poll response, dashboard, reward history, submit/redemption
- Admin endpoints: manage polls, weightages, ingest poll results, administer redemptions, user management, report exports
- All reward allocation and redemption business logic

OpenAPI docs at /docs.

Environment:
- Requires REWARD_DATABASE_URL in the environment (.env)
- SSO_SECRET, SSO_CLIENT_ID, and SSO_AUTH_URL must be set for SSO login
"""

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Body, Path
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
import datetime

from src.database.database import get_db
from src.database import models


# ---- SSO/OAuth2 (stub -- replace with real integration) ----

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SSO_USER_MAP = {"admin@company.com": {"username": "admin", "role": "admin"},
                "user@company.com": {"username": "user", "role": "user"}}  # Example

# PUBLIC_INTERFACE
class UserInfo(BaseModel):
    """Public user profile (for dashboard or auth context)"""
    id: int
    username: str
    email: EmailStr
    is_admin: bool

# PUBLIC_INTERFACE
class PollOut(BaseModel):
    """Poll public details."""
    id: int
    title: str
    description: Optional[str]
    created_at: datetime.datetime
    status: str
    weightage: float
    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
class PollAdminOut(PollOut):
    results_data: Optional[dict]  # Results visible to admin

class PollIn(BaseModel):
    """Payload for adding/updating Polls (admin)."""
    title: str = Field(..., description="Poll title")
    description: Optional[str] = Field(None, description="Description of poll")
    weightage: float = Field(1.0, description="Reward weightage factor for this poll")

class PollResultIn(BaseModel):
    """Admin: manual result entry."""
    results_data: dict = Field(..., description="Poll result data")

class PollResponseIn(BaseModel):
    """User submit poll response."""
    poll_id: int = Field(..., description="Poll ID")
    response_data: dict = Field(..., description="User's prediction or response details")

class PollResponseOut(BaseModel):
    """User's poll response + reward status."""
    id: int
    poll_id: int
    response_data: dict
    awarded: bool
    tokens_earned: Optional[int]
    submitted_at: datetime.datetime
    class Config:
        orm_mode = True

class RewardOut(BaseModel):
    """History of rewards earned."""
    poll_id: int
    tokens_earned: int
    awarded_at: datetime.datetime

class TokenAccountOut(BaseModel):
    """User dashboard reward account state."""
    total_tokens: int
    available_tokens: int
    updated_at: datetime.datetime

class RedemptionIn(BaseModel):
    """User triggers redemption."""
    tokens_requested: int = Field(..., gt=0, description="How many tokens to redeem")

class RedemptionLogOut(BaseModel):
    id: int
    requested_at: datetime.datetime
    tokens_redeemed: int
    status: str
    external_reference: Optional[str]
    log_data: Optional[dict]

class AdminRedemptionUpdate(BaseModel):
    status: str = Field(..., description="New redemption status")
    log_data: Optional[dict]

# --- Auth Dependencies ---

def get_user_from_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """
    Decode SSO token (stub), and fetch user from DB.
    In production, integrate with SSO, verify signature, etc.
    """
    # For now, SSO_USER_MAP as placeholder
    email = token
    user_info = SSO_USER_MAP.get(email)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing SSO token")
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if not db_user:
        # Auto provision on first use
        db_user = models.User(
            username=user_info["username"],
            email=email,
            is_admin=(user_info["role"] == "admin"),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        # Create empty TokenAccount as well
        acc = models.TokenAccount(user_id=db_user.id)
        db.add(acc)
        db.commit()
    return db_user

def require_admin(user: models.User = Depends(get_user_from_token)):
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user

# --- FastAPI App ---

app = FastAPI(
    title="Reward System API",
    description="APIs for poll reward/response, user/admin dashboards, and redemption",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and account APIs"},
        {"name": "poll", "description": "Poll and response APIs for users"},
        {"name": "reward", "description": "Reward calculation, token dashboard"},
        {"name": "redemption", "description": "Redemption workflow"},
        {"name": "admin", "description": "Admin APIs for poll and reward management"},
        {"name": "report", "description": "Admin endpoints for exporting reports"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers by group ---

user_router = APIRouter(prefix="/user", tags=["poll", "reward", "redemption"])
admin_router = APIRouter(prefix="/admin", tags=["admin", "report"])

########## User APIs ##########

# PUBLIC_INTERFACE
@user_router.get("/me", response_model=UserInfo, summary="Get my profile", tags=["auth"])
def get_my_profile(user: models.User = Depends(get_user_from_token)):
    """Fetch user profile and role."""
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
    )

# PUBLIC_INTERFACE
@user_router.get("/dashboard", response_model=TokenAccountOut, summary="Get user dashboard with token summary", tags=["reward"])
def get_my_dashboard(user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Get account balances/status for the current user."""
    acc = db.query(models.TokenAccount).filter(models.TokenAccount.user_id == user.id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Token account not found")
    return acc

# PUBLIC_INTERFACE
@user_router.get("/polls", response_model=List[PollOut], summary="List and describe all active polls")
def get_active_polls(user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Fetch all open polls, sorted by newest first."""
    polls = db.query(models.Poll).filter(models.Poll.status == "open").order_by(models.Poll.created_at.desc()).all()
    return polls

# PUBLIC_INTERFACE
@user_router.get("/rewards", response_model=List[RewardOut], summary="Get my reward history")
def get_my_rewards(user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Show reward history for the user."""
    rewards = db.query(models.Reward).filter(models.Reward.user_id == user.id).order_by(models.Reward.awarded_at.desc()).all()
    return [
        RewardOut(
            poll_id=r.poll_response.poll_id,
            tokens_earned=r.tokens_earned,
            awarded_at=r.awarded_at,
        ) for r in rewards
    ]

@user_router.get("/responses", response_model=List[PollResponseOut], summary="List my poll responses and awarded status")
def get_my_responses(user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """List all poll responses and reward status for this user."""
    responses = db.query(models.PollResponse).filter(models.PollResponse.user_id == user.id).all()
    result = []
    for resp in responses:
        reward = None
        tokens_earned = None
        if resp.awarded and resp.reward:
            reward = resp.reward
            tokens_earned = reward.tokens_earned
        result.append(
            PollResponseOut(
                id=resp.id,
                poll_id=resp.poll_id,
                response_data=resp.response_data,
                awarded=resp.awarded,
                tokens_earned=tokens_earned,
                submitted_at=resp.submitted_at,
            )
        )
    return result

# PUBLIC_INTERFACE
@user_router.post("/submit_response", status_code=201, summary="Submit response to a poll")
def submit_poll_response(data: PollResponseIn, user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """
    Submit a response to a poll (one per user per poll).
    """
    poll = db.query(models.Poll).filter(models.Poll.id == data.poll_id, models.Poll.status == "open").first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found or closed")
    existing = db.query(models.PollResponse).filter(models.PollResponse.user_id == user.id, models.PollResponse.poll_id == poll.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already responded to this poll")
    response = models.PollResponse(
        user_id=user.id,
        poll_id=data.poll_id,
        response_data=data.response_data,
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return {"response_id": response.id, "status": "recorded"}

# PUBLIC_INTERFACE
@user_router.post("/redeem", response_model=RedemptionLogOut, status_code=201, summary="Redeem tokens for a reward", tags=["redemption"])
def request_redemption(data: RedemptionIn, user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """User requests to redeem tokens for a reward."""
    acc = db.query(models.TokenAccount).filter(models.TokenAccount.user_id == user.id).with_for_update().first()
    if not acc or acc.available_tokens < data.tokens_requested:
        raise HTTPException(status_code=400, detail="Insufficient available tokens")
    # Deduct tokens pre-emptively, status 'pending'
    acc.available_tokens -= data.tokens_requested
    red = models.RedemptionLog(
        user_id=user.id,
        tokens_redeemed=data.tokens_requested,
        status="pending",
        external_reference=None,
        log_data=None,
    )
    db.add(red)
    db.commit()
    db.refresh(red)
    return red

@user_router.get("/redemptions", response_model=List[RedemptionLogOut], summary="Get my redemption requests/logs", tags=["redemption"])
def get_my_redemptions(user: models.User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Redemption log for current user."""
    logs = db.query(models.RedemptionLog).filter(models.RedemptionLog.user_id == user.id).order_by(models.RedemptionLog.requested_at.desc()).all()
    return logs

########## Admin APIs ##########

@admin_router.get("/polls", response_model=List[PollAdminOut], summary="Admin: list all polls")
def list_all_polls(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin: get full poll info, including results_data."""
    polls = db.query(models.Poll).order_by(models.Poll.created_at.desc()).all()
    return polls

@admin_router.post("/polls", response_model=PollAdminOut, status_code=201, summary="Admin: create a poll")
def create_poll(payload: PollIn, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin: create new poll."""
    poll = models.Poll(
        title=payload.title,
        description=payload.description,
        weightage=payload.weightage,
    )
    db.add(poll)
    db.commit()
    db.refresh(poll)
    return poll

@admin_router.patch("/polls/{poll_id}", response_model=PollAdminOut, summary="Admin: update poll (title, desc, weightage)")
def update_poll(
    poll_id: int = Path(...), payload: PollIn = Body(...),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db)):
    """Admin: edit a poll."""
    poll = db.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    poll.title = payload.title
    poll.description = payload.description
    poll.weightage = payload.weightage
    db.commit()
    db.refresh(poll)
    return poll

@admin_router.post("/polls/{poll_id}/results", response_model=PollAdminOut, summary="Admin: ingest manual poll results and trigger rewards")
def ingest_poll_results(
    poll_id: int, data: PollResultIn,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Post poll admin result & compute user rewards:
    - updates poll.result_data
    - marks poll as closed
    - allocates tokens to users based on accuracy (calls _assign_rewards)
    """
    poll = db.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll or poll.status != "open":
        raise HTTPException(status_code=404, detail="Poll not found or already closed")
    poll.results_data = data.results_data
    poll.status = "closed"
    db.commit()
    # Trigger reward computation
    _assign_rewards(poll.id, db)
    db.refresh(poll)
    return poll

# PUBLIC_INTERFACE
def _assign_rewards(poll_id: int, db: Session):
    """
    Core reward/token logic (stub/scoring rule below):
    - Iterate over all responses for poll.
    - Calculate accuracy and allocate tokens using poll.weightage.
    - Mark as awarded, create Reward entry, update TokenAccount.
    """
    # For demo: assign 10 * weightage tokens for each response
    poll = db.query(models.Poll).filter(models.Poll.id == poll_id).first()
    responses = db.query(models.PollResponse).filter(models.PollResponse.poll_id == poll_id, models.PollResponse.awarded == False).all()
    for resp in responses:
        tokens = int(10 * poll.weightage)  # Replace with real accuracy scoring based on resp.response_data and poll.results_data
        reward = models.Reward(
            user_id=resp.user_id,
            poll_response_id=resp.id,
            tokens_earned=tokens,
        )
        resp.awarded = True
        acc = db.query(models.TokenAccount).filter(models.TokenAccount.user_id == resp.user_id).with_for_update().first()
        if acc:
            acc.total_tokens += tokens
            acc.available_tokens += tokens
        db.add(reward)
    db.commit()

@admin_router.get("/users", response_model=List[UserInfo], summary="Admin: list users and roles")
def admin_list_users(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """List all users with profiles."""
    users = db.query(models.User).all()
    return [
        UserInfo(
            id=u.id,
            username=u.username,
            email=u.email,
            is_admin=u.is_admin,
        ) for u in users
    ]

@admin_router.get("/redemptions", response_model=List[RedemptionLogOut], summary="Admin: list all redemptions")
def list_redemptions(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """Show all redemption logs."""
    logs = db.query(models.RedemptionLog).order_by(models.RedemptionLog.requested_at.desc()).all()
    return logs

@admin_router.patch("/redemptions/{redemption_id}", response_model=RedemptionLogOut, summary="Admin: update redemption status/log")
def update_redemption(redemption_id: int, data: AdminRedemptionUpdate, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """Update (complete/cancel/retry) a redemption (external info, status)."""
    red = db.query(models.RedemptionLog).filter(models.RedemptionLog.id == redemption_id).first()
    if not red:
        raise HTTPException(status_code=404, detail="Redemption not found")
    old_status = red.status
    red.status = data.status
    red.log_data = data.log_data
    if old_status == "pending" and data.status == "cancelled":
        # Refund tokens if cancelled
        acc = db.query(models.TokenAccount).filter(models.TokenAccount.user_id == red.user_id).with_for_update().first()
        if acc:
            acc.available_tokens += red.tokens_redeemed
    db.commit()
    db.refresh(red)
    return red

# --- Include routers ---

app.include_router(user_router)
app.include_router(admin_router)

# --- Health check ---

@app.get("/", summary="Health Check", tags=["auth"])
def health_check():
    """Simple health check endpoint."""
    return {"message": "Healthy"}

