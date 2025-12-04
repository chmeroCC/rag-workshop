import os
import shutil
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .rag_pipeline import ingest_pdf, build_qa_chain

app = FastAPI(
    title="RAG Chatbot avec Azure OpenAI",
    description="API pour chatbot RAG utilisant Azure OpenAI et Pinecone",
    version="1.0.0"
)

# ⚠️ CONFIGURATION CORS ESSENTIELLE ⚠️
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend Next.js
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Tous les headers
)

# --- Modèles de données (Schemas) ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    doc_id: str
    question: str
    history: Optional[List[ChatMessage]] = None

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[dict]] = None

class UploadResponse(BaseModel):
    doc_id: str
    message: str
    filename: str

class HealthResponse(BaseModel):
    status: str
    message: str

# --- Endpoints ---

@app.get("/")
async def root():
    """Endpoint racine pour vérifier que l'API fonctionne."""
    return {
        "message": "Bienvenue sur le RAG Chatbot avec Azure OpenAI!",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "upload": "/upload-pdf",
            "chat": "/chat"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de l'état de l'API."""
    return HealthResponse(
        status="healthy",
        message="API RAG Chatbot est opérationnelle avec Azure OpenAI"
    )

@app.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Endpoint pour uploader et ingérer un PDF."""
    
    # Validation du type de fichier
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Le fichier doit être un PDF (application/pdf)"
        )
    
    # Création du dossier temporaire
    temp_dir = "tmp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Génération d'un nom de fichier unique
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(temp_dir, unique_filename)
    
    try:
        # Sauvegarde temporaire du fichier
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Validation que le fichier n'est pas vide
        if os.path.getsize(file_path) == 0:
            raise HTTPException(status_code=400, detail="Le fichier PDF est vide")
        
        # Appel à notre pipeline d'ingestion
        doc_id = ingest_pdf(file_path)
        
        return UploadResponse(
            doc_id=doc_id,
            message="PDF traité et ingéré avec succès dans Azure OpenAI + Pinecone",
            filename=file.filename
        )
        
    except Exception as e:
        error_message = f"Erreur lors du traitement du PDF: {str(e)}"
        if "PDF" in str(e) and "corrupt" in str(e).lower():
            error_message = "Le fichier PDF semble corrompu ou invalide"
        
        raise HTTPException(status_code=500, detail=error_message)
        
    finally:
        # Nettoyage du fichier temporaire
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/chat", response_model=ChatResponse)
async def chat_with_doc(request: ChatRequest):
    """Endpoint pour poser une question sur un document."""
    
    # Validation des paramètres
    if not request.doc_id or not request.doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id est requis")
    
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="question est requise")
    
    try:
        # Construction de la chaîne QA
        qa_chain = build_qa_chain(request.doc_id)
        
        # Exécution de la chaîne RAG
        result = qa_chain.invoke(request.question)
        answer = result["answer"]
        
        # Extraction et formatage des sources pour citation
        sources = []
        for doc in result.get("source_documents", []):
            source_info = {
                "page_number": doc.metadata.get("page_number", "N/A"),
                "snippet": doc.page_content[:250] + ("..." if len(doc.page_content) > 250 else ""),
                "doc_id": doc.metadata.get("doc_id", "N/A")
            }
            sources.append(source_info)
        
        return ChatResponse(answer=answer, sources=sources)
        
    except Exception as e:
        error_detail = f"Erreur lors de la génération de la réponse: {str(e)}"
        
        # Gestion d'erreurs spécifiques
        if "index" in str(e).lower() or "not found" in str(e).lower():
            error_detail = f"Document avec doc_id '{request.doc_id}' non trouvé. Assurez-vous que le document a été correctement uploadé."
        elif "timeout" in str(e).lower():
            error_detail = "Délai d'attente dépassé lors de la communication avec Azure OpenAI. Veuillez réessayer."
        
        raise HTTPException(status_code=500, detail=error_detail)

# Gestionnaire d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Gestionnaire d'erreurs global pour toutes les exceptions non gérées."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Une erreur interne est survenue: {str(exc)}",
            "type": "internal_server_error"
        }
    )

# Point d'entrée pour l'exécution directe
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )