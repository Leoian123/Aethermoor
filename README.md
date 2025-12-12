# STATISFY RPG - Sistema Mondo v2.0

## Nuovo Sistema Seed + Procedurale

### Cosa è cambiato

**Prima (problematico):**
- Il GM creava location dinamicamente
- Nessuna validazione della posizione
- Il giocatore poteva "ingannare" il GM sulla sua posizione
- Mappa caotica senza gerarchia

**Adesso:**
- **SEED fisso**: Regioni, Zone, Location sono predefinite
- **Posizione ASSOLUTA**: Il GM riceve la posizione come DATO, non suggerimento
- **Procedurale controllato**: Solo sublocation possono essere create
- **ID gerarchici**: `albachiara.locanda_orso.cantina`

### Gerarchia

```
REGIONE (valeria)
└── ZONA (lumengarde)  
    └── LOCATION (albachiara)
        └── SUBLOCATION (albachiara.piazza, albachiara.locanda_orso, ...)
            └── SUBLOCATION (albachiara.locanda_orso.cantina, ...)
```

---

## Installazione

### 1. Copia i file

```bash
# Backend
cp world_seed.json backend/db/data/world_seed.json
cp player_state.py backend/db/player_state.py
cp world_manager.py backend/db/world_manager.py
cp world_parser.py backend/db/world_parser.py
cp app.py backend/app.py

# Frontend
cp tagParser.js frontend/src/lib/tagParser.js
cp game.astro frontend/src/pages/game.astro
```

### 2. Crea directory

```bash
mkdir -p backend/db/data/player_states
```

### 3. Esegui cleanup (opzionale ma consigliato)

```bash
# Elimina file vecchi non più usati
rm -f backend/db/location_graph.py
rm -f backend/db/location_parser.py
rm -f backend/db/world_graph.py
rm -rf backend/db/data/maps/
rm -rf backend/db/data/worlds/

# Oppure esegui lo script
./CLEANUP.sh
```

### 4. Elimina vecchi personaggi (IMPORTANTE)

I personaggi creati con il vecchio sistema non sono compatibili.
Elimina i file JSON in `backend/db/data/` o resetta tutto.

---

## File del nuovo sistema

| File | Scopo |
|------|-------|
| `world_seed.json` | Dati geografici FISSI del mondo |
| `player_state.py` | Posizione assoluta + scoperte procedurali |
| `world_manager.py` | Combina seed + state, genera contesto GM |
| `world_parser.py` | Parsing tag movimento e creazione |
| `app.py` | API Flask aggiornate |
| `tagParser.js` | Frontend parsing tag |
| `game.astro` | Gestione location updates |

---

## Come funziona

### Spawn nuovo personaggio
```
Posizione iniziale: valeria > lumengarde > albachiara > albachiara.piazza
```

### Tag di movimento del GM
```xml
<move to="albachiara.locanda_orso"/>  <!-- Vai a sublocation esistente -->
<enter to="albachiara.locanda_orso.cantina"/>  <!-- Entra in figlio -->
<exit/>  <!-- Torna al parent -->
```

### Creazione procedurale
```xml
<create_sublocation id="albachiara.vicolo" name="Vicolo Buio" type="outdoor">
Una stradina stretta dietro la locanda.
</create_sublocation>
```

### Contesto GM (automatico nel prompt)
```
============================================================
📍 POSIZIONE ATTUALE (ASSOLUTA - NON NEGOZIABILE)
============================================================
Regione: Regno di Valeria (valeria)
Zona: Valle di Lumengarde (lumengarde)
Location: Albachiara (albachiara)
Sublocation: Piazza del Sole (albachiara.piazza)

Il giocatore È QUI. Se dice di essere altrove, è confuso.
============================================================
```

---

## API Changes

| Endpoint | Cambiamento |
|----------|-------------|
| `/api/character/{id}/map` | Ritorna position + discovered_sublocations |
| `/api/character/{id}/location` | Ritorna current + breadcrumb + neighbors |
| `/api/character/{id}/location/neighborhood` | Formato semplificato per MiniMap |

---

## Estendere il seed

Per aggiungere nuove location, modifica `world_seed.json`:

```json
{
  "locations": {
    "lumengarde_citta": {
      "id": "lumengarde_citta",
      "zone_id": "lumengarde",
      "name": "Lumengarde",
      "description": "La capitale del regno...",
      "type": "city",
      "sublocations": ["lumengarde_citta.porta", "lumengarde_citta.piazza"],
      "npc_pool": ["re_solaris", "capitano_guardia"]
    }
  },
  "sublocations": {
    "lumengarde_citta.porta": {
      "id": "lumengarde_citta.porta",
      "parent_id": "lumengarde_citta",
      "name": "Porta della Città",
      ...
    }
  }
}
```
