from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


JdCategory = Literal["applied_ai_systems", "backend_systems", "ml_heavy", "mixed"]


@dataclass(frozen=True)
class JdProfile:
    category: JdCategory
    seniority_level: str  # e.g. "junior" | "mid" | "senior" | "lead" | "unknown"
    scores: dict[str, float]


_RE_WORD = re.compile(r"[A-Za-z][A-Za-z0-9\+\#\.-]{1,}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _RE_WORD.finditer(text or "")}


def classify_jd(jd_text: str) -> JdProfile:
    """Heuristic JD classifier.

    This deliberately avoids overfitting. It is used to drive:
      - anchor ordering (AI-first vs engineering-first)
      - conservative seniority bias
    """

    t = _norm(jd_text)
    toks = _tokens(t)

    applied_ai = {
        "rag", "retrieval", "vector", "embedding", "embeddings", "llm", "llms", "prompt", "prompting",
        "knowledge", "graph", "graphs", "sparql", "rdf", "ontology", "evaluation", "hallucination",
        "grounding", "agent", "agents", "tool", "tools",
    }
    backend = {
        "api", "apis", "microservices", "service", "services", "distributed", "scalable", "scalability",
        "latency", "throughput", "reliability", "monitoring", "observability", "docker", "kubernetes",
        "cicd", "ci/cd", "aws", "gcp", "azure", "security",
    }
    ml_heavy = {
        "tensorflow", "pytorch", "training", "train", "finetune", "fine-tune", "fine-tuning",
        "feature", "features", "featurestore", "feature-store", "mlops", "model", "models",
        "hyperparameter", "hyperparameters", "xgboost", "lightgbm", "catboost",
    }

    def score(sig: set[str]) -> float:
        if not sig:
            return 0.0
        return len(sig & toks) / max(1, len(sig))

    s_applied = score(applied_ai)
    s_backend = score(backend)
    s_ml = score(ml_heavy)

    # Category decision
    best = max([(s_applied, "applied_ai_systems"), (s_backend, "backend_systems"), (s_ml, "ml_heavy")], key=lambda x: x[0])
    # If signals are close, call it mixed.
    sorted_scores = sorted([s_applied, s_backend, s_ml], reverse=True)
    if sorted_scores[0] > 0 and (sorted_scores[0] - sorted_scores[1]) < 0.03:
        category: JdCategory = "mixed"
    else:
        category = best[1]  # type: ignore[assignment]

    # Seniority detection (coarse)
    seniority_level = "unknown"
    if any(w in t for w in ["principal", "staff", "architect"]):
        seniority_level = "principal"
    elif any(w in t for w in ["lead", "tech lead", "team lead", "manager", "management"]):
        seniority_level = "lead"
    elif "senior" in t:
        seniority_level = "senior"
    elif "junior" in t or "graduate" in t:
        seniority_level = "junior"
    elif "mid" in t or "mid-level" in t:
        seniority_level = "mid"

    return JdProfile(
        category=category,
        seniority_level=seniority_level,
        scores={
            "applied_ai_systems": round(s_applied, 4),
            "backend_systems": round(s_backend, 4),
            "ml_heavy": round(s_ml, 4),
        },
    )
