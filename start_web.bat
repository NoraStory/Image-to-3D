@echo off
REM Windows batch script to start the web server

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Load environment variables from .env
if exist .env (
    for /f "tokens=*" %%a in (.env) do (
        set %%a
    )
)

REM Start web server
echo Starting Image to 3D Web Server...
echo Visit http://127.0.0.1:5000 in your browser
echo.
python -m imageto3d.web
