import uuid
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from flashrank import Ranker, RerankRequest
import os
from dotenv import load_dotenv

load_dotenv()


#  Models & clients — loaded once when app starts    

print("Loading embedding model...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Embedding model ready!")

print("Loading reranker...")
reranker = Ranker()   # flashrank default model, downloads on first run
print("Reranker ready!")

COLLECTION  = "finance_docs"
VECTOR_SIZE = 384     # dimension for all-MiniLM-L6-v2

# Connect to Qdrant — falls back to in-memory if server not running
try:
    qdrant = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333))
    )
    qdrant.get_collections()   # quick check
    print("Connected to Qdrant server")
except Exception:
    print("Qdrant server not found → using in-memory mode (data lost on restart)")
    qdrant = QdrantClient(":memory:")

# Create collection if it doesn't exist
existing = [c.name for c in qdrant.get_collections().collections]
if COLLECTION not in existing:
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
    print(f"Created Qdrant collection: {COLLECTION}")



#  Text splitting                                                     

def split_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=150,
        chunk_overlap=30
    )
    return splitter.split_text(text)



#  Store document chunks in Qdrant                                    

def store_document(doc_id: int, text: str, title: str, company_name: str, doc_type: str):
    chunks = split_text(text)

    if not chunks:
        return 0

    points = []
    for chunk in chunks:
        embedding = embed_model.encode(chunk).tolist()
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "document_id":   doc_id,
                    "chunk_text":    chunk,
                    "title":         title,
                    "company_name":  company_name,
                    "document_type": doc_type,
                }
            )
        )

    qdrant.upsert(collection_name=COLLECTION, points=points)
    return len(chunks)



#  Remove document from Qdrant                                        

def remove_document(doc_id: int):
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
        )
    )



#  Search + Rerank pipeline                                           

def search_documents(query: str, top_k: int = 5) -> list[dict]:

    # Step 1 — convert query into embedding vector
    query_vector = embed_model.encode(query).tolist()

    # Step 2 — semantic vector search from Qdrant
    response = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=20,
        with_payload=True
    )

    hits = response.points

    if not hits:
        return []

    # Step 3 — prepare candidates
    candidates = [
        {
            "document_id":   h.payload["document_id"],
            "title":         h.payload["title"],
            "company_name":  h.payload["company_name"],
            "chunk_text":    h.payload["chunk_text"],
            "vector_score":  float(h.score),
        }
        for h in hits
    ]

    # Step 4 — rerank results using FlashRank
    passages = [
        {"id": i, "text": c["chunk_text"]}
        for i, c in enumerate(candidates)
    ]

    rerank_request = RerankRequest(
        query=query,
        passages=passages
    )

    reranked = reranker.rerank(rerank_request)

    # Step 5 — return top reranked results
    results = []

    for item in reranked[:top_k]:
        original = candidates[item["id"]]
        original["rerank_score"] = float(item["score"])
        results.append(original)

    return results


#  Get all chunks of one document (context)                          


def get_context(doc_id: int) -> list[str]:
    results, _ = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
        ),
        with_payload=True,
        limit=100
    )
    chunks = [r.payload["chunk_text"] for r in results]
    return chunks


#####   Generate Answer Using Ollama

def generate_answer(query: str, chunks: list[dict]) -> str:
    try:
        from langchain_ollama import OllamaLLM

        # take the text from top chunks and join them as context
        context = "\n\n".join([c["chunk_text"] for c in chunks])

        llm = OllamaLLM(model="llama3")

        prompt = f"""
You are a financial document assistant.

Answer the user's question ONLY using the provided document context.

Rules:
- Do NOT invent information.
- Do NOT assume missing details.
- If the answer exists in the context, return it clearly and precisely.
- If the answer is not found, say: "Answer not found in the provided documents."
- Keep the answer concise and factual.

Document Context:
{context}

Question:
{query}

Answer:
"""

        answer = llm.invoke(prompt)
        return answer

    except Exception as e:
        return f"Could not generate answer: {str(e)}"