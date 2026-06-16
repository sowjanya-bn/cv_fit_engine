/**
 * profile.js — Sowjanya's resume data
 * Edit this file to update your profile without touching app logic.
 */

const PROFILE = {
  name: "Naga Sowjanya Barla",
  location: "Liverpool, UK",
  email: "nagasowjanya.barla@gmail.com",
  phone: "+44 7440 115 316",
  linkedin: "https://www.linkedin.com/in/naga-sowjanya-barla",
  github: "https://github.com/sowjanya-bn",

  education: [
    {
      degree: "MSc Data Science and Artificial Intelligence (Distinction)",
      inst: "University of Liverpool, UK",
      year: "2026",
      note: "Dissertation: RAG-based Digital Storytelling on Music Knowledge Graphs"
    },
    {
      degree: "B.E. Electronics and Communication Engineering",
      inst: "GITAM University, India",
      year: "2011"
    }
  ],

  skills: {
    "Applied AI":         ["RAG", "KG-RAG", "LLM orchestration", "knowledge-graph-backed retrieval", "conversational AI", "evaluation frameworks", "NLP", "prompt engineering", "SHAP", "XGBoost"],
    "Semantic Web":       ["RDF", "SPARQL", "ontology modelling", "knowledge graphs"],
    "Backend Engineering":["Java", "Spring Boot", "Spring WebFlux", "Python", "FastAPI", "REST APIs", "distributed systems", "Apache Camel", "MuleSoft", "Apigee", "microservices", "event-driven systems"],
    "Cloud & Infrastructure": ["AWS", "Docker", "Kafka", "Elasticsearch", "Redis", "MySQL", "SQL", "CI/CD", "Git"]
  },

  certifications: [
    "TM Forum Frameworx Foundation (eTOM, SID and TAM)",
    "Professional Scrum Master (PSM I), Scrum.org",
    "Oracle Certified Java Programmer",
    "Oracle Certified Java EE Web Component Developer"
  ],

  experience: [
    {
      id: "exp_001",
      role: "AI Research Engineer",
      co: "University of Liverpool, UK",
      dates: "Apr 2026–Present",
      bullets: [
        "Designing and building a voice-controlled, knowledge-graph-grounded conversational AI system for museum human-robot interaction, integrating RAG, SPARQL retrieval, LLM orchestration and embodied dialogue.",
        "Architecting a layered system that separates real-time interaction, semantic reasoning, evidence validation and response planning, with explicit handling of uncertainty, conflicting evidence and provenance-heavy answers.",
        "Implementing coordination logic to manage latency trade-offs, clarification decisions and transitions between fast conversational responses and slower KG-RAG reasoning steps.",
        "Evaluating KG-RAG configurations against factual grounding, response latency and conversational smoothness to inform production-minded design decisions."
      ],
      tags: ["rag", "kg-rag", "llm-orchestration", "knowledge-graphs", "sparql", "evaluation", "conversational-ai", "python", "rdf"]
    },
    {
      id: "exp_002",
      role: "Research Intern",
      co: "University of Liverpool, UK",
      dates: "Jun–Jul 2025",
      bullets: [
        "Built Python LLM pipelines for structured metadata extraction, entity and event modelling, relationship extraction and provenance capture from cultural heritage records.",
        "Modelled RDF knowledge graphs and developed SPARQL query patterns to support grounded retrieval, evidence-backed generation and narrative consistency checks.",
        "Designed evaluation workflows for grounding, retrieval coverage, latency and narrative quality across KG-RAG, Hybrid RAG and Graph RAG configurations.",
        "Ran reproducible experiments comparing retrieval strategies and LLM backends, translating findings into practical pipeline design decisions."
      ],
      tags: ["rag", "llm", "knowledge-graphs", "evaluation", "sparql", "rdf", "python", "research"]
    },
    {
      id: "exp_003",
      role: "Senior Backend Engineer",
      co: "Tata Consultancy Services, UK",
      dates: "Apr 2019–Feb 2025",
      bullets: [
        "Built production REST APIs and distributed data replication pipelines for large-scale SIP telephony platforms, supporting high-volume provisioning workflows with strong consistency guarantees across geographically separated datacentres.",
        "Designed Apigee API gateway proxies and enterprise service integrations using Apache Camel and MuleSoft, enforcing OAuth2, rate-limiting and reliable asynchronous message exchange across multi-region infrastructure.",
        "Led a cross-functional engineering team delivering backend systems for telecom platforms, coordinating design, development, testing and production support across a multi-year programme.",
        "Architected Elasticsearch-based observability and alerting capabilities, improving diagnosis of service failures and driving reliability improvements including fault isolation and graceful degradation patterns.",
        "Supported GDPR-related data retention, access review and audit logging across production systems, translating compliance requirements into technical implementation plans."
      ],
      tags: ["distributed-systems", "api-design", "backend-development", "observability", "reliability", "gdpr", "java", "python", "apigee", "apache-camel", "mulesoft", "elasticsearch"]
    },
    {
      id: "exp_004",
      role: "Backend Systems Engineer",
      co: "Tata Consultancy Services, India / Norway / UK",
      dates: "Jul 2011–Mar 2019",
      bullets: [
        "Designed and delivered full-stack network provisioning systems in Java for large-scale telecom platforms, integrating OSS/BSS components across end-to-end service activation workflows.",
        "Migrated legacy work-order management systems to jBPM-orchestrated workflows, reducing order-to-activation cycle times and improving operational throughput.",
        "Built a fault isolation proof-of-concept using network topology graph traversal, enabling faster and more precise root-cause diagnosis for field engineers.",
        "Supported GDPR data retention audits and implemented automated purge workflows across multiple production systems, alongside system testing and performance tuning to maintain production SLAs."
      ],
      tags: ["backend-development", "provisioning-systems", "workflow-design", "compliance", "graph-traversal", "java", "jbpm"]
    }
  ],

  projects: [
    {
      id: "proj_001",
      title: "Stock Price ML Analysis",
      bullets: [
        "Engineered features from OHLCV data, earnings surprises and news sentiment to predict pre-market price movement using XGBoost, applying SHAP analysis to interpret feature importance and identify key predictors."
      ],
      tags: ["ml", "xgboost", "shap", "feature-engineering", "python"]
    }
  ],

  publications: [
    {
      title: "Evaluating Knowledge Graph-Augmented Generation for Factual Grounding in Conversational Museum AI",
      venue: "ESWC 2026 (Extended Semantic Web Conference)",
      year: "2026",
      note: "Peer-reviewed. Evaluates KG-RAG configurations for factual grounding, latency and conversational coherence in museum human-robot interaction."
    }
  ]
};

