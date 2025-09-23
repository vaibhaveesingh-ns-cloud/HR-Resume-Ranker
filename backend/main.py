from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import tempfile
import zipfile
from typing import List, Dict, Any
import asyncio
from dotenv import load_dotenv

from services.openai_service import ChatGPTService
from models.schemas import RankingResponse, Candidate, RejectedCandidate

# Load environment variables
load_dotenv()

app = FastAPI(
    title="HR Resume Ranker API",
    description="AI-powered resume ranking system using ChatGPT",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM provider service (ChatGPT)
llm_service = ChatGPTService()

@app.get("/")
async def root():
    return {"message": "HR Resume Ranker API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "HR Resume Ranker API"}

@app.post("/api/rank-resumes", response_model=RankingResponse)
async def rank_resumes(
    job_description: str = Form(...),
    resume_file: UploadFile = File(...)
):
    """
    Rank resumes based on job description and uploaded ZIP file containing PDFs
    """
    try:
        # Validate file type
        if not resume_file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are allowed")
        
        # Create temporary file to store uploaded ZIP
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = await resume_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Process resumes using ChatGPT service
            result = await llm_service.rank_resumes(job_description, temp_file_path)
            
            return RankingResponse(
                ranked_candidates=result["ranked"],
                rejected_candidates=result["rejected"],
                total_processed=len(result["ranked"]) + len(result["rejected"])
            )
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing resumes: {str(e)}")

@app.post("/api/rank-resumes-stream")
async def rank_resumes_stream(
    job_description: str = Form(...),
    resume_file: UploadFile = File(...)
):
    """
    Stream resume ranking progress (for future WebSocket implementation)
    """
    # This endpoint can be extended to support real-time progress updates
    return await rank_resumes(job_description, resume_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
