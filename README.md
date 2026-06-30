# Eightfold Internship Assignment

Python pipeline that ingests **recruiter CSV** (structured) and **resume PDF** (unstructured), then produces one **canonical candidate profile** with normalization, confidence-based merging, provenance, config-driven projection, and JSON Schema validation.



## How to Run the CLI

### 1. Clone the repository

```bash
git clone https://github.com/aarifzz/eightfold-internship-assignment.git
cd eightfold-internship-assignment
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

**Windows (CMD)**

```bash
.venv\Scripts\activate
```

### 3. Install the package

```bash
pip install -r requirements.txt
python -m pip install -e .
```

### 4. Run the pipeline (default configuration)

```bash
python -m eightfold_profile --csv samples/recruiter.csv --pdf samples/resume.pdf --config config/sample_config.json --pretty
```

### 5. Run with the minimal configuration

```bash
python -m eightfold_profile --csv samples/recruiter.csv --pdf samples/resume.pdf --config config/minimal_config.json --pretty
```


### 6. Run the tests

```bash
pytest
```

**CLI flags**

| Flag | Description |
|------|-------------|
| `--csv` | Recruiter CSV path (required) |
| `--pdf` | Resume PDF path (required; missing/malformed PDF falls back to CSV-only) |
| `--config` | Runtime JSON config |
| `--candidate-id` | Select row when CSV has multiple candidates |
| `--pretty` | Pretty-print JSON to stdout |



## Sample input

**Recruiter CSV** (`samples/recruiter.csv`):

```csv
candidate_id,first_name,last_name,email,phone,location,current_title,current_company,skills,...
CAND-1001,Jane,Doe,jane.doe@example.com,(415) 555-0199,"San Francisco, CA",...
```

**Resume PDF** (`samples/resume.pdf`): machine-readable text with `EXPERIENCE`, `EDUCATION`, and `SKILLS` sections. A conflicting work email and phone are included to exercise merging.

## Sample output (excerpt)

```json
{
  "candidate_id": "CAND-1001",
  "full_name": "Jane Doe",
  "emails": [
    {"value": "jane.doe@example.com", "confidence": 0.99, "primary": true},
    {"value": "jane.doe@work-email.com", "confidence": 0.88, "primary": false}
  ],
  "location": {
    "city": "San Francisco",
    "region": "CA",
    "country": "US",
    "formatted": "San Francisco, CA"
  },
  "skills": [
    {"name": "Python", "confidence": 0.95, "sources": ["recruiter_csv", "resume_pdf"]}
  ],
  "experience": [
    {
      "title": "Senior Software Engineer",
      "company": "Acme Corp",
      "start": "2022-01",
      "summary": "Built APIs and data pipelines..."
    }
  ],
  "education": [
    {
      "institution": "State University",
      "degree": "B.S",
      "field": "Computer Science",
      "end_year": 2018
    }
  ],
  "overall_confidence": 0.89
}
```




## Tests

Run all tests:

```bash
pytest
```

The repository includes tests for:

- Parsing
- Normalization
- Merging
- Canonical profile generation
- Validation
- Pipeline execution
- Provenance projection

## License

MIT (sample / educational project)
