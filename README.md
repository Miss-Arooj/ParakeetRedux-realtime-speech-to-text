# Real-Time Speech-to-Text Dashboard

Real-time PCM audio transcription over a WebSocket, with partial/final transcript handling and a browser dashboard. Includes a MongoDB-backed custom vocabulary manager with explicit variation correction and fuzzy matching.

## Highlights

- Real-time audio streaming from browser to backend using WebSockets.
- Partial and finalized transcription flow.
- Custom vocabulary CRUD backed by MongoDB.
- Explicit recognized-variation correction and fuzzy matching.
- Browser dashboard served by FastAPI.

## Technology stack

Python, FastAPI, WebSockets, Moondream Parakeet Redux, MongoDB, Motor, NumPy

## Configuration

Copy `.env.example` to `.env` and set your MongoDB connection details. Never commit `.env`. The application validates the MongoDB settings during startup.

## Repository contents

- `main.py` — original project notebook or application entry point.
- `requirements.txt` — Python dependencies.
- `.gitignore` — excludes local environments, secrets, datasets, and model artifacts.
- `screenshots/` — spaces for project documentation and genuine screenshots.

## Setup

1. Clone this repository.
2. Create and activate a virtual environment.
3. Install the dependencies.
4. Follow the project-specific instructions below.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

## Run / reproduce

The app requires a reachable MongoDB database and downloads/initializes the Parakeet Redux model at startup. Create a local `.env` file from `.env.example`, fill in your own MongoDB settings, then run:

```bash
uvicorn main:app --host 127.0.0.1 --port 5005
```

Open `http://127.0.0.1:5005`. Allow microphone access in the browser.

Run with `uvicorn main:app --host 127.0.0.1 --port 5005`. Requires MongoDB and the Parakeet Redux model runtime. The app loads the model on CPU.

## Limitations and Future Improvements

- Transcription performance depends on the available hardware and speech recognition model.
- Further evaluation is needed to measure transcription accuracy and response latency.
- Future improvements may include support for additional languages and enhanced transcription accuracy (handling noise and adding VAD).
