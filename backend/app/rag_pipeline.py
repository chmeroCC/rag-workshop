"""RAG pipeline implemented with LangChain v1 (LCEL) components."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone

from .config import (
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_VERSION,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    PINECONE_API_KEY,
    PINECONE_DIMENSION,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    OPENAI_TEMPERATURE,
)

logger = logging.getLogger(__name__)

# Initialisation du client Pinecone
try:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    PINE_CONE_AVAILABLE = True
    logger.info("✅ Pinecone client initialized successfully")
except Exception as e:
    logger.error(f"❌ Pinecone initialization failed: {e}")
    PINE_CONE_AVAILABLE = False
    raise

def _ensure_pinecone_index() -> None:
    """Crée l'index Pinecone s'il n'existe pas déjà."""
    if not PINE_CONE_AVAILABLE:
        raise RuntimeError("Pinecone is not available")
        
    try:
        existing_indexes = [i.name for i in pc.list_indexes()]
        if PINECONE_INDEX_NAME in existing_indexes:
            logger.info(f"✅ Pinecone index '{PINECONE_INDEX_NAME}' already exists")
            return
        
        logger.info(f"📦 Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=PINECONE_DIMENSION,
            metric="cosine",
            spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
        )
        
        # Attente que l'index soit prêt
        logger.info("⏳ Waiting for index to be ready...")
        while True:
            idx = pc.describe_index(PINECONE_INDEX_NAME)
            if idx.status["ready"]:
                break
            time.sleep(1)
        logger.info(f"✅ Pinecone index '{PINECONE_INDEX_NAME}' is ready")
        
    except Exception as e:
        logger.error(f"❌ Failed to ensure Pinecone index: {e}")
        raise

# Initialisation des modèles Azure OpenAI
try:
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_VERSION,
    )
    logger.info("✅ Azure OpenAI Embeddings initialized successfully")
    
    llm = AzureChatOpenAI(
        azure_deployment=AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_VERSION,
        temperature=OPENAI_TEMPERATURE,
    )
    logger.info("✅ Azure Chat OpenAI initialized successfully")
    
except Exception as e:
    logger.error(f"❌ Azure OpenAI initialization failed: {e}")
    raise

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    add_start_index=True,
)

def ingest_pdf(file_path: str, doc_id: Optional[str] = None) -> str:
    """
    Charge un PDF, le découpe et stocke les vecteurs dans Pinecone.
    """
    if not PINE_CONE_AVAILABLE:
        raise RuntimeError("Pinecone is not available. Please check your API key.")
    
    # S'assurer que l'index existe avant d'ingérer
    _ensure_pinecone_index()
    
    document_id = doc_id or str(uuid.uuid4())
    logger.info(f"📄 Processing PDF: {file_path} with doc_id: {document_id}")
    
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    logger.info(f"📖 Loaded {len(pages)} pages from PDF")
    
    # Ajout de métadonnées pour le filtrage
    for i, page in enumerate(pages, start=1):
        page.metadata["doc_id"] = document_id
        page.metadata["page_number"] = page.metadata.get("page", i)
    
    chunks = text_splitter.split_documents(pages)
    logger.info(f"✂️ Split into {len(chunks)} chunks")
    
    # S'assurer que chaque chunk a le doc_id
    for chunk in chunks:
        chunk.metadata.setdefault("doc_id", document_id)
    
    # Stockage dans Pinecone
    logger.info("💾 Storing vectors in Pinecone...")
    PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=PINECONE_INDEX_NAME,
        namespace=PINECONE_NAMESPACE,
    )
    logger.info("✅ PDF successfully processed and stored")
    
    return document_id

def get_retriever_for_doc(doc_id: str):
    """
    Crée un 'retriever' qui ne cherche QUE dans le document spécifié.
    """
    if not PINE_CONE_AVAILABLE:
        raise RuntimeError("Pinecone is not available. Please check your API key.")
    
    vectorstore = PineconeVectorStore.from_existing_index(
        index_name=PINECONE_INDEX_NAME,
        embedding=embeddings,
        namespace=PINECONE_NAMESPACE,
    )
    
    return vectorstore.as_retriever(
        search_kwargs={
            "k": 5,
            "filter": {"doc_id": {"$eq": doc_id}},
        }
    )

def _format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "If you cannot find the answer in the context, please say so. "
    "Keep your answers concise and accurate."
)

def build_qa_chain(doc_id: str) -> RunnableParallel:
    """
    Construit la chaîne RAG pour un document spécifique.
    """
    retriever = get_retriever_for_doc(doc_id)
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DEFAULT_SYSTEM_PROMPT),
            ("human", "Context:\n{context}\n\nQuestion: {question}"),
        ]
    )
    
    answer_chain = (
        {
            "context": retriever | RunnableLambda(_format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return RunnableParallel(
        answer=answer_chain,
        source_documents=retriever,
    )