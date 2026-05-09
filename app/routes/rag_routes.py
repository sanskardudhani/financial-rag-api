from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pypdf import PdfReader

from app.database import get_db
from app.models import Document, User
from app.schemas import SearchSchema
from app.auth import get_current_user
import app.rag as rag

router = APIRouter()


def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or plain text file."""
    if file_path.endswith(".pdf"):
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"PDF read error: {e}")
            return ""
    else:
        # try reading as plain text
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            print(f"File read error: {e}")
            return ""


@router.post("/rag/index-document")
def index_document(
    document_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reads the uploaded file → extracts text → splits into chunks
    → generates embeddings → stores in Qdrant
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.is_indexed:
        return {"message": "Document already indexed"}

    # extract text
    text = extract_text_from_file(doc.file_path)
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract text. Make sure it's a readable PDF or TXT file."
        )

    # store in Qdrant
    chunk_count = rag.store_document(
        doc_id=doc.id,
        text=text,
        title=doc.title,
        company_name=doc.company_name,
        doc_type=doc.document_type
    )

    # mark as indexed
    doc.is_indexed = True
    db.commit()

    return {
        "message":      "Document indexed successfully",
        "document_id":  document_id,
        "chunks_stored": chunk_count
    }


@router.delete("/rag/remove-document/{document_id}")
def remove_from_index(
    document_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actually removes document embeddings from Qdrant."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    rag.remove_document(document_id)

    doc.is_indexed = False
    db.commit()

    return {"message": f"Embeddings removed for document {document_id}"}


@router.post("/rag/search")
def semantic_search(
    data: SearchSchema,
    current_user: User = Depends(get_current_user)
):
    """
    Semantic search pipeline:
    Query → Embed → Qdrant top 20 → Flashrank rerank → Return top 5
    """
    results = rag.search_documents(query=data.query, top_k=data.top_k)

    if not results:
        return {"query": data.query, "results": []}

    return {
        "query":   data.query,
        "results": results
    }


@router.get("/rag/context/{document_id}")
def get_document_context(
    document_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all stored chunks for a document from Qdrant."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.is_indexed:
        raise HTTPException(
            status_code=400,
            detail="Document not indexed yet. Call POST /rag/index-document first."
        )

    chunks = rag.get_context(document_id)

    return {
        "document_id": document_id,
        "title":       doc.title,
        "total_chunks": len(chunks),
        "chunks":      chunks
    }

@router.post("/rag/ask")
def ask_question(
    data: SearchSchema,
    current_user: User = Depends(get_current_user)
):
    """
    Full RAG pipeline with answer generation:
    Query → Search relevant chunks → Send to Ollama → Get real answer
    """

    # Step 1 - find relevant chunks
    results = rag.search_documents(query=data.query, top_k=data.top_k)

    if not results:
        return {
            "query": data.query,
            "answer": "No relevant documents found.",
            "sources": []
        }

    # Step 2 - send chunks to Ollama and get a real answer
    answer = rag.generate_answer(query=data.query, chunks=results)

    # Step 3 - also return which documents were used
    sources = [
        {
            "document_id": r["document_id"],
            "title": r["title"],
            "company_name": r["company_name"],
            "chunk_text": r["chunk_text"]
        }
        for r in results
    ]

    return {
        "query": data.query,
        "answer": answer,        # actual AI generated answer
        "sources": sources       # which document chunks were used
    }