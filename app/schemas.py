from pydantic import BaseModel
from typing import Optional


# --- Auth ---

class RegisterSchema(BaseModel):
    username: str
    email: str
    password: str


class LoginSchema(BaseModel):
    email: str
    password: str


# --- Role ---

class AssignRoleSchema(BaseModel):
    email: str
    role: str   # "Admin" | "Financial Analyst" | "Auditor" | "Client"
    

# --- RAG Search ---

class SearchSchema(BaseModel):
    query: str
    top_k: Optional[int] = 5