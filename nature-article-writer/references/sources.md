# Source Notes

These notes document the official and representative sources used to build this skill. Accessed on **2026-04-19**.

## Official skill-design references supplied by the user

- `The Complete Guide to Building Skills for Claude`
- `What are skills?`
- `Using scripts in skills`
- `Specification`
- `Optimizing skill descriptions`
- `Evaluating skill output quality`
- `Overview`

These were used to shape the folder structure, progressive disclosure design, script behaviour, skill description, and optional evals.

## Nature and Nature Portfolio sources used for content

### 1. Nature formatting guide
URL:
- https://www.nature.com/nature/for-authors/formatting-guide

Key points used:
- Nature Articles start with a referenced summary paragraph aimed at readers outside the field.
- Main Nature titles are short and broadly readable.
- The manuscript sequence includes figure legends, Methods, separate Data Availability and Code Availability statements, and end matter.
- Figure legends should begin with a brief title and stay concise.

### 2. Nature initial submission guide
URL:
- https://www.nature.com/nature/for-authors/initial-submission

Key points used:
- Typical Article lengths and display-item counts.
- Methods should contain enough detail for interpretation and replication.
- Data Availability and Code Availability expectations.

### 3. Nature Portfolio guide: `How to write your paper`
URL:
- https://www.nature.com/nature-portfolio/for-authors/write

Key points used:
- prefer active voice
- avoid jargon and unnecessary acronyms
- write for readers outside the immediate discipline
- keep titles comprehensible and searchable

### 4. Nature editorial criteria and processes
URL:
- https://www.nature.com/nature/for-authors/editorial-criteria-and-processes

Key points used:
- main editorial bar for Nature is original research of outstanding importance with interdisciplinary interest

### 5. Nature AI policy
URL:
- https://www.nature.com/nature/editorial-policies/ai

Key points used:
- LLMs are not authors
- AI-assisted copy editing does not need declaration
- human authors remain accountable
- AI-generated images are not allowed for publication

### 6. Nature Portfolio reporting standards and availability of data, materials, code and protocols
URL:
- https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards

Key points used:
- data, materials, code, and protocols should be available without undue restriction
- reporting summaries are required in many research areas and published with accepted papers

### 7. Data availability statements and data citations policy
URL:
- https://www.nature.com/documents/nr-data-availability-statements-data-citations.pdf

Key points used:
- examples and expected structure for data availability statements
- accession numbers, identifiers, and access conditions should be explicit

## Representative journal-format sources used to generalise `portfolio-article` and `portfolio-letter`

These were used to infer common patterns across Nature Portfolio journals, while keeping the skill explicit that exact limits must be checked live.

- Nature Materials content types
  - https://www.nature.com/nmat/content
- Nature Immunology content types
  - https://www.nature.com/ni/content
- Nature Cardiovascular Research content types
  - https://www.nature.com/natcardiovascres/content
- Nature Metabolism content types
  - https://www.nature.com/natmetab/content
- Nature Communications guide to authors and formatting snippets
  - https://www.nature.com/ncomms/submit/guide-to-authors
  - https://www.nature.com/documents/ncomms-formatting-instructions.pdf

## Notes on interpretation

- Nature Portfolio formats vary substantially by journal and article type.
- This skill therefore uses a small set of robust modes plus an explicit instruction to verify the live guide whenever the target journal is known.
- The `human-sounding` layer was also informed by the anti-slop and humanizer patterns present in the user-supplied archive, adapted here for scientific writing rather than casual prose.
