from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import tempfile
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

import dotenv

dotenv.load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="RAG API", version="1.0.0")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for vector store and retriever
vector_store = None
retriever = None
current_file_path = None

api_key = os.getenv("groq_api_key")

# Pydantic models
class QueryRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    status: str


class UploadResponse(BaseModel):
    message: str
    status: str
    file_name: str


def build_context(docs):
    """Build context string from retrieved documents."""
    context = ""
    for i, doc in enumerate(docs, 1):
        context += f"\n--- Document {i} ---\n{doc.page_content}\n"
    return context


def dense_retrieval(query: str):
    """Retrieve documents using the vector store."""
    if retriever is None:
        raise Exception("No documents indexed. Please upload a PDF first.")
    return retriever.invoke(query)


def rag_pipeline(user_query: str):
    """Complete RAG pipeline: retrieve and generate."""
    
    # Step 1: Dense Retrieval
    retrieved_docs = dense_retrieval(user_query)
    
    if not retrieved_docs:
        return "No relevant documents found for your query."
    
    # Step 2: Build Context
    context = build_context(retrieved_docs)
    
    # Step 3: Generate Response with Groq LLM
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.7
    )
    
    system_prompt = """You are a knowledgeable AI assistant. Answer questions based on the provided context. 
If the answer is not available in the context, clearly state that you don't have enough information.
Be concise and accurate in your response."""
    
    messages = [
        ("system", system_prompt),
        ("human", f"Context:\n{context}\n\nQuestion: {user_query}")
    ]
    
    response = llm.invoke(messages)
    
    return response.content


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "RAG API is running", "version": "1.0.0"}


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF file and create a vector store."""
    global vector_store, retriever, current_file_path
    
    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        # Save uploaded file
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        current_file_path = file_path
        
        # Load PDF
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
        
        if not docs:
            raise Exception("No documents found in PDF")
        
        # Split documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150
        )
        chunks = splitter.split_documents(docs)
        
        # Create embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Create vector store
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory="./chroma_db"
        )
        
        retriever = vector_store.as_retriever(search_kwargs={"k": 15})
        
        return UploadResponse(
            message=f"Successfully uploaded and indexed {file.filename}",
            status="success",
            file_name=file.filename
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error uploading file: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: QueryRequest):
    """Send a query and get an answer from the RAG system."""
    try:
        if retriever is None:
            raise Exception("No documents indexed. Please upload a PDF first.")
        
        answer = rag_pipeline(request.query)
        
        return ChatResponse(
            answer=answer,
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing query: {str(e)}")


@app.get("/status")
async def status():
    """Get the current status of the RAG system."""
    return {
        "has_documents": retriever is not None,
        "current_file": current_file_path or "None",
        "status": "ready" if retriever else "waiting_for_upload"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
