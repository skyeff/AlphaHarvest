# Alpha Harvest 

**Autonomous scholarly retrieval engine with boolean predicate filtering**

---

## Thesis

Academic literature discovery remains ensnared in manual drudgery—click,
filter, download, repeat . Alpha Harvest excises this tedium via parallel
interrogation of multiple open-access repositories, orchestrating bulk PDF
acquisition through boolean logic whilst you attend to matters of genuine
intellectual consequence.

## Architectural Paradigm

The system operates as a distributed query executor against scholarly metadata
aggregators (CrossRef) with concurrent resolution across four distinct OA
sources (Unpaywall, Semantic Scholar, OpenAlex, CORE). Boolean expressions
parse into predicate closures evaluated against concatenated title+abstract
corpora, culling non-conformant entries *ante* network traversal.

Year-stratified processing ensures constant-memory complexity O(n) per temporal
slice, liberating systems of modest computational endowment from thrashing
under multi-year queries spanning tens of thousands of candidates.

## Epistemic Machinery

### Boolean Predicate Algebra

Expressions nest arbitrarily via parenthetical grouping, honoring conjunction/disjunction precedence:
```
(Graphene OR Carbon_Nanotubes) AND (Catalysis OR Photocatalysis) AND NOT Review
```

Tokenization proceeds recursively, constructing evaluation closures that
short-circuit on falsification—*modus tollens* optimization at the syntax
level.

### Source Hierarchy

1. **Unpaywall**: Publisher repositories + institutional archives
2. **Semantic Scholar**: AI-indexed corpus with citation graph traversal
3. **OpenAlex**: Comprehensive scholarly entity resolution
4. **CORE**: Aggregated repository harvest (>200M papers)
5. **CrossRef Direct**: Metadata-embedded PDF links (fallback heuristic)

Failure at tier *n* cascades to *n+1* with exponential backoff—no candidate abandoned prematurely.

### Validation Heuristics

- **Size threshold**: 10KB minimum (excludes abstract-only stubs)
- **Textual extraction**: 50 chars from initial pages via PyPDF2
- **Content-type verification**: MIME header + URL suffix concordance

False positives (scanned images lacking OCR, paywalled redirects) expunged via
post-download validation with automatic cleanup.

## Deployment Rubric

### Environment 
```bash
python3 -m venv venv
source venv/bin/activate  # POSIX
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Syntax
```bash
python harvest.py \
  --keywords "(Nanocomposites OR Microplastics) AND Remediation" \
  --start 2018 \
  --end 2024 \
  --email scholar@institution.edu \
  --output ./corpus
```

### Parameter Ontology

| Directive | Type | Semantics |
|-----------|------|-----------|
| `--keywords` | str | Boolean query expression (case-sensitive operators) |
| `--start` | int | Temporal lower bound (publication year) |
| `--end` | int | Temporal upper bound (inclusive) |
| `--email` | str | RFC 2822 contact for API politeness protocol |
| `--output` | str | Filesystem destination (created if absent) |

## Execution Phenomenology
```
===========================================================
  Alpha Harvest v0.9.0 — Automated Article Farm
===========================================================

[>] Query: '(CRISPR OR Cas9) AND Therapeutics'
[>] Time span: 2020–2023 (4 years)
[>] Destination: ./papers
------------------------------------------------------------

  >> Year 2020: querying CrossRef...
  [OK] Year 2020: 847 harvested                    

[>>] Processing year 2020: 847 entries...
Year 2020: 100%|████████████████| 847/847 [03:24<00:00, 4.14doc/s]
[#] Year 2020 complete: 312/847 PDFs retrieved
------------------------------------------------------------

  >> Year 2021: querying CrossRef...
  [OK] Year 2021: 1203 harvested                   
...
```

## Artifact Morphology
```
corpus/
├── 2020_Smith_CRISPR_mediated_gene_editing.pdf
├── 2021_Zhang_Cas9_delivery_nanoparticles.pdf
├── 2022_Kumar_Therapeutic_applications.pdf
└── metadata.jsonl
```

### Metadata Schema

Each JSONL entry manifests as:
```json
{
  "doi": "10.1234/example.5678",
  "title": "Novel CRISPR applications in oncology",
  "year": 2023,
  "status": "ok",
  "pdf_url": "https://repository.org/paper.pdf",
  "source": "Unpaywall",
  "version": "publishedVersion",
  "local_path": "./corpus/2023_Johnson_Novel_CRISPR.pdf",
  "size": 2847219
}
```

### Status Taxonomy

| Code | Interpretation |
|------|----------------|
| `ok` | Successfully retrieved & validated |
| `filtered` | Boolean predicate rejection |
| `no_pdf` | Absent across all OA sources |
| `fail` | Network/HTTP error during acquisition |
| `empty` | Insufficient extractable text content |
| `corrupt` | Malformed PDF structure |

## Performance Characteristics

- **Concurrency**: 5 threads (tuned for consumer hardware sans thermal throttling)
- **Throughput**: ~4–8 PDFs/minute (network-bound)
- **Memory footprint**: ~150MB baseline + 2KB per candidate entry
- **Rate limiting**: Cooperative delays (50–100ms inter-request) honoring API terms

## Epistemic Constraints

### What This System Achieves

- Bulk acquisition of **legally open-access** scholarly literature
- Boolean logic filtering against metadata (not full-text)
- Year-stratified processing preventing memory exhaustion
- Robust error recovery with granular status tracking

### What It Categorically Does Not

- Circumvent paywalls (respects publisher access controls)
- Provide full-text search (operates on titles/abstracts only)
- Guarantee exhaustive coverage (OA availability ~30% of literature)
- Include preprint servers (arXiv/bioRxiv require dedicated pipelines)

## Troubleshooting Guide 

**Null harvest despite expansive query:**
- Validate boolean syntax (operators must be uppercase: `AND`/`OR`)
- Inspect CrossRef API status (status.crossref.org)
- Broaden temporal range or relax boolean constraints

**Disproportionate `no_pdf` prevalence:**
- Many journals impose 6–24 month embargo periods
- Conference proceedings often lack open repositories
- Recent publications may not yet appear in OA indices

**Thread saturation / system unresponsiveness:**
- Reduce `THREADS` constant (line 6) to `3` or `2`
- Check bandwidth saturation via `nethogs` or equivalent
- Verify disk I/O isn't bottlenecked (SSD recommended)

**JSON decode errors in metadata:**
- Script now auto-sanitizes special characters
- Corrupt lines skipped with warning; harvest continues
- Inspect `metadata.jsonl` manually for anomalies if issues persist

## Ethical Axioms

- Exclusively retrieves content designated as open-access by publishers/repositories
- Implements cooperative rate limiting per API provider guidelines
- User-Agent strings contain contact email for accountability
- No circumvention of `robots.txt` or authentication mechanisms

## Extensibility Vectors

**Custom source integration:**
Append tuple to `process_item()` source list (line 112):
```python
(lambda:(YourCustomAPI(s,doi),None),"YourSource")
```

**Validation criteria modification:**
Adjust `MIN_SIZE`/`MIN_CHARS` constants (line 8) to taste.

**Parallelism tuning:**
Scale `THREADS` (line 6) proportional to available cores/bandwidth.

