from fastapi import FastAPI, HTTPException, Header
import httpx
from pydantic import BaseModel

app = FastAPI()

# Configuration for API endpoints and credentials
ACCESS_TOKEN_URL = "https://sam.ihsmarkit.com/sso/oauth2/access_token"
SUBMISSION_URL = "https://www.lmepassport.com/api/doc-upload-service/records/inventory/import"
CLIENT_ID = "ihsmarkit-lme-essdocs-prod-MZ5QC2zAoX"
CLIENT_SECRET = "LExOVc4Mhdit6rpRJmQbeAlW0vaInFGT"

class OWSRPayload(BaseModel):
    inventoryDate: str
    records: list

@app.post("/get-access-token")
async def get_access_token():
    """Generates an access token."""
    data = {
        "grant_type": "client_credentials",
        "scope": "openid profile email",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(ACCESS_TOKEN_URL, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch access token.")
        return response.json()

@app.post("/submit-owsr")
async def submit_owsr(payload: OWSRPayload, Authorization: str = Header(...)):
    """Submits OWSR stock data."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": Authorization
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBMISSION_URL, json=payload.dict(), headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
