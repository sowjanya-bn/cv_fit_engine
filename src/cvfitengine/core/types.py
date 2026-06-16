from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

BulletKind = Literal["impact", "responsibility", "technical", "leadership", "other"]

class BulletTags(BaseModel):
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    domain: List[str] = Field(default_factory=list)

class Bullet(BaseModel):
    id: str
    text: str
    kind: BulletKind = "other"
    metrics: List[str] = Field(default_factory=list)
    tags: BulletTags = Field(default_factory=BulletTags)
    # Evidence and rewrite metadata (Phase 1 enrichment)
    evidence: Optional[str] = None
    allowed_strength: Optional[str] = "moderate"   # strong | moderate | weak
    rewrite_allowed: bool = False
    title_relevance: List[str] = Field(default_factory=list)

class BlockTags(BaseModel):
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    domain: List[str] = Field(default_factory=list)
    seniority: List[str] = Field(default_factory=list)

class ExperienceBlock(BaseModel):
    id: str
    role: str
    company: str
    location: Optional[str] = ""
    start: Optional[str] = ""
    end: Optional[str] = ""
    employment_type: Optional[str] = ""
    summary: Optional[str] = ""
    bullets: List[Bullet] = Field(default_factory=list)
    tags: BlockTags = Field(default_factory=BlockTags)
    # Title strategy metadata (Phase 1 enrichment)
    official_title: Optional[str] = None
    market_title: Optional[str] = None
    title_basis: Optional[str] = None

class PublicationBlock(BaseModel):
    id: str
    title: str
    venue: Optional[str] = ""
    year: Optional[str] = ""
    authors: Optional[str] = ""
    links: List[str] = Field(default_factory=list)
    notes: Optional[str] = ""

class ProjectBlock(BaseModel):
    id: str
    title: str
    context: Optional[str] = ""
    links: List[str] = Field(default_factory=list)
    start: Optional[str] = ""
    end: Optional[str] = ""
    bullets: List[Bullet] = Field(default_factory=list)
    tags: BlockTags = Field(default_factory=BlockTags)

class EducationBlock(BaseModel):
    id: str
    degree: str
    institution: str
    location: Optional[str] = ""
    start: Optional[str] = ""
    end: Optional[str] = ""
    grade: Optional[str] = ""
    modules: List[str] = Field(default_factory=list)
    notes: Optional[str] = ""

class PersonLinks(BaseModel):
    linkedin: str = ""
    github: str = ""
    website: str = ""

class Person(BaseModel):
    full_name: str
    location: str = ""
    email: str = ""
    phone: str = ""
    links: PersonLinks = Field(default_factory=PersonLinks)

class Headline(BaseModel):
    id: str
    text: str

class Summary(BaseModel):
    id: str
    text: str

class SkillCategory(BaseModel):
    name: str
    items: List[str] = Field(default_factory=list)

class Skills(BaseModel):
    categories: List[SkillCategory] = Field(default_factory=list)

class Profile(BaseModel):
    person: Person
    headlines: List[Headline] = Field(default_factory=list)
    summaries: List[Summary] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    interests: str = ""
    certifications: List[str] = Field(default_factory=list)

class Blocks(BaseModel):
    experience: List[ExperienceBlock] = Field(default_factory=list)
    projects: List[ProjectBlock] = Field(default_factory=list)
    education: List[EducationBlock] = Field(default_factory=list)
    publications: List[PublicationBlock] = Field(default_factory=list)

class IncludeExclude(BaseModel):
    experience: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)

class IncludeRule(BaseModel):
    role_key: str
    include: IncludeExclude = Field(default_factory=IncludeExclude)
    exclude: IncludeExclude = Field(default_factory=IncludeExclude)

class SummaryVariant(BaseModel):
    role_key: str
    summary_id: str

class Variants(BaseModel):
    summary_by_role: List[SummaryVariant] = Field(default_factory=list)
    include_rules: List[IncludeRule] = Field(default_factory=list)

class ResumeForm(BaseModel):
    resume_schema_version: int = 1
    profile: Profile
    blocks: Blocks
    variants: Optional[Variants] = None

class JobSpec(BaseModel):
    raw_text: str
    keywords: List[str] = Field(default_factory=list)
    title: str = ""


class JobListing(BaseModel):
    id: str
    title: str
    company: str
    location: str = ""
    salary_raw: str = ""
    employment_type: str = ""
    description_full: str = ""
    url: str = ""
    apply_url: str = ""
    source: Literal["linkedin", "indeed", "reed", "adzuna"] = "reed"
    easy_apply: bool = False
    posted_date: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    fit_score: Optional[float] = None
    skill_gaps: Optional[List[str]] = None
    apply_status: Literal["none", "queued", "applied", "failed", "skipped"] = "none"

    # Convenience aliases used by the frontend and existing API contract
    @property
    def salary(self) -> str:
        return self.salary_raw

    @property
    def summary(self) -> str:
        return (self.description_full or "")[:280]

    @property
    def posted(self) -> str:
        return self.posted_date

    @property
    def type(self) -> str:
        return self.employment_type
