import os
from dotenv import load_dotenv

load_dotenv()

# Configuration Azure OpenAI
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_VERSION = os.getenv("AZURE_OPENAI_VERSION", "2024-02-01")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Configuration Pinecone
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "azure-openai-rag-index")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE")
PINECONE_DIMENSION = int(os.getenv("PINECONE_DIMENSION", "1536"))

# Paramètres de modèle
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

# Vérifications
required_vars = {
    "AZURE_OPENAI_KEY": AZURE_OPENAI_KEY,
    "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
    "AZURE_OPENAI_DEPLOYMENT": AZURE_OPENAI_DEPLOYMENT,
    "PINECONE_API_KEY": PINECONE_API_KEY,
}

missing_vars = [var for var, value in required_vars.items() if not value]

if missing_vars:
    raise RuntimeError(
        f"Configuration manquante: {', '.join(missing_vars)}. "
        "Veuillez vérifier votre fichier .env"
    )