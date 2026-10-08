# Campus Customs: Yale merch shop with an AI shopping assistant

MGT 409 (AI Foundations) Homework 4. A storefront for Campus Customs, with a chatbot that answers from the real catalogue and inventory:

- **Frontend:** React + Vite + TypeScript (`frontend/`).
- **Backend:** FastAPI (`backend/main.py`).
- **Chatbot:** a PydanticAI agent (`backend/agent.py`, `tools.py`, `models.py`, `prompts/prompt.md`) using OpenAI models through Yale's Portkey gateway.

How it all fits together is in [`output/harness.md`](output/harness.md).

## Requirements

- Python 3.11+
- Node.js 20+ and npm
- A Portkey API key
- The Campus Customs data pack (not included in this repo)

## 1. Set up the Python environment

From the `hw4/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Install the frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## 3. Add the data pack

The database and product photos are not committed. Put them here:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/
        ├── basic-hoodie-big-yale.jpg
        └── ... (one .jpg per product)
```

- The backend stops with a clear "Database not found" error if the db is missing; it never creates an empty one.
- On startup it adds the one extra column it needs (`chat_messages.model`), so a fresh copy of the db works as-is.

## 4. Create your `.env`

```bash
cp .env.example .env
```

Then edit `.env`:

```
PORTKEY_API_KEY=your_key_here          # required for the chatbot
SESSION_SECRET=your_random_secret_here # optional; signs login sessions
```

- Without `SESSION_SECRET`, a random secret is generated at startup, so everyone is logged out whenever the backend restarts.
- The backend finds `.env` with python-dotenv's `find_dotenv()`, starting in `backend/` and walking up through parent folders. A `.env` in a parent folder also works.
- **Never commit `.env`.** It is in `.gitignore`.

## 5. Run it

Use two terminals.

**Backend** (venv active), from `backend/`:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Frontend**, from `frontend/`:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/media` to the backend on port 8000.

## What's inside

| Path | What it is |
|---|---|
| `backend/main.py` | FastAPI app: products, images, sign-up/login, chat and chat history. |
| `backend/agent.py` | PydanticAI agent: Portkey client, model routing, capped runs, audit trail. |
| `backend/tools.py` | Read-only database tools: description, price, stock, search, similar items. |
| `backend/models.py` | Pydantic types for requests, replies, product cards, tool results and audit entries. |
| `backend/prompts/prompt.md` | The assistant's voice, tool rules and safety rules. |
| `frontend/src/` | Pages (Home, Products, product detail, About, Log in, Create account), the chat panel and the product cards. |
| `output/harness.md` | How the whole system works: database, auth, agent, tools, safety, specs. |
| `output/usability.md`, `output/design.md` | The usability improvements and the visual design, with screenshots. |
| `output/app_check.html` | Playwright site check with screenshots. Open it in a browser. |
| `output/audit_trail.json` | Append-only log of agent tool calls and runs. |
| `AI_prompts.md` | The prompts used to build this project, by problem. |
