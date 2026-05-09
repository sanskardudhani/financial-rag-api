import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Document, User
from app.auth import get_current_user, require_permission

router = APIRouter()

UPLOAD_FOLDER      = "app/uploads"
VALID_DOC_TYPES    = ["invoice", "report", "contract"]
ALLOWED_EXTENSIONS = [".pdf", ".txt"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/documents/upload")
def upload_document(
    title: str         = Form(...),
    company_name: str  = Form(...),     
    document_type: str = Form(...),
    file: UploadFile   = File(...),
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_permission("upload"))
):
    if document_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"document_type must be: {VALID_DOC_TYPES}")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and TXT files allowed")

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        title=title,
        company_name=company_name,
        document_type=document_type,
        uploaded_by=current_user.username,
        file_path=file_path
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"message": "Document uploaded", "document_id": doc.id, "title": doc.title}


@router.get("/documents")
def get_all_documents(
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_permission("view"))
):
    docs = db.query(Document).all()
    return docs


# /documents/search must stay ABOVE /documents/{document_id}
@router.get("/documents/search")
def search_documents(
    title: Optional[str]         = Query(None),
    company_name: Optional[str]  = Query(None),
    document_type: Optional[str] = Query(None),
    db: Session                  = Depends(get_db),
    current_user: User           = Depends(require_permission("view"))
):
    query = db.query(Document)

    if title:
        query = query.filter(Document.title.ilike(f"%{title}%"))
    if company_name:
        query = query.filter(Document.company_name.ilike(f"%{company_name}%"))
    if document_type:
        query = query.filter(Document.document_type == document_type)

    results = query.all()
    return {"total": len(results), "documents": results}


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_permission("view"))
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


#  PUT /documents/{document_id} for editing metadata
@router.put("/documents/{document_id}")
def edit_document(
    document_id: int,
    title: Optional[str]         = Form(None),
    company_name: Optional[str]  = Form(None),
    document_type: Optional[str] = Form(None),
    db: Session                  = Depends(get_db),
    current_user: User           = Depends(require_permission("edit"))  # Analyst + Admin
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    
    if title:
        doc.title = title
    if company_name:
        doc.company_name = company_name
    if document_type:
        if document_type not in VALID_DOC_TYPES:
            raise HTTPException(status_code=400, detail=f"document_type must be: {VALID_DOC_TYPES}")
        doc.document_type = document_type

    db.commit()

    return {"message": "Document updated", "document_id": document_id}


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_permission("delete"))
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # only uploader or Admin can delete
    if doc.uploaded_by != current_user.username and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="You can only delete your own documents")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()

    return {"message": f"Document {document_id} deleted"}