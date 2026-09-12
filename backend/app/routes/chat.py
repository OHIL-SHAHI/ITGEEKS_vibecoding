import logging
from fastapi import APIRouter, HTTPException
from backend.app.models.schemas import ChatQueryRequest, ChatQueryResponse
from backend.app.services.rag import rag_service
from backend.app.services.mongo_store import mongo_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/query", response_model=ChatQueryResponse)
async def query_assistant(req: ChatQueryRequest):
    try:
        session_id = req.session_id or "default"
        response = await rag_service.answer_query(req.query, session_id=session_id)
        return response
    except Exception as e:
        logger.error(f"Chat query handling failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    try:
        messages = await mongo_store.get_chat_history(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        logger.error(f"Failed to fetch history for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
