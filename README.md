# Evaluation Agent

This service powers the Evaluation Agent, responsible for handling evaluation post interview.
It is built using FastAPI and managed with uv for fast dependency management and execution.

The service runs on port 8001.

---

## 🚀 Tech Stack

* FastAPI
* Uvicorn
* Python
* Pydantic


---

## 📦 Prerequisites

Make sure you have the following installed:

* Python **3.9+**
* pip


Check your installation:

```bash
python --version
pip --version
```

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/JeneshaMalar/keboli-evaluation-agent.git

```

---

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate the environment:

**Mac/Linux**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### 3. Install dependencies using `uv`

This project uses **uv** for fast Python package management and environment handling.

Install `uv` if you don't have it:

```bash
pip install uv
```

or (recommended)

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

---

### 4. Install project dependencies

Install dependencies defined in `pyproject.toml`:

```bash
uv sync
```

This will:

* Create a virtual environment automatically
* Install all dependencies from `pyproject.toml`
* Lock them in `uv.lock`

---



## ▶️ Run the Development Server



```bash
uv run python3 -m app.main
```

The API will start at:

```
http://127.0.0.1:8002
```

---

## 📖 API Documentation

FastAPI automatically generates interactive API documentation.

Swagger UI:

```
http://127.0.0.1:8002/docs
```

ReDoc:

```
http://127.0.0.1:8002/redoc
```

---



## 🔧 Environment Variables

Create a `.env` file in the root directory if your project uses environment variables.

Example:

```
MAIN_BACKEND_URL=http://localhost:8000/api
GROQ_API_KEY=<YOUR API KEY>
GROQ_MODEL=llama-3.3-70b-versatile
```

---

