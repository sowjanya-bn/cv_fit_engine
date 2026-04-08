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
      degree: "MSc Data Science and Artificial Intelligence",
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

  achievements: [
    {
      title: "First-author paper accepted at ESWC 2026",
      detail: "'Competency Questions as Executable Plans: a Controlled RAG Architecture for Cultural Heritage Storytelling' — European Semantic Web Conference, arXiv:2604.02545"
    }
  ],

  skills: {
    "Languages":   ["Python", "Java", "SQL"],
    "Frameworks":  ["Spring Boot", "Spring WebFlux", "FastAPI", "Apache Camel", "MuleSoft"],
    "AI / ML":     ["Retrieval-Augmented Generation", "LLMs", "Knowledge Graphs", "NLP",
                    "Machine Learning", "SHAP", "XGBoost", "Prompt Engineering"],
    "Semantic Web":["RDF", "SPARQL", "Ontology Modelling", "Schema.org", "Music Meta"],
    "Data / Infra":["Elasticsearch", "Kafka", "MySQL", "Redis", "Docker", "AWS", "CI/CD", "Git"],
    "Integration": ["Apigee", "API Gateways", "HAProxy", "Microservices", "Event-driven systems"]
  },

  certifications: [
    "AI Consulting Micro Internship (Springpod)",
    "Oracle Certified Java Programmer",
    "Oracle Certified Java EE Web Component Developer"
  ],

  experience: [
    {
      id: "e2",
      role: "Summer Research Intern — AI & Knowledge Graphs",
      co: "University of Liverpool",
      dates: "Jun–Jul 2025",
      bullets: [
        "Built Python LLM pipelines for structured metadata extraction from semi-structured data sources.",
        "Modelled and queried knowledge graphs using RDF and SPARQL for grounded, structured retrieval.",
        "Developed evaluation frameworks to assess consistency, grounding, and reliability of AI-generated outputs.",
        "Designed reproducible workflows comparing retrieval strategies; analysed trade-offs to optimise pipeline performance."
      ],
      tags: ["rag", "llm", "knowledge-graphs", "nlp", "evaluation", "python", "rdf", "sparql"]
    },
    {
      id: "e3",
      role: "Programmer",
      co: "Tata Consultancy Services, UK",
      dates: "Apr 2022–Feb 2025",
      bullets: [
        "Developed and maintained large-scale SIP-based telephony platforms serving millions of subscribers.",
        "Designed high-performance REST APIs for telecom provisioning and network management using Spring Boot.",
        "Engineered distributed data replication pipelines across geographically separated nodes with strong consistency guarantees.",
        "Integrated MuleSoft and Apache Camel workflows for reliable data exchange across enterprise service boundaries.",
        "Built secure Apigee gateway proxies exposing network capabilities to internal and external consumers.",
        "Prototyped Python data tooling and early AI-adjacent analytics features in production environments."
      ],
      tags: ["java", "spring", "api", "distributed", "backend", "python", "kafka", "apigee"]
    },
    {
      id: "e4",
      role: "Development Team Lead",
      co: "Tata Consultancy Services, UK",
      dates: "Apr 2019–Apr 2022",
      bullets: [
        "Led 6-person cross-functional engineering team delivering scalable backend systems on time and within scope.",
        "Designed Elasticsearch-based monitoring and alerting systems improving operational incident response.",
        "Drove architectural decisions to improve system reliability, fault tolerance, and horizontal scalability.",
        "Ensured GDPR compliance through structured data governance and retention policy implementation."
      ],
      tags: ["lead", "architecture", "elasticsearch", "reliability", "java", "gdpr"]
    },
    {
      id: "e5",
      role: "IT Analyst",
      co: "Tata Consultancy Services, India / Norway",
      dates: "Jul 2015–Mar 2019",
      bullets: [
        "Migrated work-order management system to structured jBPM-based workflows, improving operational efficiency.",
        "Built POC fault-handling system enabling network engineers to isolate root causes across full network topology.",
        "Managed GDPR data retention policy review across TCS-managed systems for a major Norwegian provider."
      ],
      tags: ["workflow", "compliance", "java", "jbpm"]
    },
    {
      id: "e6",
      role: "System Engineer → Assistant System Engineer",
      co: "Tata Consultancy Services, India / UK",
      dates: "Jul 2011–Jun 2015",
      bullets: [
        "Designed and built full-stack network provisioning systems for a major British telecom provider.",
        "Integrated front-end and back-end technologies to deliver seamless OSS/BSS service activation workflows.",
        "Conducted rigorous system testing and troubleshooting to maintain production quality standards."
      ],
      tags: ["java", "provisioning", "fullstack", "testing"]
    }
  ],

  projects: [
    {
      id: "p1",
      title: "MSc Dissertation: Knowledge Graph RAG System",
      bullets: [
        "Designed end-to-end KG-first RAG pipeline for personalised narrative generation over a Live Aid knowledge base.",
        "Built and curated 20K+ triple RDF knowledge graph using Music Meta and Schema.org ontologies.",
        "Implemented KG-RAG, Hybrid RAG and Graph RAG retrieval strategies with comparative evaluation.",
        "Developed Python orchestration and evaluation pipelines assessing grounding accuracy, coverage, and coherence.",
        "Analysed retrieval-quality vs generation-performance trade-offs to inform system design and optimisation."
      ],
      tags: ["rag", "kg", "llm", "python", "rdf", "sparql", "evaluation", "research"]
    },
    {
      id: "p3",
      title: "Stock Price ML Analysis",
      bullets: [
        "Engineered features from OHLCV, EPS surprises and news sentiment for pre-market price movement prediction.",
        "Benchmarked XGBoost achieving ~80% accuracy; used SHAP to identify key predictive drivers."
      ],
      tags: ["ml", "xgboost", "shap", "feature-engineering", "python"]
    }
  ]
};

