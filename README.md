# STATISFY RPG

> Un gioco di ruolo narrativo AI-driven basato sul sistema magico delle Dieci Sfere.

## 🏗️ Struttura

```
statisfy-rpg/
├── frontend/                    # Astro.js (UI)
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/           # Chat components
│   │   │   ├── dashboard/      # Selezione personaggi
│   │   │   ├── sheet/          # Scheda personaggio
│   │   │   ├── ui/             # Componenti riutilizzabili
│   │   │   └── Layout.astro
│   │   ├── lib/                # Logica condivisa
│   │   │   ├── gameState.js    # Stato personaggio
│   │   │   ├── tagParser.js    # Parser tag [TAG: value]
│   │   │   └── api.js          # Client API
│   │   ├── pages/
│   │   │   ├── index.astro     # Dashboard
│   │   │   └── game.astro      # Chat + Scheda
│   │   └── styles/
│   │       └── global.css
│   ├── package.json
│   └── astro.config.mjs
│
└── backend/                     # Flask (API)
    ├── app.py                   # Server + System Prompt
    ├── requirements.txt
    └── .env.example
```

## 🚀 Quick Start

### 1. Backend

```bash
cd backend

# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oppure: venv\Scripts\activate  # Windows

# Dipendenze
pip install -r requirements.txt

# Configurazione
cp .env.example .env
# Aggiungi ANTHROPIC_API_KEY nel .env

# Avvia
python app.py
```

Backend su **http://localhost:5000**

### 2. Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend su **http://localhost:3000**

## 🏷️ Sistema Tag

Il GM inserisce tag inline per gli eventi meccanici:

```
[DMG: 15 | target: enemy | source: sword]
[HEAL: 20 | target: self]
[CONDITION: poisoned | target: self | duration: 3_turns]
[ITEM: Pozione Rossa]
[SPHERE: ignis +2]
```

Il parser legge `target` per capire chi subisce l'effetto.

## 🎮 Flusso

```
Dashboard (index.astro)
    │
    ├── 6 slot personaggio
    ├── Click slot → va a /game?slot=N
    └── Dati in localStorage
    
Game (game.astro)
    │
    ├── Chat con Game Master (Claude)
    ├── Scheda personaggio (slide panel)
    └── Auto-save ogni 5 secondi
```

## 📜 License

MIT
