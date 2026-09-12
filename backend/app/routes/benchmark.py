import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.app.services.evaluator import benchmark_evaluator
from backend.app.services.mongo_store import mongo_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.post("/run")
async def trigger_benchmark(limit: Optional[int] = Query(None, ge=1, le=50)) -> Dict[str, Any]:
    try:
        status = benchmark_evaluator.start_evaluation_task(limit=limit)
        return status
    except Exception as e:
        logger.error(f"Benchmark trigger failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start benchmark: {str(e)}")


@router.get("/status")
async def get_benchmark_status() -> Dict[str, Any]:
    return benchmark_evaluator.get_status()


@router.get("/latest")
async def get_latest_benchmark(min_questions: int = Query(20, ge=0)) -> Optional[Dict[str, Any]]:
    try:
        # First check in-memory state if it meets min_questions
        state = benchmark_evaluator.get_status()
        if (
            state.get("status") == "completed"
            and state.get("last_result")
            and state["last_result"].get("total_questions", 0) >= min_questions
        ):
            return state["last_result"]

        # Otherwise check MongoDB for completed evaluation meeting min_questions
        runs = await mongo_store.get_latest_evaluations(limit=1, min_questions=min_questions)
        if runs:
            return runs[0]

        # Fallback to any run in MongoDB if no run meets min_questions
        if min_questions > 0:
            runs = await mongo_store.get_latest_evaluations(limit=1, min_questions=0)
            if runs:
                return runs[0]

        # Fallback to in-memory state
        if state.get("last_result"):
            return state["last_result"]

        return None
    except Exception as e:
        logger.error(f"Failed to fetch latest benchmark: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    try:
        runs = await mongo_store.get_latest_evaluations(limit=limit)
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Failed to fetch benchmark history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
