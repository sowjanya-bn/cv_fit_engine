from __future__ import annotations
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

class ResumeForm(BaseModel):
    resume_schema_version: int = 1
    profile: Profile
    blocks: Blocks

class JobSpec(BaseModel):
    raw_text: str
    keywords: List[str] = Field(default_factory=list)
    title: str = ""
