@echo off
REM Mega Quiz - Iniciar servidor
REM Direitos Reservados - ezetecf@gmail.com

cd /d "%~dp0"

echo ========================================
echo          MEGA QUIZ - v1.0
echo   Jogo de Perguntas e Respostas
echo ========================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado.
    echo Instale o Python em: https://python.org
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo [OK] Iniciando servidor...
echo.
echo Acesse: http://localhost:8080
echo Pressione Ctrl+C para parar
echo.

python mega_quiz.py
pause
