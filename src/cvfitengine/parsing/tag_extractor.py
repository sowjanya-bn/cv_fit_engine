from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import yaml


@dataclass(frozen=True)
class TagVocab:
    skills: List[str]
    tools: List[str]
    domain: List[str]
    seniority: List[str]


DEFAULT_SYNONYMS: dict[str, list[str]] = {
    # skills
    "rag": ["retrieval augmented generation", "retrieval-augmented generation"],
    "knowledge-graphs": ["knowledge graph", "knowledge graphs", "kg"],
    "nlp": ["natural language processing"],
    "machine-learning": ["machine learning", "ml"],
    "distributed-systems": ["distributed systems", "distributed system"],
    "api-design": ["api design", "rest api", "restful api", "apis"],
    "system-design": ["system design", "architecture", "architecting"],
    "data-quality": ["data quality", "data validation", "data consistency"],
    "evaluation": ["evaluation", "benchmarking", "metrics"],
    "prompt-engineering": ["prompt engineering", "prompting"],

    # tools
    "aws": ["amazon web services"],
    "sql": ["sql", "postgres", "postgresql", "mysql", "sqlite", "bigquery"],
    "docker": ["docker", "containers", "containerisation", "containerization"],
    "cicd": ["ci/cd", "ci cd", "cicd", "continuous integration", "continuous delivery"],
    "elasticsearch": ["elasticsearch", "elastic search"],
    "xgboost": ["xgboost"],
    "shap": ["shap"],

    # domain
    "cultural-heritage": ["cultural heritage", "museum", "exhibition"],
    "telecom": ["telecom", "telecommunications", "sip"],
    "finance": ["finance", "trading", "stocks", "equities", "earnings"],
    "consulting": ["consulting", "client brief", "stakeholder"],
    "research": ["research", "paper", "publication", "conference"],
}


def load_tag_vocab(path: str | Path = "configs/tag_vocab.yaml") -> TagVocab:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return TagVocab(
        skills=list(data.get("skills", [])),
        tools=list(data.get("tools", [])),
        domain=list(data.get("domain", [])),
        seniority=list(data.get("seniority", [])),
    )


def _normalize(text: str) -> str:
    t = text.lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[\u2010-\u2015]", "-", t)  # normalize dash variants
    t = re.sub(r"[^a-z0-9\+\#\-/\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokenize(text: str) -> Set[str]:
    # keep hyphens, split into components too
    words = re.findall(r"[a-z][a-z0-9\+\#\-]{1,}", text)
    out: set[str] = set()
    for w in words:
        out.add(w)
        if "-" in w:
            out.update([p for p in w.split("-") if p])
    return out


def extract_job_tags(
    jd_text: str,
    vocab: TagVocab,
    synonyms: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    syn = synonyms or DEFAULT_SYNONYMS
    text = _normalize(jd_text)
    tokens = _tokenize(text)

    # Build a flat lookup of canonical tags by category for validation
    valid = {
        "skills": set(vocab.skills),
        "tools": set(vocab.tools),
        "domain": set(vocab.domain),
        "seniority": set(vocab.seniority),
    }

    found: dict[str, set[str]] = {k: set() for k in valid.keys()}

    # Phrase matching via synonyms (multi-word first)
    for canonical, phrases in syn.items():
        canonical_lc = canonical.lower()
        if canonical_lc not in (valid["skills"] | valid["tools"] | valid["domain"] | valid["seniority"]):
            # ignore synonyms for tags not in vocab
            continue
        for ph in phrases:
            if _normalize(ph) in text:
                # assign to the right category
                for cat, catset in valid.items():
                    if canonical_lc in catset:
                        found[cat].add(canonical_lc)
                        break

    # Token matching for canonical tags and common abbreviations
    for cat, catset in valid.items():
        for tag in catset:
            if tag in tokens:
                found[cat].add(tag)

    # Heuristic seniority signals
    seniority_hints = {
        "lead": ["lead", "leading", "team lead", "tech lead", "manager", "management", "ownership"],
        "mid-level": ["mid", "mid-level", "intermediate"],
        "entry": ["entry", "graduate", "junior", "intern"],
        # If present in vocab, map common senior terms.
        "senior": ["senior", "sr."],
        "principal": ["principal", "staff", "architect"],
    }
    for canon, hints in seniority_hints.items():
        if canon in valid["seniority"]:
            for h in hints:
                if _normalize(h) in text:
                    found["seniority"].add(canon)

    # return sorted lists
    return {k: sorted(list(v)) for k, v in found.items()}


def collect_resume_tags(resume) -> dict[str, set[str]]:
    """Union of all block-level tags across resume blocks."""
    out = {"skills": set(), "tools": set(), "domain": set(), "seniority": set()}
    for section in ["experience", "projects"]:
        for b in getattr(resume.blocks, section, []) or []:
            t = getattr(b, "tags", None)
            if not t:
                continue
            for k in out.keys():
                vals = getattr(t, k, None)
                if vals:
                    out[k].update([str(x).lower() for x in vals])
    return out