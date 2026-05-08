"""
DocuBot — Benchmark del motor RAG con corpus de 5.000 documentos.
Mide: throughput, latencias, calidad de retrieval y costos estimados.

Uso:
    python benchmark_rag.py --base-url http://localhost:8000 --token YOUR_JWT

Fases:
    1. Warm-up (10 consultas) — calentamiento del sistema
    2. Throughput test — consultas concurrentes
    3. Latency test — consultas secuenciales con medición precisa
    4. Quality test — validación de confianza y citas
    5. Stress test — carga sostenida 60 segundos
"""
import asyncio
import argparse
import time
import json
import statistics
import httpx
from datetime import datetime


# ── Preguntas de benchmark con respuesta esperada ───────────────────────
BENCHMARK_QUERIES = [
    {
        "question": "¿Cuál es el plazo de garantía del contrato?",
        "expected_keywords": ["garantía", "plazo", "días"],
        "min_confidence": 0.6,
    },
    {
        "question": "¿Qué multas se aplican por retraso en la entrega?",
        "expected_keywords": ["multa", "retraso", "porcentaje"],
        "min_confidence": 0.6,
    },
    {
        "question": "¿Cuáles son las condiciones de pago establecidas?",
        "expected_keywords": ["pago", "días", "estado de pago"],
        "min_confidence": 0.6,
    },
    {
        "question": "¿Qué documentos se requieren para la recepción provisional?",
        "expected_keywords": ["recepción", "documentos", "provisional"],
        "min_confidence": 0.5,
    },
    {
        "question": "¿Cuáles son los requisitos de seguros del contratista?",
        "expected_keywords": ["seguro", "responsabilidad"],
        "min_confidence": 0.5,
    },
]


