from fastapi import FastAPI, HTTPException, Header, status
import httpx
from pydantic import BaseModel, Field
import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from fastapi.middleware import Middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration for API endpoints and credentials
ACCESS_TOKEN_URL = "https://sam.ihsmarkit.com/sso/oauth2/access_token"
SUBMISSION_URL = "https://www.lmepassport.com/api/doc-upload-service/records/inventory/import"
CLIENT_ID = "ihsmarkit-lme-essdocs-prod-MZ5QC2zAoX"
CLIENT_SECRET = "LExOVc4Mhdit6rpRJmQbeAlW0vaInFGT"
REQUEST_TIMEOUT = 30  # seconds

# Custom exceptions
class TokenError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

class SubmissionError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class RateLimitError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )

# Rate limiting
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    def is_allowed(self) -> bool:
        current_time = time.time()
        # Remove requests older than 1 minute
        self.requests = [req for req in self.requests if current_time - req < 60]
        
        if len(self.requests) >= self.requests_per_minute:
            return False
            
        self.requests.append(current_time)
        return True

rate_limiter = RateLimiter()

class OWSRPayload(BaseModel):
    inventoryDate: str = Field(..., description="Date in YYYY-MM-DD format")
    records: List[Dict[str, Any]]

    @property
    def validate_date(self):
        try:
            datetime.strptime(self.inventoryDate, '%Y-%m-%d')
            return True
        except ValueError:
            raise ValueError("Incorrect date format, should be YYYY-MM-DD")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.post("/get-access-token")
async def get_access_token():
    """Generates an access token."""
    if not rate_limiter.is_allowed():
        raise RateLimitError()

    data = {
        "grant_type": "client_credentials",
        "scope": "openid profile email",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ACCESS_TOKEN_URL,
                data=data,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info("Successfully obtained access token")
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Request timed out while getting access token")
        raise TokenError("Request timed out while getting access token")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        raise TokenError(f"Failed to fetch access token: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@app.post("/submit-owsr")
async def submit_owsr(payload: OWSRPayload, Authorization: str = Header(...)):
    """Submits OWSR stock data."""
    # Validate date format
    payload.validate_date

    if not Authorization.startswith("Bearer "):
        raise TokenError("Invalid authorization header format. Must start with 'Bearer '")

    headers = {
        "Content-Type": "application/json",
        "Authorization": Authorization
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SUBMISSION_URL,
                json=payload.dict(),
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info("Successfully submitted OWSR data")
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Request timed out while submitting OWSR data")
        raise SubmissionError("Request timed out while submitting OWSR data")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        raise SubmissionError(f"Failed to submit OWSR data: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)