const ROLES = [
  {
    id: "kg",
    label: "Knowledge Graph / Semantic AI Engineer",
    fit: 95,
    pitch: "Your strongest and most differentiated position. ESWC 2026 first-author paper + KG-RAG dissertation + RDF/SPARQL expertise + production engineering is exceptionally rare. Very few engineers have this combination. Low supply, rising demand.",
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

    // What to paste into "additional context" for best results
    additionalContext: `Seeking Knowledge Graph or Semantic AI roles where RDF, SPARQL, and ontology design are core to the work — not just a nice-to-have. I have a first-author paper accepted at ESWC 2026 on controlled RAG architectures for knowledge graphs, and an MSc dissertation building a 20K+ triple RDF knowledge graph with multiple RAG retrieval strategies. I am not a pure backend engineer trying to move into AI — I have published research in this specific domain. Open to roles in cultural heritage, publishing, life sciences, enterprise knowledge management, or any domain that takes knowledge representation seriously. Strong Python. Production engineering background means I can build and deploy, not just prototype.`,

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

    additionalContext: `Looking for roles where RAG, LLMs, and production AI systems are the core of the work. I have a first-author publication at ESWC 2026 on controlled RAG architectures, an MSc dissertation implementing multiple RAG retrieval strategies over a knowledge graph. I bring something unusual: rigorous evaluation methodology from research experience combined with 13 years of production engineering — I know how to build AI systems that are reliable, not just demos. Particularly interested in roles where grounding, factual accuracy, and evaluation matter (not just "prompt and hope"). Python-first. Open to early-stage startups or established teams building serious AI products.`,

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

    additionalContext: `Applied AI researcher with a first-author paper accepted at ESWC 2026 ('Competency Questions as Executable Plans: a Controlled RAG Architecture for Cultural Heritage Storytelling', arXiv:2604.02545) and an MSc dissertation on knowledge-graph-backed RAG systems. I sit at the intersection of knowledge representation, retrieval-augmented generation, and evaluation — a combination that is practically rare in industry. My research is applied by design: I build and measure systems, not just theorise. 13 years of production engineering means I can take a research idea to deployment. Looking for roles in industry R&D or applied science teams where the work leads to published output or shipped systems — ideally both. Especially interested in NLP, information retrieval, knowledge-intensive NLP, and grounded generation.`,

    fitClass: "badge-green",
    fitLabel: "Strong fit — industry / applied"
  }
];