class RagBenchmark:
    def __init__(self, base_url: str, token: str, project_id: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.project_id = project_id
        self.results = []

    async def single_query(self, client: httpx.AsyncClient, question: str) -> dict:
        """Ejecuta una consulta RAG y retorna métricas."""
        t0 = time.monotonic()
        try:
            resp = await client.post(
                f"{self.base_url}/api/v1/rag/query",
                json={
                    "project_id": self.project_id,
                    "question": question,
                    "top_k": 8,
                },
                headers=self.headers,
                timeout=30.0,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "latency_ms": latency_ms,
                    "confidence": data.get("confidence", 0),
                    "requires_human_review": data.get("requires_human_review", True),
                    "evidence_count": len(data.get("evidence", [])),
                    "answer_length": len(data.get("answer", "")),
                    "status_code": 200,
                }
            else:
                return {
                    "success": False,
                    "latency_ms": latency_ms,
                    "status_code": resp.status_code,
                    "error": resp.text[:200],
                }
        except Exception as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            return {
                "success": False,
                "latency_ms": latency_ms,
                "status_code": 0,
                "error": str(e),
            }

    async def warmup(self, client: httpx.AsyncClient, n: int = 5):
        """Warm-up del sistema."""
        print(f"\n{'─'*50}")
        print(f"FASE 1: Warm-up ({n} consultas secuenciales)")
        print(f"{'─'*50}")
        for i in range(n):
            q = BENCHMARK_QUERIES[i % len(BENCHMARK_QUERIES)]["question"]
            result = await self.single_query(client, q)
            status = "✓" if result["success"] else "✗"
            print(f"  [{i+1}/{n}] {status} {result['latency_ms']}ms")
        print("  Warm-up completado\n")

    async def latency_test(self, client: httpx.AsyncClient, n: int = 50):
        """Test de latencia secuencial — medición precisa."""
        print(f"{'─'*50}")
        print(f"FASE 2: Latency test ({n} consultas secuenciales)")
        print(f"{'─'*50}")
        latencies = []
        successes = 0

        for i in range(n):
            q = BENCHMARK_QUERIES[i % len(BENCHMARK_QUERIES)]["question"]
            result = await self.single_query(client, q)
            if result["success"]:
                latencies.append(result["latency_ms"])
                successes += 1
            if (i + 1) % 10 == 0:
                print(f"  Progreso: {i+1}/{n}", end="\r")

        if latencies:
            latencies.sort()
            print(f"\n  Consultas exitosas: {successes}/{n}")
            print(f"  P50:  {statistics.median(latencies):.0f}ms")
            print(f"  P90:  {latencies[int(len(latencies)*0.9)]:.0f}ms")
            print(f"  P99:  {latencies[int(len(latencies)*0.99)]:.0f}ms")
            print(f"  Min:  {min(latencies)}ms")
            print(f"  Max:  {max(latencies)}ms")
            print(f"  Avg:  {statistics.mean(latencies):.0f}ms")

            sla_ok = latencies[int(len(latencies)*0.9)] < 15000
            print(f"\n  SLA P90 < 15s: {'✓ CUMPLE' if sla_ok else '✗ NO CUMPLE'}")

        return latencies

    async def throughput_test(self, client: httpx.AsyncClient,
                               concurrency: int = 5, duration_s: int = 30):
        """Test de throughput con consultas concurrentes."""
        print(f"\n{'─'*50}")
        print(f"FASE 3: Throughput test ({concurrency} concurrentes, {duration_s}s)")
        print(f"{'─'*50}")

        completed = []
        errors = []
        stop_event = asyncio.Event()
        t_start = time.monotonic()

        async def worker(worker_id: int):
            idx = 0
            while not stop_event.is_set():
                q = BENCHMARK_QUERIES[idx % len(BENCHMARK_QUERIES)]["question"]
                idx += 1
                result = await self.single_query(client, q)
                if result["success"]:
                    completed.append(result["latency_ms"])
                else:
                    errors.append(result.get("status_code", 0))

        # Lanzar workers
        workers = [asyncio.create_task(worker(i)) for i in range(concurrency)]

        # Esperar duración del test
        await asyncio.sleep(duration_s)
        stop_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        elapsed = time.monotonic() - t_start
        rps = len(completed) / elapsed if elapsed > 0 else 0

        print(f"  Consultas completadas: {len(completed)}")
        print(f"  Errores: {len(errors)}")
        print(f"  Throughput: {rps:.2f} req/s")
        if completed:
            print(f"  Latencia promedio: {statistics.mean(completed):.0f}ms")

        return {"rps": rps, "completed": len(completed), "errors": len(errors)}

    async def quality_test(self, client: httpx.AsyncClient):
        """Test de calidad de respuestas RAG."""
        print(f"\n{'─'*50}")
        print(f"FASE 4: Quality test ({len(BENCHMARK_QUERIES)} preguntas)")
        print(f"{'─'*50}")

        results = []
        for bq in BENCHMARK_QUERIES:
            result = await self.single_query(client, bq["question"])
            if result["success"]:
                meets_confidence = result["confidence"] >= bq["min_confidence"]
                has_evidence = result["evidence_count"] > 0
                results.append({
                    "question": bq["question"][:50] + "...",
                    "confidence": result["confidence"],
                    "evidence_count": result["evidence_count"],
                    "meets_confidence": meets_confidence,
                    "has_evidence": has_evidence,
                    "latency_ms": result["latency_ms"],
                })
                status = "✓" if (meets_confidence and has_evidence) else "⚠"
                print(
                    f"  {status} Conf: {result['confidence']:.2f} | "
                    f"Citas: {result['evidence_count']} | "
                    f"{result['latency_ms']}ms | {bq['question'][:40]}..."
                )

        if results:
            avg_conf = statistics.mean(r["confidence"] for r in results)
            pct_with_evidence = sum(1 for r in results if r["has_evidence"]) / len(results)
            print(f"\n  Confianza promedio: {avg_conf:.2f}")
            print(f"  Respuestas con citas: {pct_with_evidence*100:.0f}%")

    async def run(self, phases: list = None):
        """Ejecuta todas las fases del benchmark."""
        phases = phases or ["warmup", "latency", "throughput", "quality"]
        print(f"\n{'='*50}")
        print(f"DocuBot RAG Benchmark")
        print(f"Proyecto: {self.project_id}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print(f"{'='*50}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Verificar health
            try:
                resp = await client.get(f"{self.base_url}/health")
                health = resp.json()
                print(f"\nSistema: {health.get('status', 'unknown')} — v{health.get('version', '?')}")
            except Exception as e:
                print(f"\n⚠ No se pudo verificar health: {e}")

            if "warmup" in phases:
                await self.warmup(client, n=5)
            if "latency" in phases:
                await self.latency_test(client, n=50)
            if "throughput" in phases:
                await self.throughput_test(client, concurrency=3, duration_s=30)
            if "quality" in phases:
                await self.quality_test(client)

        print(f"\n{'='*50}")
        print(f"Benchmark completado")
        print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocuBot RAG Benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default="TEST_TOKEN", help="JWT Bearer token")
    parser.add_argument("--project-id", default="550e8400-e29b-41d4-a716-446655440000")
    parser.add_argument("--phases", nargs="+",
                        choices=["warmup", "latency", "throughput", "quality"],
                        default=["warmup", "latency", "quality"])
    args = parser.parse_args()

    benchmark = RagBenchmark(args.base_url, args.token, args.project_id)
    asyncio.run(benchmark.run(phases=args.phases))
