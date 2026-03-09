#!/bin/bash
# STATISFY RPG - Quick Start
# Avvia backend Flask + frontend Astro in parallelo

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
  echo -e "\n${RED}Shutting down...${NC}"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

# --- Backend ---
echo -e "${GREEN}[1/2] Starting backend...${NC}"

if [ ! -d "$BACKEND/venv" ]; then
  echo "Creating venv..."
  python -m venv "$BACKEND/venv"
  "$BACKEND/venv/Scripts/pip" install -r "$BACKEND/requirements.txt"
fi

if [ ! -f "$BACKEND/.env" ]; then
  echo -e "${RED}.env mancante! Copia backend/.env.example in backend/.env e aggiungi la tua API key.${NC}"
  exit 1
fi

"$BACKEND/venv/Scripts/python" "$BACKEND/app.py" &
BACKEND_PID=$!

# --- Frontend ---
echo -e "${GREEN}[2/2] Starting frontend...${NC}"

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install --prefix "$FRONTEND"
fi

npm run dev --prefix "$FRONTEND" &
FRONTEND_PID=$!

echo -e "\n${GREEN}=== STATISFY RPG ===${NC}"
echo -e "Backend:  http://localhost:5000"
echo -e "Frontend: http://localhost:3000"
echo -e "Press Ctrl+C to stop\n"

wait
