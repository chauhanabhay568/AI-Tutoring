# AI Tutoring Assistant

A personalised AI-powered tutoring web application built with Streamlit. Students upload their study material, chat with an AI tutor that answers questions using that material as context (RAG), generate custom quizzes, and track their learning preferences — all tailored to their individual goals and understanding level.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How the RAG Pipeline Works](#how-the-rag-pipeline-works)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Usage Guide](#usage-guide)
- [Admin Access](#admin-access)
- [Known Limitations](#known-limitations)

---

## Features

| Feature | Description |
|---|---|
| RAG-powered Topic Help | Upload a PDF or TXT → chat with an AI tutor that answers from your document |
| AI Quiz Generator | GPT-4 generates MCQ quizzes, evaluates answers, gives study recommendations |
| Student Profiles | Save subjects, understanding level, confidence, goals, preferred language |
| Pre Survey | Collect feedback on traditional teaching methods before using the AI system |
| Post Survey | Collect feedback on the AI tutoring experience after using it |
| Admin Dashboard | Download all survey responses as CSV |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Chat (Topic Help) | OpenAI GPT-3.5-turbo |
| Quiz + Feedback | OpenAI GPT-4 |
| Embeddings | SentenceTransformers — all-MiniLM-L6-v2 |
| Vector Store | ChromaDB (local, persistent) |
| Student Profiles | MongoDB Atlas |
| Auth + Surveys | SQLite |
| Text Chunking | LangChain RecursiveCharacterTextSplitter |
| PDF Parsing | PyMuPDF (fitz) |
| Password Hashing | bcrypt |

---

## Project Structure

```
ai_tutoring/
│
├── main.py                          # Entry point — Login / Register
├── navigation.py                    # Sidebar navigation
├── requirements.txt                 # All dependencies
├── .env                             # Your secrets (never commit this)
├── .env.example                     # Template for setting up .env
│
├── utils/                           # Shared utility modules
│   ├── css_utils.py                 # load_css(), load_bootstrap()
│   ├── rag_utils.py                 # Extract, chunk, embed, retrieve, prompt builder
│   ├── quiz_utils.py                # Generate quiz, parse JSON, score, feedback
│   └── chart_utils.py              # Charts, dataframe helpers, form renderers
│
├── database/                        # All database logic
│   ├── auth_db.py                   # SQLite — user auth (register, login, reset)
│   ├── student_db.py                # MongoDB — student learning profiles
│   ├── survey_traditional_db.py    # SQLite — pre-survey responses
│   └── survey_ai_db.py             # SQLite — post-survey responses
│
├── pages/                           # Streamlit pages
│   ├── topic_help.py                # RAG chat page
│   ├── quiz_help.py                 # Quiz generation and evaluation
│   ├── pre_survey.py                # Traditional teaching survey
│   ├── post_survey.py               # AI tutoring survey
│   ├── my_account.py               # Student profile dashboard
│   └── dummyquiz.txt               # Fallback quiz if API call fails
│
├── styles/
│   └── style.css                    # Custom CSS
│
├── database_files/                  # SQLite .db files (auto-created on first run)
└── doc_db/                          # ChromaDB vector store (auto-created on first run)
```

---

## How the RAG Pipeline Works

RAG stands for **Retrieval-Augmented Generation**. Instead of relying only on GPT's training knowledge, the system retrieves relevant content from the student's own uploaded document and uses it as context when answering.

```
Student uploads PDF or TXT
          │
          ▼
    Extract raw text
    (PyMuPDF for PDF, plain decode for TXT)
          │
          ▼
    Split into chunks
    (500 characters, 50 character overlap)
          │
          ▼
    Embed each chunk
    (SentenceTransformer — all-MiniLM-L6-v2)
          │
          ▼
    Store vectors in ChromaDB
          │
    Student types a question
          │
          ▼
    Embed the question (same model)
          │
          ▼
    Retrieve top 3 most similar chunks
    from ChromaDB
          │
          ▼
    Inject chunks as context into
    GPT-3.5-turbo system prompt
          │
          ▼
    Streamed answer to the student
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-tutoring-assistant.git
cd ai-tutoring-assistant
```

### 2. Create a virtual environment

```bash
# Using uv (recommended)
uv venv

# Or standard Python
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
# Using uv
uv pip install -r requirements.txt

# Or pip
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
OPENAI_API_KEY=your_openai_api_key_here
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
SQLITE_DB_PATH=database_files/user_data.db
```

**Getting the keys:**
- OpenAI API key → [platform.openai.com](https://platform.openai.com)
- MongoDB URI → [mongodb.com/atlas](https://mongodb.com/atlas) (free tier is enough)

### 5. Create required folders

```bash
mkdir -p database_files doc_db
```

### 6. Run the app

```bash
# Using uv
uv run streamlit run main.py

# Or standard
streamlit run main.py
```

The app opens at `http://localhost:8501`

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `MONGODB_URI` | MongoDB Atlas connection string | Yes |
| `SQLITE_DB_PATH` | Path to the SQLite database file | No (defaults to `database_files/user_data.db`) |

---

## Usage Guide

### First time setup
1. Open the app at `http://localhost:8501`
2. Go to the **Register** tab and create an account
3. You will be redirected to the **Pre Survey** — fill it in
4. Go to **My Account** → fill in your subjects, understanding level, learning goals
5. You are now ready to use the system

### Topic Help (RAG Chat)
1. Click **Topic Help** in the sidebar
2. Fill in the preferences form — subject, depth, type of assistance
3. Optionally upload a PDF or TXT file (your notes, textbook chapter etc.)
4. Click **Submit** and start chatting
5. The AI will answer your questions using your uploaded document as context

### Quiz Help
1. Click **Quiz Help** in the sidebar
2. Choose subject, topic, difficulty, number of questions
3. Click **Generate Quiz** and wait for GPT-4 to create it
4. Answer all questions and click **Submit Quiz**
5. See your score, correct answers, and personalised study recommendations

### Post Survey
1. After using the system, click **AI Teaching Survey** in the sidebar
2. Fill in your feedback about the AI tutoring experience

---

## Password Requirements

When registering or resetting your password it must:
- Be at least **8 characters** long
- Contain at least **one letter**
- Contain at least **one number**

---

## Admin Access

To view and download all survey responses, log in with:

```
Email:  admin.com
Name:   admin
```

The admin account skips the student profile requirement and shows a data download page for each survey where you can view responses and export them as CSV.

---

## Known Limitations

- The RAG pipeline only uses the **most recently uploaded** document per session. Uploading a new file replaces the previous one in ChromaDB.
- Quiz generation requires an active OpenAI API connection. If the API is unavailable, a fallback dummy quiz is loaded from `pages/dummyquiz.txt`.
- The app is designed for **single-user sessions** — multiple users on the same machine may share the same ChromaDB session collection.

---

## License

This project is for educational and research purposes.
