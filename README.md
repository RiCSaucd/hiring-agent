# Hiring Agent

<p align="center"><strong>Job-seeker desk + recruiter scorer.</strong> Review your own application, match public listings, prepare packets you approve before applying — and still score candidate PDFs with the original LLM pipeline.</p>

<p align="center">
  <a href="https://www.python.org/downloads/release/python-3110/">
    <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  </a>
  <a href="https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg">
  </a>
  <a href="https://github.com/psf/black">
    <img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-Black-000000.svg">
  </a>
</p>

---

## Contents

- [Application desk (job seeker)](#application-desk-job-seeker)
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation and Setup](#installation-and-setup)
  - [Prerequisites](#prerequisites)
  - [Quick setup with pip](#quick-setup-with-pip)
  - [Ollama models](#ollama-models)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [CLI usage](#cli-usage)
- [Directory layout](#directory-layout)
- [Provider details](#provider-details)
- [Contributing](#contributing)
- [License](#license)

---

## Application desk (job seeker)

Use this when **you** are applying: the agent reviews *your* resume, ranks roles, drafts a cover letter, and tracks applications. It will not POST your materials to Greenhouse, Lever, LinkedIn, or any other employer until you confirm, and even then it only opens their apply URL and records the attempt locally.

The desk runs with the Python standard library plus packages already in this repo (`requests`, `Jinja2`). No LLM is required. If Ollama or Gemini is configured, the original recruiter evaluator is used as an extra signal.

```bash
# Review a resume (markdown, text, or a simple PDF)
python3 -m job_agent review job_agent/data/sample_resume.md --role "senior backend engineer"

# Search the bundled catalog (live Remotive/Jobicy/Arbeitnow are used when reachable)
python3 -m job_agent search --query "python fastapi" --no-live

# Draft a packet, then mark applied after you submit on the employer site
python3 -m job_agent prepare fieldnote-python
python3 -m job_agent apply 1 --confirm

# Local UI
python3 -m job_agent serve --port 8765
```

Open `http://127.0.0.1:8765`. Drop your resume, set a target role, find jobs, prepare a packet, and confirm apply.

Paste any posting the catalog misses. Live job APIs are optional; this environment may block them, which is why a local catalog ships in `job_agent/data/jobs.json`.

---

## Overview

The original recruiter pipeline parses a resume PDF to Markdown, extracts sectioned JSON using a local or hosted LLM, augments the data with GitHub profile and repository signals, then produces an objective evaluation with category scores, evidence, bonus points, and deductions. You can run fully local with Ollama or use Google Gemini.

---

## Architecture

<table>
<tr>
<td>

**Flow**

1. `pymupdf_rag.py` converts PDF pages to Markdown-like text.
2. `pdf.py` calls the LLM per section using Jinja templates under `prompts/templates`.
3. `github.py` fetches profile and repos, classifies projects, and asks the LLM to select the top 7.
4. `evaluator.py` runs a strict-scored evaluation with fairness constraints.
5. `score.py` orchestrates everything end to end and writes CSV when development mode is on.

</td>
<td>

**Key modules**

- `models.py`
  Pydantic schemas and LLM provider interfaces.

- `llm_utils.py`
  Provider initialization and response cleanup.

- `transform.py`
  Normalization from loose LLM JSON to JSON Resume style.

- `prompts/`
  All Jinja templates for extraction and scoring.

</td>
</tr>
</table>

---

## Installation and Setup

### Prerequisites

- **Python 3.11+**

  The repository pins `.python-version` to 3.11.13.

- **One LLM backend** (either of them)

  - **Ollama** for local models
    Install from the [official site](https://ollama.com/), then run `ollama serve`.
  - **Google Gemini** if you have an API key, get it from [here](https://aistudio.google.com/api-keys).

### Quick setup with pip

```bash
$ git clone https://github.com/interviewstreet/hiring-agent
$ cd hiring-agent

$ python -m venv .venv
# Linux or macOS
$ source .venv/bin/activate
# Windows
# .venv\Scripts\activate

$ pip install -r requirements.txt
```

### Ollama Models

Pull the model you want to use. For example:

```bash
$ ollama pull gemma3:4b
```

If you want different results, you can pull other models such as:

```bash
# For higher system configuration
$ ollama pull gemma3:12b

# For lower system configuration
$ ollama pull gemma3:1b
```

---

## Configuration

Copy the template and set your environment variables.

```bash
$ cp .env.example .env
```

**Environment variables**

| Variable         | Values                                      | Description                                                            |
| ---------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `LLM_PROVIDER`   | `ollama` or `gemini`                        | Chooses provider. Defaults to Ollama.                                  |
| `DEFAULT_MODEL`  | for example `gemma3:4b` or `gemini-2.5-pro` | Model name passed to the provider.                                     |
| `GEMINI_API_KEY` | string                                      | Required when `LLM_PROVIDER=gemini`.                                   |
| `GITHUB_TOKEN`   | optional                                    | Inherits from your shell environment, improves GitHub API rate limits. |

Provider mapping lives in `prompt.py` and `models.py`. The `config.py` file has a single flag:

```python
# config.py
DEVELOPMENT_MODE = True  # enables caching and CSV export
```

You can leave it on during iteration. See the next section for details.

---

## How it works

<details>
<summary><b>1) PDF extraction</b></summary>

- `pymupdf_rag.py` and `pdf.py` read the PDF using PyMuPDF and convert pages to Markdown-like text.
- The `to_markdown` routine handles headings, links, tables, and basic formatting.

</details>

<details>
<summary><b>2) Section parsing with templates</b></summary>

- `prompts/templates/*.jinja` define strict instructions for each section
  Basics, Work, Education, Skills, Projects, Awards.
- `pdf.PDFHandler` calls the LLM per section and assembles a `JSONResume` object (see `models.py`).

</details>

<details>
<summary><b>3) GitHub enrichment</b></summary>

- `github.py` extracts a username from the resume profiles, fetches profile and repos, and classifies each project.
- It asks the LLM to select exactly 7 unique projects with a minimum author commit threshold, favoring meaningful contributions.

</details>

<details>
<summary><b>4) Evaluation</b></summary>

- `evaluator.py` uses templates that encode fairness and scoring rules.
- Scores include `open_source`, `self_projects`, `production`, and `technical_skills`, plus bonus and deductions, then an explanation for evidence.

</details>

<details>
<summary><b>5) Output and CSV export</b></summary>

- `score.py` prints a readable summary to stdout.
- When `DEVELOPMENT_MODE=True` it creates or appends a `resume_evaluations.csv` with key fields, and caches intermediate JSON under `cache/`.

</details>

---

## CLI usage

### End to end scoring

Provide a path to a resume PDF.

```bash
$ python score.py /path/to/resume.pdf
```

What happens:

1. If development mode is on, the PDF extraction result is cached to `cache/resumecache_<basename>.json`.
2. If a GitHub profile is found in the resume, repositories are fetched and cached to `cache/githubcache_<basename>.json`.
3. The evaluator prints a report and, in development mode, appends a CSV row to `resume_evaluations.csv`.

---

## Directory layout

```text
.
├── job_agent/          # job-seeker desk (review, match, apply tracker, UI)
│   ├── data/           # sample resume + bundled job catalog
│   ├── web/            # Application Desk UI
│   └── ...
├── tests/
├── score.py            # original recruiter CLI
├── evaluator.py
└── ...
```

---

## Provider details

### Ollama

- Set `LLM_PROVIDER=ollama`
- Set `DEFAULT_MODEL` to any pulled model, for example `gemma3:4b`
- The provider wrapper in `models.OllamaProvider` calls `ollama.chat`

### Gemini

- Set `LLM_PROVIDER=gemini`
- Set `DEFAULT_MODEL` to a supported Gemini model, for example `gemini-2.0-flash`
- Provide `GEMINI_API_KEY`
- The wrapper in `models.GeminiProvider` adapts responses to a unified format

---

## Contributing

Please read the [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines on filing issues, proposing changes, and submitting pull requests. Key principles include:

- Keep prompts declarative and provider-agnostic.
- Validate changes with a couple of real resumes under different providers.
- Add or adjust unit-free smoke tests that call each stage with minimal inputs.

---


## License

[MIT](https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE) © HackerRank
