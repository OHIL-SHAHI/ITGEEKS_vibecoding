import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend.app.config import settings
from backend.app.services.rag import rag_service
from backend.app.services.mongo_store import mongo_store
from backend.app.models.schemas import BenchmarkQuestionResult, BenchmarkRunResponse

logger = logging.getLogger(__name__)


class BenchmarkEvaluator:
    def __init__(self):
        self.benchmark_file = settings.BENCHMARK_DIR / "benchmark_questions.json"
        self._active_task: Optional[asyncio.Task] = None
        self.state: Dict[str, Any] = {
            "status": "idle",  # "idle" | "running" | "completed" | "failed"
            "current": 0,
            "total": 0,
            "progress": 0,
            "current_question": "",
            "run_id": None,
            "error": None,
            "last_result": None
        }

    def load_questions(self) -> List[Dict[str, Any]]:
        if not self.benchmark_file.exists():
            raise FileNotFoundError(f"Benchmark file not found at {self.benchmark_file}")
        with open(self.benchmark_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_status(self) -> Dict[str, Any]:
        return self.state

    def start_evaluation_task(self, limit: int = None) -> Dict[str, Any]:
        if self.state["status"] == "running" and self._active_task and not self._active_task.done():
            logger.info("Evaluation task already in progress. Returning existing task state.")
            return self.state

        self.state["status"] = "running"
        self.state["current"] = 0
        self.state["progress"] = 0
        self.state["error"] = None
        self.state["current_question"] = "Initializing evaluation suite..."
        self._active_task = asyncio.create_task(self._run_evaluation_background(limit=limit))
        return self.state

    async def _run_evaluation_background(self, limit: int = None) -> None:
        try:
            res = await self.run_evaluation(limit=limit)
            self.state["status"] = "completed"
            self.state["progress"] = 100
            self.state["last_result"] = res.model_dump()
        except Exception as e:
            logger.error(f"Background benchmark run failed: {str(e)}")
            self.state["status"] = "failed"
            self.state["error"] = str(e)

    async def run_evaluation(self, limit: int = None) -> BenchmarkRunResponse:
        questions = self.load_questions()
        if limit:
            questions = questions[:limit]

        total_q = len(questions)
        self.state["total"] = total_q
        self.state["current"] = 0
        self.state["progress"] = 0

        run_id = f"run_{int(time.time())}"
        self.state["run_id"] = run_id
        results: List[BenchmarkQuestionResult] = []

        target_total = 0
        target_passed = 0
        target_citation_correct = 0

        refusal_total = 0
        refusal_passed = 0

        for i, q in enumerate(questions):
            qid = q.get("id", "UNK")
            qtype = q.get("type", "single")
            query = q.get("question", "")
            must_refuse = q.get("must_refuse", False)
            expected_pages = q.get("expected_pages", [])
            keywords = q.get("keywords", [])

            self.state["current"] = i + 1
            self.state["progress"] = int(((i + 1) / total_q) * 100)
            self.state["current_question"] = query

            logger.info(f"Evaluating benchmark [{i+1}/{total_q}]: {qid} - {query[:60]}...")

            # Execute query
            resp = await rag_service.answer_query(query, session_id=f"benchmark_{run_id}")
            answer = resp.answer
            is_refusal = resp.is_refusal

            actual_pages = [
                {"filename": s.filename, "page": s.page}
                for s in resp.sources
            ]

            if must_refuse:
                refusal_total += 1
                refusal_correct = is_refusal
                citation_correct = True
                passed = refusal_correct
                if refusal_correct:
                    refusal_passed += 1
            else:
                target_total += 1
                refusal_correct = not is_refusal

                # Check citation accuracy: at least one expected page matches
                citation_correct = False
                for exp in expected_pages:
                    exp_file = exp.get("filename", "").lower()
                    exp_page = exp.get("page")
                    for act in actual_pages:
                        act_file = act.get("filename", "").lower()
                        act_page = act.get("page")
                        if exp_file == act_file and (exp_page is None or exp_page == act_page):
                            citation_correct = True
                            break
                    if citation_correct:
                        break

                if citation_correct:
                    target_citation_correct += 1

                # Check keywords in answer
                kw_match = True
                if keywords:
                    lower_ans = answer.lower()
                    kw_match = any(kw.lower() in lower_ans for kw in keywords)

                passed = (not is_refusal) and citation_correct and kw_match
                if passed:
                    target_passed += 1

            results.append(
                BenchmarkQuestionResult(
                    id=qid,
                    type=qtype,
                    question=query,
                    must_refuse=must_refuse,
                    expected_pages=expected_pages,
                    actual_pages=actual_pages,
                    is_refusal=is_refusal,
                    refusal_correct=refusal_correct,
                    citation_correct=citation_correct,
                    passed=passed,
                    answer=answer
                )
            )
            # Throttle between queries to respect API rate limits
            await asyncio.sleep(1.0)

        refusal_acc = (refusal_passed / refusal_total) if refusal_total > 0 else 1.0
        citation_acc = (target_citation_correct / target_total) if target_total > 0 else 0.0
        overall_pass = ((target_passed + refusal_passed) / len(questions)) if questions else 0.0

        run_response = BenchmarkRunResponse(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_questions=len(questions),
            target_questions=target_total,
            refusal_questions=refusal_total,
            refusal_accuracy=round(refusal_acc * 100, 2),
            citation_accuracy=round(citation_acc * 100, 2),
            overall_pass_rate=round(overall_pass * 100, 2),
            results=results
        )

        # Persist run in MongoDB
        try:
            await mongo_store.save_evaluation_run(run_response.model_dump())
        except Exception as e:
            logger.error(f"Failed to persist benchmark run: {str(e)}")

        return run_response


benchmark_evaluator = BenchmarkEvaluator()
