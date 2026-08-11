from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class PasswordResetRequest(BaseModel):
    email: EmailStr
    redirect_to: str | None = Field(default=None, max_length=500)


class PasswordUpdateRequest(BaseModel):
    password: str = Field(min_length=8, max_length=72)


class Session(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    expires_at: int | None = None


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None
    full_name: str | None
    role: str
    status: str
    plan_code: str


class AuthResponse(BaseModel):
    user: UserProfile
    session: Session | None = None
    email_confirmation_required: bool = False


class CurrentUser(BaseModel):
    id: str
    email: str | None
    profile: UserProfile


class UsageResponse(BaseModel):
    plan_code: str
    plan_name: str
    granted_searches: int
    used_searches: int
    remaining_searches: int


class AccountResponse(BaseModel):
    user: UserProfile
    usage: UsageResponse
