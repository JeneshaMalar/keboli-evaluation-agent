# Keboli – Evaluation Agent

The **Evaluation Agent** is the AI-powered service responsible for analyzing candidate responses and generating structured evaluation results for interview sessions.

It processes the responses collected during the interview and uses **Large Language Models (LLMs)** to assess candidate performance across multiple dimensions such as correctness, reasoning ability, and technical depth.

The Evaluation Agent operates as a **separate microservice** and is triggered by the backend after an interview session is completed.

---

# 1. Project Information

## Overview

The Evaluation Agent performs **automated assessment of candidate responses** collected during the interview process.

While the **Interview Agent** conducts the interview and collects responses, the Evaluation Agent analyzes those responses using LLMs and generates structured evaluation results.

These results include:

* candidate score
* strengths and weaknesses
* skill-based evaluation
* overall interview feedback

The evaluation results are sent back to the backend and stored for recruiter review.

---

## Responsibilities

The Evaluation Agent is responsible for:

* evaluating candidate responses using LLMs
* generating structured interview scores
* providing technical feedback on answers
* analyzing candidate strengths and weaknesses
* generating final interview evaluation reports
* sending evaluation results back to the backend

---

## Key Features

* automated AI-driven candidate evaluation
* structured scoring and feedback generation
* skill-based response analysis
* LLM-powered evaluation engine
* asynchronous evaluation processing
* integration with backend evaluation APIs

---

## Technology Stack

| Component       | Technology        |
| --------------- | ----------------- |
| Language        | Python            |
| AI Integration  | LangGraph         |
| LLM Provider    | Groq              |
| HTTP Client     | httpx             |
| Async Framework | asyncio           |


---

# 2. Architecture Overview

The Evaluation Agent operates as a **dedicated evaluation microservice** that analyzes candidate responses after an interview session is completed.

It receives responses from the backend, evaluates them using LLMs, and returns structured evaluation results.

## System Architecture

```
                   +------------------------+
                   |       FastAPI Backend  |
                   |  (Session Management)  |
                   +-----------+------------+
                               |
                               | Trigger Evaluation
                               |
                               v
                    +-----------------------+
                    |    Evaluation Agent   |
                    |                       |
                    |  - Response Analysis  |
                    |  - LLM Evaluation     |
                    |  - Score Generation   |
                    +-----------+-----------+
                                |
                                v
                        +------------------+
                        |   LLM Provider   |
                        |      (Groq)      |
                        +------------------+
```

---

## Component Responsibilities

### Evaluation Agent Core

Handles:

* candidate response analysis
* evaluation orchestration
* scoring logic
* evaluation report generation

---

### LLM Adapter

The LLM adapter module:

* sends candidate responses to the LLM
* processes model output
* extracts structured evaluation data

---

### Backend Communication

The Evaluation Agent communicates with the backend to:

* receive candidate responses
* trigger evaluation workflows
* return evaluation results

---

# 3. Service Interaction Flow

```
Recruiter Creates Assessment
            |
            v
Backend API
            |
            v
Interview Agent Conducts Interview
            |
            v
Candidate Responses Collected
            |
            v
Responses Stored in Backend
            |
            | Trigger Evaluation
            v
Evaluation Agent
            |
            v
LLM Evaluates Responses
            |
            v
Evaluation Results Generated
            |
            v
Results Sent to Backend
            |
            v
Recruiter Views Results
```

---

# 4. Evaluation Workflow

The Evaluation Agent follows a structured evaluation process.

---

### 1. Evaluation Trigger

After the interview session is completed, the backend sends an evaluation request containing:

* session ID
* candidate responses
* interview context

---

### 2. Response Processing

The agent processes candidate responses and prepares them for evaluation.

---

### 3. LLM-Based Evaluation

Responses are sent to the LLM for evaluation.

The model analyzes:

* correctness
* technical explanation
* reasoning ability
* clarity of answer

---

### 4. Score Generation

The system generates structured scoring including:

* per-question score
* skill-based score
* overall performance score

---

### 5. Feedback Generation

The agent generates feedback such as:

* strengths
* weaknesses


---

### 6. Result Reporting

The evaluation results are sent back to the backend API and stored in the database.

Recruiters can then review the results in the dashboard.

---

# 5. Running the Evaluation Agent Locally

## Prerequisites

Install:

* Python 3.10+
* Docker (optional)

---

# Option 1 – Run with Docker

Clone repository:

```
git clone https://github.com/JeneshaMalar/keboli-evaluation-agent.git
cd keboli-evaluation-agent
```

Build container:

```
docker build -t evaluation-agent .
```

Run container:

```
docker run evaluation-agent
```

---

# Option 2 – Run without Docker

Create virtual environment:

```
python -m venv venv
```

Activate environment:

Linux / Mac

```
source venv/bin/activate
```

Install dependencies:

```
uv sync
```

---

### Start Evaluation Agent

Entry point:

```
main.py
```

Run service:

```
python -m app.main.py
```

---

# 6. Environment Variables

Example `.env` file:

```
MAIN_BACKEND_URL=http://localhost:8000/api
GROQ_API_KEY=<YOUR API KEY>
GROQ_MODEL=llama-3.3-70b-versatile
```

---

# 7. Error Handling and Logging

The Evaluation Agent includes logging mechanisms for:

* evaluation request processing
* LLM communication failures
* backend API errors

These logs help diagnose issues during evaluation workflows.

---

# Author

**Jenesha Malar**

Keboli – Evaluation Agent Development


