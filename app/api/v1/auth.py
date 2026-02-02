import uuid
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.core.config.logging import bind_context, logger
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import (
    SessionResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.database import DatabaseService, database_service
from app.utils.auth import create_access_token, verify_token
from app.utils.sanitization import (
    sanitize_email,
    sanitize_string,
    validate_password_strength,
)
router = APIRouter()
security = HTTPBearer()




async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Dependency that validates the JWT token and returns the current user.
    """
    try:
        # Sanitize token input prevents injection attacks via headers
        token = sanitize_string(credentials.credentials)

        user_id = verify_token(token)
        if user_id is None:
            logger.warning("invalid_token_attempt")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Verify user actually exists in DB
        user_id_int = int(user_id)
        user = await database_service.get_user(user_id_int)
        
        if user is None:
            logger.warning("user_not_found_from_token", user_id=user_id_int)
            raise HTTPException(
                status_code=404,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # CRITICAL: Bind user context to structured logs.
        # Any log generated after this point will automatically include user_id.
        bind_context(user_id=user_id_int)
        return user
        
    except ValueError as ve:
        logger.error("token_validation_error", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Session:
    """
    Dependency that validates a Session-specific JWT token.
    """
    try:
        token = sanitize_string(credentials.credentials)

        session_id = verify_token(token)
        if session_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        session_id = sanitize_string(session_id)
        # Verify session exists in DB
        session = await database_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        # Bind context for logging
        bind_context(user_id=session.user_id, session_id=session.id)
        return session
    except ValueError as ve:
        raise HTTPException(status_code=422, detail="Invalid token format")

@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def register_user(request: Request, user_data: UserCreate):
    """
    Register a new user.
    """
    try:
        # 1. Sanitize & Validate
        sanitized_email = sanitize_email(user_data.email)
        password = user_data.password.get_secret_value()
        validate_password_strength(password)

        # 2. Check existence
        if await database_service.get_user_by_email(sanitized_email):
            raise HTTPException(status_code=400, detail="Email already registered")
        # 3. Create User (Hash happens inside model)
        # Note: User.hash_password is static, but we handle it in service/model logic usually.
        # Here we pass the raw password to the service which should handle hashing, 
        # or hash it here if the service expects a hash. 
        # Based on our service implementation earlier, let's hash it here:
        hashed = User.hash_password(password)
        user = await database_service.create_user(email=sanitized_email, password_hash=hashed)
        # 4. Auto-login (Mint token)
        token = create_access_token(str(user.id))
        return UserResponse(id=user.id, email=user.email, token=token)
        
    except ValueError as ve:
        logger.warning("registration_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
async def login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    grant_type: str = Form(default="password")
):
    """
    Authenticate user and return JWT token.
    """
    try:
        # Sanitize
        username = sanitize_string(username)
        password = sanitize_string(password)

        if grant_type != "password":
            raise HTTPException(status_code=400, detail="Unsupported grant type")
        # Verify User
        user = await database_service.get_user_by_email(username)
        if not user or not user.verify_password(password):
            logger.warning("login_failed", email=username)
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(str(user.id))
        
        logger.info("user_logged_in", user_id=user.id)
        return TokenResponse(
            access_token=token.access_token, 
            token_type="bearer", 
            expires_at=token.expires_at
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.post("/session", response_model=SessionResponse)
async def create_session(user: User = Depends(get_current_user)):
    """
    Create a new chat session (thread) for the authenticated user.
    """
    try:
        # Generate a secure random UUID
        session_id = str(uuid.uuid4())

        # Persist to DB
        session = await database_service.create_session(session_id, user.id)
        # Create a token specifically for this session ID
        # This token allows the Chatbot API to identify which thread to write to
        token = create_access_token(session_id)
        logger.info("session_created", session_id=session_id, user_id=user.id)
        return SessionResponse(session_id=session_id, name=session.name, token=token)
        
    except Exception as e:
        logger.error("session_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(user: User = Depends(get_current_user)):
    """
    Retrieve all historical chat sessions for the user.
    """
    sessions = await database_service.get_user_sessions(user.id)
    return [
        SessionResponse(
            session_id=s.id,
            name=s.name,
            # We re-issue tokens so the UI can resume these chats
            token=create_access_token(s.id) 
        )
        for s in sessions
    ]


