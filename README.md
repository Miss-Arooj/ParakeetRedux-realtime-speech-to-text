# Real-Time Speech-to-Text Dashboard

Real-time PCM audio transcription over a WebSocket, with partial/final transcript handling and a browser dashboard. Includes a MongoDB-backed custom vocabulary manager with explicit variation correction and fuzzy matching.

## Highlights

- Real-time audio streaming from browser to backend using WebSockets.
- Partial and finalized transcription flow.
- Custom vocabulary CRUD backed by MongoDB.
- Explicit recognized-variation correction and fuzzy matching.
- Browser dashboard served by FastAPI.

## Technology Stack

Python, FastAPI, WebSockets, Moondream Parakeet Redux, MongoDB, Motor, NumPy

## Configuration

Copy `.env.example` to `.env` and set your MongoDB connection details. Never commit `.env`. The application validates the MongoDB settings during startup.

## Repository Contents

- `main.py` — application entry point containing the backend logic and FastAPI application.
- `requirements.txt` — Python dependencies.
- `.gitignore` — excludes local environments, secrets, datasets, and model artifacts.
- `screenshots/` — screenshots for project documentation.

## Setup

1. Clone this repository.
2. Create and activate a virtual environment.
3. Install the dependencies.

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Demo Videos

### 1. Real-Time Speech-to-Text Transcription

This demonstration tests the application's real-time speech recognition functionality. Spoken sentences are captured through the browser microphone and converted into text, showcasing the transcription process and live transcript updates.

https://github.com/user-attachments/assets/f82dbd75-5615-4dd8-8c8d-b86f73924a4d

### 2. Custom Vocabulary Recognition

This demonstration tests the custom vocabulary feature. A specific word and its variations are added to the vocabulary manager to evaluate how the system recognizes and corrects custom terms during transcription.

https://github.com/user-attachments/assets/5374109d-630c-42a9-8440-1d85290e7862

## Run / Reproduce

The application requires a reachable MongoDB database and downloads/initializes the Parakeet Redux model at startup.

1. Create a local `.env` file from `.env.example`.
2. Add your MongoDB connection details.
3. Run the application:

```bash
uvicorn main:app --host 127.0.0.1 --port 5005
```

Open the dashboard in your browser:

```text
http://127.0.0.1:5005
```

Allow microphone access in your browser to start testing speech transcription.

The application loads the Parakeet Redux model on CPU.

## Limitations and Future Improvements

- Transcription performance depends on the available hardware and speech recognition model.
- Further evaluation is needed to measure transcription accuracy and response latency.
- Future improvements may include support for additional languages and enhanced transcription accuracy, including better noise handling and Voice Activity Detection (VAD).
