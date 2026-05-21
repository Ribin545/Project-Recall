@echo off
:: Project Recall startup helper.
::
:: Responsibilities:
:: 1. Verify Python is available
:: 2. Install local dependencies
:: 3. Check whether Ollama is running
:: 4. Build extracted memories / vector index if missing
:: 5. Launch the FastAPI app and open the browser
chcp 65001 >nul
title Project Recall - Mentra Chat
echo ==========================================
echo   Project Recall - Mentra Baseline Chat
echo ==========================================
echo.

:: --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: --- Install dependencies ---
echo [1/5] Installing dependencies...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [WARNING] pip install had issues, continuing anyway...
) else (
    echo         Dependencies OK.
)

:: --- Check Ollama ---
echo [2/5] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama does not appear to be running on localhost:11434.
    echo           Chat responses will fail until Ollama is started.
    echo           Continuing anyway for the memory system demo...
) else (
    echo         Ollama is running.
)

:: --- Extract memories if needed ---
echo [3/5] Checking memory data...
if not exist "data\sample_project_recall_sessions.json" (
    echo         Generating sample sessions...
    python generate_project_recall_sessions.py
    if errorlevel 1 (
        echo [ERROR] Session generation failed.
        pause
        exit /b 1
    )
) else (
    echo         Sample sessions found.
)

if not exist "data\extracted_memories_project_recall.json" (
    echo         Extracting memories from session archive...
    python app/memory_extractor.py
    if errorlevel 1 (
        echo [ERROR] Memory extraction failed.
        pause
        exit /b 1
    )
) else (
    echo         Extracted memories found.
)

:: --- Build vector index if needed ---
if not exist "data\chroma_project_recall_db" (
    echo         Building vector index...
    python app/build_memory_index.py
    if errorlevel 1 (
        echo [ERROR] Index build failed.
        pause
        exit /b 1
    )
) else (
    echo         Vector index found.
)

:: --- Load env ---
echo [4/5] Loading configuration...
set PROVIDER=
set MODEL=
for /f "tokens=1,* delims==" %%a in ('findstr /R "^LLM_PROVIDER= ^OLLAMA_MODEL= ^GEMINI_MODEL=" .env 2^>nul') do (
    if /I "%%a"=="LLM_PROVIDER" set PROVIDER=%%b
    if /I "%%a"=="OLLAMA_MODEL" if not defined MODEL set MODEL=%%b
    if /I "%%a"=="GEMINI_MODEL" if /I "!PROVIDER!"=="gemini" set MODEL=%%b
)
if not defined PROVIDER set PROVIDER=ollama
if /I "%PROVIDER%"=="gemini" (
    if not defined MODEL set MODEL=gemini-2.0-flash-lite
    echo         Provider: Gemini
    echo         Model: %MODEL%
) else (
    if not defined MODEL set MODEL=llama3.1
    echo         Provider: Ollama
    echo         Model: %MODEL%
)

:: --- Start server ---
echo [5/5] Starting backend server...
echo.
echo         URL: http://localhost:8000
echo.
echo         Endpoints:
echo           GET /new-session/demo_user
echo           GET /new-session/demo_user?memory=true
echo           GET /debug/memories/demo_user
echo           GET /debug/retrieve-memory/demo_user?q=...
echo.
echo         Press Ctrl+C to stop
echo.

:: Open browser only after backend is actually reachable
start /b powershell -WindowStyle Hidden -Command "for ($i=0; $i -lt 60; $i++) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200) { Start-Process 'http://localhost:8000'; exit 0 } } catch {} Start-Sleep -Seconds 1 }"

:: Start uvicorn
uvicorn app.main:app --reload

echo.
echo Server stopped.
pause