const ROLES = [
  {
    id: "kg",
    label: "Knowledge Graph / Semantic AI Engineer",
    fit: 95,
    pitch: "Your strongest and most differentiated position. KG-RAG dissertation + RDF/SPARQL expertise + production engineering is exceptionally rare. Very few engineers have this combination. Low supply, rising demand.",
    companies: "Ontotext, Stardog, Elsevier, BBC R&D, NHS Digital, Wolfram, Semantic Web Company, Pool Party, Cambridge Semantics, Eccenca, Metaphacts, data.world, cultural heritage tech orgs",
    keySkills: ["RDF", "SPARQL", "Knowledge Graphs", "RAG", "Ontology Modelling", "LLMs", "Python", "Graph Databases"],

    // All the job titles this role actually gets posted under
    searchTitles: [
      "Knowledge Graph Engineer",
      "Semantic Web Engineer",
      "Ontology Engineer",
      "Knowledge Engineer",
      "Graph Data Engineer",
      "Linked Data Engineer",
      "AI Knowledge Engineer",
      "Knowledge Representation Engineer",
      "Semantic AI Engineer",
      "Knowledge Graph Developer",
      "Data Knowledge Engineer",
      "RDF Engineer",
    ],

    fitClass: "badge-green",
    fitLabel: "Strongest fit"
  },

  {
    id: "ai",
    label: "AI / LLM Engineer",
    fit: 85,
    pitch: "Strong fit. Published RAG research, MSc dissertation and TCS backend scale gives you solid credentials. Your research depth and publication give a real edge over the many bootcamp-level candidates flooding this space.",
    companies: "AI-native startups (RAG products, copilots, document AI), enterprise AI teams, Anthropic partners, NHS AI units, legal tech (Luminance, Relativity), FinTech AI (Thought Machine, Monzo AI), publishing AI (Springer, Reuters)",
    keySkills: ["RAG", "LLMs", "Python", "Prompt Engineering", "Knowledge Graphs", "Evaluation Frameworks", "FastAPI", "Vector Databases"],

    searchTitles: [
      "AI Engineer",
      "LLM Engineer",
      "Generative AI Engineer",
      "RAG Engineer",
      "AI/ML Engineer",
      "Machine Learning Engineer",
      "NLP Engineer",
      "Conversational AI Engineer",
      "AI Software Engineer",
      "Applied AI Engineer",
      "Senior AI Engineer",
      "AI Developer",
      "Large Language Model Engineer",
      "AI Integration Engineer",
      "Retrieval Engineer",
      "AI Platform Engineer",
    ],

    fitClass: "badge-green",
    fitLabel: "Strong fit"
  },

  {
    id: "ml",
    label: "ML / Data Engineer",
    fit: 68,
    pitch: "Moderate fit. XGBoost project and feature engineering are real, but you lack deep MLOps or data platform background. Best positioned at orgs that need ML-aware engineers rather than pure ML specialists. Your research rigour is a differentiator here.",
    companies: "FinTech (Monzo, Starling, Wise), InsurTech (Tractable), HealthTech (Babylon, Sensyne), NHS data teams, analytics platforms (Palantir, Databricks customers), scale-ups with small DS teams",
    keySkills: ["Python", "XGBoost", "SHAP", "SQL", "Elasticsearch", "Feature Engineering", "Kafka", "Data Pipelines"],

    searchTitles: [
      "Machine Learning Engineer",
      "ML Engineer",
      "Data Scientist",
      "Senior Data Scientist",
      "Applied Data Scientist",
      "AI/ML Engineer",
      "Data Engineer",
      "ML Platform Engineer",
      "Research Scientist",
      "Quantitative Analyst",
      "Data Science Engineer",
      "Analytics Engineer",
    ],

    additionalContext: `Looking for ML or data science roles where research rigour matters alongside engineering delivery. I have hands-on ML experience (XGBoost, SHAP, feature engineering on financial time-series data) and a strong evaluation mindset from published AI research. My background is unusual: 13 years of production data systems (pipelines, Elasticsearch, Kafka, distributed data replication) combined with recent AI/ML research. I can own the full lifecycle from data to deployed model — not just notebook work. Particularly interested in domains where interpretability and model trust matter (FinTech, HealthTech, regulated industries). Less interested in pure data warehousing or ETL-only roles.`,

    fitClass: "badge-amber",
    fitLabel: "Moderate fit"
  },

  {
    id: "java",
    label: "Java / Backend Engineer (AI-adjacent)",
    fit: 88,
    pitch: "Deep competence — 13 years of Java, Spring, Kafka, distributed systems is real. Best pursued as 'backend engineer building AI systems' rather than pure backend, so your AI credentials add value rather than being ignored. Avoids the crowded pure-AI market.",
    companies: "Banks (HSBC, Barclays tech), FinTech infrastructure, telecom (BT, Vodafone tech), enterprise SaaS with AI features, large system integrators (Accenture AI, IBM iX), government digital (CDDO, HMRC digital)",
    keySkills: ["Java", "Spring Boot", "Kafka", "Apigee", "MuleSoft", "REST APIs", "Microservices", "Elasticsearch", "Python"],

    searchTitles: [
      "Senior Java Engineer",
      "Senior Software Engineer",
      "Backend Engineer",
      "Java Developer",
      "Senior Backend Developer",
      "Software Engineer (Java)",
      "API Engineer",
      "Integration Engineer",
      "Platform Engineer",
      "Senior Software Developer",
      "Java Spring Engineer",
      "Microservices Engineer",
      "Enterprise Software Engineer",
    ],

    additionalContext: `Senior Java engineer (13 years, Spring Boot, Kafka, Apigee, MuleSoft, distributed systems at telecom scale) now also building AI-powered systems. I bring something most pure-backend candidates don't: published AI research and hands-on LLM/RAG implementation. Looking for backend roles where there is genuine AI/ML work to be done — building APIs for AI systems, integrating LLMs into production services, or working on platforms that power AI products. Not looking for maintenance-only legacy work. Strong on reliability, compliance (GDPR), and API design. The AI background means I understand what the ML teams actually need from the infrastructure.`,

    fitClass: "badge-navy",
    fitLabel: "High competence — frame as AI-adjacent"
  },

  {
    id: "research",
    label: "Applied AI Researcher",
    fit: 78,
    pitch: "Strong fit for company-side applied research. Your ESWC 2026 paper shows you can do rigorous work and publish it. RAG evaluation frameworks + KG-grounded generation + production engineering makes you rare: a researcher who ships. Target industry labs and R&D divisions — not academic faculty.",
    companies: "BBC R&D, Microsoft Research Cambridge, Amazon Science, Google DeepMind (applied), Hugging Face, Cohere, Thomson Reuters Labs, Elsevier Labs, Springer Nature tech, BL Labs, Wellcome Trust, NHS AI Lab, The Alan Turing Institute (industry fellows), Faculty AI, Wayve, PolyAI",
    keySkills: ["RAG", "Knowledge Graphs", "NLP", "Evaluation Frameworks", "LLMs", "RDF", "SPARQL", "Python", "Research Methods", "Technical Writing"],

    searchTitles: [
      "Applied Scientist",
      "Research Engineer",
      "AI Research Engineer",
      "Applied AI Researcher",
      "Research Scientist",
      "Applied Research Scientist",
      "NLP Research Engineer",
      "AI Scientist",
      "Machine Learning Researcher",
      "Applied ML Researcher",
      "Senior Research Engineer",
      "Conversational AI Researcher",
      "Knowledge Graph Researcher",
      "Computational Linguist",
      "AI Research Scientist",
    ],
    fitClass: "badge-green",
    fitLabel: "Strong fit — industry / applied"
  }
];
