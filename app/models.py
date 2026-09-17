from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# AUTH
# =============================================================================
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# =============================================================================
# PROFILE / ONBOARDING  (the 7-question flow)
# =============================================================================
class Phone(BaseModel):
    country_code: str = Field(default="+44", max_length=6)
    number: str = Field(max_length=20)


class Profile(BaseModel):
    """Everything the onboarding flow collects. All optional so a partially
    completed onboarding can still be saved."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    company: Optional[str] = Field(default=None, max_length=160)
    role: Optional[str] = None                 # Embedded / ML Engineer / ...
    role_other: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[Phone] = None
    region: Optional[str] = Field(default=None, max_length=80)   # country
    targets: List[str] = Field(default_factory=list)             # ARM Cortex-M, ESP32...
    purpose: Optional[str] = None              # Production / Prototype / Research / Hobby
    purpose_detail: Optional[str] = Field(default=None, max_length=300)


class OnboardingSubmit(Profile):
    """Body of POST /me/onboarding — the profile plus silently captured meta."""
    locale: Optional[str] = Field(default=None, max_length=20)
    referrer: Optional[str] = Field(default=None, max_length=500)
    utm: dict = Field(default_factory=dict)


class GithubPublic(BaseModel):
    """GitHub link status. The access token is NEVER returned."""
    linked: bool = False
    login: Optional[str] = None
    avatar_url: Optional[str] = None
    scope: Optional[str] = None        # "public_repo" or "repo" (incl. private)
    linked_at: Optional[datetime] = None


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    plan: str = "free"
    profile: Profile = Field(default_factory=Profile)
    onboarding_completed: bool = False
    github: GithubPublic = Field(default_factory=GithubPublic)
    credits: int = 0                   # unlock credits bought but unspent
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# =============================================================================
# CONVERSIONS
# =============================================================================
SourceKind = Literal["upload", "github", "sample"]


class ConversionSource(BaseModel):
    kind: SourceKind = "upload"
    filename: Optional[str] = None
    blob_key: Optional[str] = None     # where the .onnx lives in blob storage
    # github-sourced models:
    repo: Optional[str] = None         # "owner/name"
    ref: Optional[str] = None          # branch or commit sha
    path: Optional[str] = None         # path to the .onnx inside the repo


class ConversionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=60)
    quant: str = "int8"
    goal: str = "size"
    source: ConversionSource = Field(default_factory=ConversionSource)


class ArtifactInfo(BaseModel):
    """Metadata about the generated C. The blob key itself is never exposed —
    downloads go through a short-lived signed URL from /artifacts/{id}/download."""
    ready: bool = False
    files: List[str] = Field(default_factory=list)     # ["model.c", "model.h"]
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    line_count: Optional[int] = None


class ConversionPublic(BaseModel):
    id: str
    name: str
    target: str
    quant: str
    goal: str
    status: str                        # queued|building|done|failed
    flash: Optional[str] = None
    ram: Optional[str] = None
    error: Optional[str] = None
    source: ConversionSource = Field(default_factory=ConversionSource)
    artifact: ArtifactInfo = Field(default_factory=ArtifactInfo)
    unlocked: bool = False             # has the user paid / is it free-tier?
    created_at: datetime


# =============================================================================
# BILLING  (artifact purchase)
# =============================================================================
OrderKind = Literal["single_unlock", "credit_pack", "plan_upgrade"]
OrderStatus = Literal["pending", "paid", "failed", "refunded"]


class CheckoutCreate(BaseModel):
    kind: OrderKind = "single_unlock"
    conversion_id: Optional[str] = None   # required for single_unlock
    quantity: int = Field(default=1, ge=1, le=100)


class OrderPublic(BaseModel):
    id: str
    kind: OrderKind
    conversion_id: Optional[str] = None
    amount_cents: int
    currency: str = "usd"
    status: OrderStatus
    checkout_url: Optional[str] = None
    created_at: datetime


class DownloadGrant(BaseModel):
    """Short-lived signed URL the browser uses to fetch the artifact."""
    url: str
    expires_at: datetime
    filename: str


# =============================================================================
# GITHUB
# =============================================================================
class GithubRepo(BaseModel):
    full_name: str
    private: bool
    default_branch: str
    updated_at: Optional[datetime] = None


class GithubImport(BaseModel):
    repo: str = Field(min_length=3, max_length=140)   # "owner/name"
    path: str = Field(min_length=1, max_length=400)   # "models/mnist.onnx"
    ref: Optional[str] = None                         # defaults to default branch
