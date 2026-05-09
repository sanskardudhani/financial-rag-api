from fastapi import FastAPI
from app.database import Base, engine
from app.routes import auth_routes, document_routes, role_routes, rag_routes

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Financial Document Management API",
    description="Upload, manage and search financial documents using AI",
    version="1.0.0"
)


# Register all routers
app.include_router(auth_routes.router)
app.include_router(document_routes.router)
app.include_router(role_routes.router)
app.include_router(rag_routes.router)


@app.get("/")
def home():
    return {"message": "Financial RAG API is running!"}