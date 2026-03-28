from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import voice, insights, pdf
from db import models
from db.database import engine

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="VoiceTrace API", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(voice.router, prefix="/api", tags=["Voice"])
app.include_router(insights.router, prefix="/api", tags=["Insights"])
app.include_router(pdf.router, prefix="/api", tags=["PDF"])

@app.get("/")
def read_root():
    return {"message": "Welcome to VoiceTrace API", "status": "online"}
