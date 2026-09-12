import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
from backend.app.services.evaluator import benchmark_evaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("benchmark_runner")


async def main():
    logger.info("Executing 30-question Evaluation Benchmark Suite...")
    resp = await benchmark_evaluator.run_evaluation()

    print("\n" + "=" * 60)
    print("EXAM-NIGHT MULTIMODAL RAG BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Run ID:            {resp.run_id}")
    print(f"Timestamp:         {resp.timestamp}")
    print(f"Total Questions:   {resp.total_questions}")
    print(f"Target Questions:  {resp.target_questions}")
    print(f"Refusal Questions: {resp.refusal_questions}")
    print("-" * 60)
    print(f"Refusal Accuracy:  {resp.refusal_accuracy}% (Target: 100%)")
    print(f"Citation Accuracy: {resp.citation_accuracy}%")
    print(f"Overall Pass Rate: {resp.overall_pass_rate}%")
    print("=" * 60 + "\n")

    print(f"{'ID':<6} {'TYPE':<8} {'PASSED':<8} {'REFUSAL':<8} {'CIT_OK':<8} {'QUESTION'}")
    print("-" * 75)
    for r in resp.results:
        p_str = "PASS" if r.passed else "FAIL"
        ref_str = "YES" if r.is_refusal else "NO"
        cit_str = "YES" if r.citation_correct else "NO"
        short_q = (r.question[:45] + "...") if len(r.question) > 45 else r.question
        print(f"{r.id:<6} {r.type:<8} {p_str:<8} {ref_str:<8} {cit_str:<8} {short_q}")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
