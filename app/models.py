from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String, unique=True)
    email      = Column(String, unique=True)
    password   = Column(String)                   # stored as bcrypt hash
    role       = Column(String, default="Client") # Admin, Financial Analyst, Auditor, Client


class Document(Base):
    __tablename__ = "documents"

    id            = Column(Integer, primary_key=True, index=True)
    title         = Column(String)
    company_name  = Column(String)      
    document_type = Column(String)   # invoice, report, contract
    uploaded_by   = Column(String)   # username of uploader
    file_path     = Column(String)
    created_at    = Column(DateTime, default=datetime.utcnow)
    is_indexed    = Column(Boolean, default=False)  # True after RAG indexing