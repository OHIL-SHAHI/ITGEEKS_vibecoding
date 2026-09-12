import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.app.services.evaluator import benchmark_evaluator
from backend.app.services.mongo_store import mongo_store
from backend.app.models.schemas import BenchmarkRunResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.post("/run", response_model=BenchmarkRunResponse)
async def run_benchmark(limit: Optional[int] = Query(None, ge=1, le=50)):
    try:
        results = await benchmark_evaluator.run_evaluation(limit=limit)
        return results
    except Exception as e:
        logger.error(f"Benchmark run failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Benchmark execution failed: {str(e)}")


@router.get("/history")
async def get_history(limit: int = Query(10, ge=1, le=50)):
    try:
        runs = await mongo_store.get_latest_evaluations(limit=limit)
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Failed to fetch benchmark history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
