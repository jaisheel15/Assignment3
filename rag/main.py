from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

import dotenv
import os

dotenv.load_dotenv()

# Global state for vector store and retriever
_vector_store = None
_retriever = None
_embeddings = None

# Configuration constants
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PERSIST_DIR = "./chroma_db"
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.7
RETRIEVER_K = 15

# Get API key from environment
api_key = os.getenv("GROQ_API_KEY")


def get_embeddings():
    """Get or create embeddings instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
    return _embeddings


def create_vector_store(documents):
    """Create a new Chroma vector store from documents."""
    global _vector_store, _retriever
    
    # Split documents into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(documents)
    
    # Get embeddings
    embeddings = get_embeddings()
    
    # Create vector store
    _vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    # Create retriever
    _retriever = _vector_store.as_retriever(
        search_kwargs={"k": RETRIEVER_K}
    )
    
    return _vector_store, _retriever


def load_from_directory(directory_path="./data/"):
    """Load all PDF documents from a directory."""
    loader = DirectoryLoader(
        path=directory_path,
        glob="**/*.pdf",
        show_progress=True,
        loader_cls=PyMuPDFLoader,
    )
    return loader.load()

def dense_retrieval(query):
    """Retrieve relevant documents for a query."""
    global _retriever
    if _retriever is None:
        raise RuntimeError("Retriever not initialized. Please upload a document first.")
    return _retriever.invoke(query)


def build_context(docs):
    """Build context string from retrieved documents."""
    context = ""
    for i, doc in enumerate(docs, 1):
        context += f"\n--- Document {i} ---\n{doc.page_content}\n"
    return context


def rag_pipeline(user_query):
    """Complete RAG pipeline: retrieve and generate response."""
    if _retriever is None:
        raise RuntimeError("Retriever not initialized. Please upload a document first.")
    
    # Step 1: Dense Retrieval
    retrieved_docs = dense_retrieval(user_query)
    
    # Step 2: Build Context
    context = build_context(retrieved_docs)
    
    # Step 3: Generate Response with Groq LLM
    llm = ChatGroq(
        api_key=api_key,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE
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


def initialize_from_directory(directory_path="./data/"):
    """Initialize the RAG system by loading all PDFs from a directory."""
    print(f"📂 Loading documents from {directory_path}...")
    docs = load_from_directory(directory_path)
    print(f"✓ Loaded {len(docs)} documents")
    
    create_vector_store(docs)
    print(f"✓ Vector store created and persisted to {CHROMA_PERSIST_DIR}")


def main():
    """Main function for standalone testing."""
    print("=" * 60)
    print("RAG SYSTEM - Document Question Answering")
    print("=" * 60)
    
    try:
        # Initialize from directory
        initialize_from_directory()
        
        # Example queries
        queries = [
            "What is the main topic of the documents?",
            "Provide a summary of the key information.",
            "What are the most important findings?"
        ]
        
        for query in queries:
            try:
                print(f"\n❓ Question: {query}")
                answer = rag_pipeline(query)
                print(f"\n✅ Answer: {answer}")
                print("\n" + "-" * 60)
            except Exception as e:
                print(f"❌ Error processing query '{query}': {str(e)}")
                print("-" * 60)
    except Exception as e:
        print(f"❌ Initialization error: {str(e)}")
        print("Please ensure:")
        print("  1. PDF files exist in the ./data/ directory")
        print("  2. Environment variables are properly set")
        print("  3. Required dependencies are installed")


if __name__ == "__main__":
    main()

