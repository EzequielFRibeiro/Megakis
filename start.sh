#!/bin/bash
# Mega Quiz - Iniciar servidor
# Direitos Reservados - ezetecf@gmail.com

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "========================================"
echo "         MEGA QUIZ - v1.0"
echo "  Jogo de Perguntas e Respostas"
echo "========================================"
echo ""

if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON="python"
    else
        echo "[ERRO] Python nao encontrado. Instale o Python 3."
        exit 1
    fi
else
    PYTHON="python3"
fi

echo "[OK] Python: $($PYTHON --version)"
echo "[OK] Iniciando servidor..."
echo ""
echo "Acesse: http://localhost:8080"
echo "Pressione Ctrl+C para parar"
echo ""

$PYTHON mega_quiz.py
