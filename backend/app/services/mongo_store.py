import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from backend.app.config import settings

logger = logging.getLogger(__name__)


class MongoStore:
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db = None

    def get_db(self):
        if self._client is None:
            self._client = AsyncIOMotorClient(settings.MONGODB_URL)
            self._db = self._client[settings.MONGODB_DB_NAME]
        return self._db

    async def ping(self) -> bool:
        try:
            db = self.get_db()
            await db.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection ping failed: {str(e)}")
            return False

    # Documents collection
    async def upsert_document(self, doc_data: Dict[str, Any]) -> str:
        db = self.get_db()
        doc_data["updated_at"] = datetime.utcnow().isoformat()
        await db.documents.update_one(
            {"doc_id": doc_data["doc_id"]},
            {"$set": doc_data},
            upsert=True
        )
        return doc_data["doc_id"]

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        db = self.get_db()
        return await db.documents.find_one({"doc_id": doc_id}, {"_id": 0})

    async def list_documents(self) -> List[Dict[str, Any]]:
        db = self.get_db()
        cursor = db.documents.find({}, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def update_document_status(
        self,
        doc_id: str,
        status: str,
        progress: int,
        status_message: str,
        error_message: Optional[str] = None
    ) -> None:
        db = self.get_db()
        update_data = {
            "status": status,
            "progress": progress,
            "status_message": status_message,
            "updated_at": datetime.utcnow().isoformat()
        }
        if error_message is not None:
            update_data["error_message"] = error_message
        await db.documents.update_one(
            {"doc_id": doc_id},
            {"$set": update_data}
        )

    async def delete_document(self, doc_id: str) -> bool:
        db = self.get_db()
        result = await db.documents.delete_one({"doc_id": doc_id})
        return result.deleted_count > 0


    # Chat Sessions collection
    async def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        is_refusal: bool = False,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        db = self.get_db()
        message = {
            "role": role,
            "content": content,
            "is_refusal": is_refusal,
            "sources": sources or [],
            "timestamp": datetime.utcnow().isoformat()
        }
        await db.chat_sessions.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$setOnInsert": {"created_at": datetime.utcnow().isoformat()},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            },
            upsert=True
        )

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        db = self.get_db()
        session = await db.chat_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if session and "messages" in session:
            return session["messages"]
        return []

    # Evaluation collection
    async def save_evaluation_run(self, eval_data: Dict[str, Any]) -> str:
        db = self.get_db()
        eval_data["saved_at"] = datetime.utcnow().isoformat()
        res = await db.evaluations.insert_one(eval_data)
        return str(res.inserted_id)

    async def get_latest_evaluations(self, limit: int = 10) -> List[Dict[str, Any]]:
        db = self.get_db()
        cursor = db.evaluations.find({}, {"_id": 0}).sort("timestamp", -1)
        return await cursor.to_list(length=limit)


mongo_store = MongoStore()
