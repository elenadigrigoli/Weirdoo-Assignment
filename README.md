# Policy-Aware PII Redaction Service (Dynamic Policy Guard)

## 1. **Dynamic Policy Guard** 
E' un microservizio HTTP progettato per disaccoppiare la logica di business dalle regole di privacy (policy). Il sistema gestisce l'offuscamento di dati sensibili (PII) per vari clienti, ad esempio una banca vuole hashare le email o un ospedale che vuole oscurarle completamente.

Invece di utilizzare logiche condizionali hardcoded (es. `if customer == 'ACME'`), il servizio implementa un'architettura **RAG (Retrieval-Augmented Generation)** locale che recupera le regole da un Vector Store e le interpreta per decidere come trattare ogni singola entità, garantendo flessibilità e tracciabilità totale.

### 1.1 ChromaDB & Sentence Transformers
Per soddisfare il requisito di esecuzione locale senza dipendenze da API esterne (OpenAI/Anthropic), ho implementato uno stack RAG :

* **Vector Store: ChromaDB**
  * ChromaDB in modalità *in-memory/local*; non richiede container Docker pesanti per girare; permette di avere un DB vettoriale performante installando una semplice libreria Python.
* **Embedding Model: `all-MiniLM-L6-v2`**
  * `MiniLM-L6` è estremamente veloce su CPU, occupa poca RAM e offre una buona accuratezza semantica.

### 1.2 Strategy Pattern per l'Esecuzione
Nel file `logic.py`, ho usato il **Design Pattern Strategy**.
* Ho creato una mappa (`Dict[str, Callable]`) che collega le keyword delle policy (es. `"HASH"`, `"MASK_LAST_4"`) direttamente alle funzioni Python.

### 1.3 Algoritmo di Ricostruzione del Testo
Per applicare le modifiche al testo originale, il sistema utilizza una ricostruzione posizionale basata sugli indici delle entità, applicando le sostituzioni in ordine inverso per preservare la validità delle coordinate.

### 1.4 Semantic Layer & Determinismo
Il sistema non si affida all'AI generativa, ma utilizza un layer semantico deterministico:
* Il `Retrieval` individua la regola più pertinente ed il codice analizza il testo della policy per prendere decisioni logiche sicure e riproducibili.

---

## 2. Guida all'Installazione e Avvio

### 2.1 Prerequisiti
* Python 3.10 o superiore
* Pip (Python Package Installer)

### 2.2 Setup Ambiente
1. Estraggo la mia cartella di lavoro.
2. Creo un Virtual Environment:
```bash
python -m venv venv
.\venv\Scripts\activate
```


### 2.3 Installo le dipendenze:
```bash
pip install -r requirements.txt
```
Questo installerà FastAPI, Uvicorn, ChromaDB e Sentence-Transformers.

### 2.4 Avvio del Servizio
Eseguo il comando:
```bash
uvicorn main:app --reload
```
Il server sarà accessibile su: http://127.0.0.1:8000

---

## 3. Struttura del Progetto

Il codice è organizzato in moduli distinti:

* **`main.py`** (API Layer)
    * È l'entry point dell'applicazione (FastAPI).
    * Gestisce le richieste HTTP (`POST /redact`, `POST /policy/explain`).
    * Definisce i modelli di validazione dati (Pydantic) per input e output.

* **`database.py`** (Data Layer)
    * Gestisce la connessione con il Vector Store (**ChromaDB**).
    * Si occupa di creare gli embedding (tramite `sentence-transformers`) e di caricare le policy in memoria all'avvio.
    * Esegue le query di ricerca semantica (Retrieval) per trovare la regola più adatta.

* **`logic.py`** (Business Logic Layer)
    * Contiene la classe `RedactionEngine`.
    * Implementa lo **Strategy Pattern**: mappa le regole testuali (es. "HASH") alle funzioni Python concrete.
    * Esegue il *Reasoning* (es. gestione delle eccezioni "ECCETTO") e applica le trasformazioni ai dati.

* **`tests/`**
    * Contiene la parte riguardante test unitari che verificano il funzionamento del `RedactionEngine` in isolamento, usando `unittest.mock` per simulare il database.
---
## 4. Funzionalità Chiave
* **Context-Aware Retrieval:** Recupera la policy corretta basandosi sulla combinazione di Cliente (`customer_id`) e Tipo di Entità (`entity_type`).
* **Gerarchia e Fallback:** Se non esiste una regola specifica per il cliente, il sistema applica automaticamente una policy globale di sicurezza ("Safety First: REDACT").
* **Tracciabilità:** Ogni risposta include non solo il testo oscurato, ma anche la giustificazione tecnica (`justification`) e la fonte della policy applicata.
* **Esecuzione Locale:** Funziona interamente offline utilizzando `ChromaDB` e `SentenceTransformers`.
* **Ricostruzione Precisa**: Utilizza il Reverse Index Slicing per modificare il testo originale senza corrompere gli indici delle entità.
---

## 5. Dettagli Implementativi e Algoritmi

### 5.1 Logica di Retrieval Gerarchico 
Il sistema non cerca solo la regola più simile, ma gestisce i conflitti tra clienti diversi implementando un meccanismo di ricerca a due livelli:
1.  **Level 1 (Specifico):** Esegue una query sul Vector Store filtrando strettamente per `customer_id`.
2.  **Level 2 (Fallback):** Se la ricerca specifica non produce risultati (o score troppo bassi), il sistema esegue una seconda query filtrando per `customer="GLOBAL"`.
Questo garantisce che le regole custom abbiano sempre la precedenza, ma che esista sempre una rete di sicurezza.

### 5.2 Motore di Reasoning Deterministico
Il `RedactionEngine` adotta un approccio deterministico:
Il testo recuperato viene normalizzato e scansionato per keyword logiche (es. la clausola `"ECCETTO"` per gestire regole condizionali complesse come quella del cliente BETA). La regola testuale viene poi tradotta in una funzione Python concreta tramite una mappa di strategie, garantendo che l'output sia sempre prevedibile.

### 5.3 Algoritmo di Ricostruzione 
Invece di usare metodi rischiosi come `str.replace()` (che potrebbe oscurare omonimie non desiderate nel testo), il sistema opera matematicamente sugli indici:
1.  Le entità vengono ordinate per posizione di partenza (`start_index`) in ordine **decrescente**.
2.  Procede alla sostituzione partendo dal fondo della stringa verso l'inizio --> modificare la stringa all'inizio farebbe slittare tutti i caratteri successivi, invalidando gli indici delle altre entità. L'approccio inverso garantisce che ogni coordinata rimanga valida fino al momento del suo utilizzo.

### 5.4 Testing 
Il progetto include una sezione di test basata su `unittest.mock`. I test simulano il Vector Store, permettendo di verificare la logica di business in isolamento.

Per eseguire i test: 
```bash
python -m unittest discover tests
```
Output: Ran 4 tests in 0.003s OK

L'output conferma non solo la correttezza della logica, ma anche l'efficacia del disaccoppiamento architetturale. Grazie all'uso dei Mock, i test non devono collegarsi a un vero database, rendendoli istantanei (0.003s). Possiamo quindi lanciare i test continuamente senza dover aspettare, garantendo che il software sia sempre funzionante.

---
## 6. Esempi di Test e Risultati

### 6.1 Scenario 1: Cliente "ACME" (Policy Custom)
Regola: Email -> HASH, Telefono -> MASK, Nome -> KEEP. Output: Nome in chiaro, Email hashata, Telefono mascherato.

#### Request (Input)
```json
{
  "customer_id": "ACME",
  "policy_version": "v2",
  "content": {
       "text": "L'utente Mario Rossi (mario@acme.com) ha chiamato il 333-123456.",
       "entities": [
         { "type": "NAME", "value": "Mario Rossi", "start": 9, "end": 20 },
         { "type": "EMAIL", "value": "mario@acme.com", "start": 22, "end": 36 },
         { "type": "PHONE", "value": "333-123456", "start": 53, "end": 63 }
    ]
  }
}
```
#### Output - Response Body
```json
{
  "original_text_length": 64,
  "redacted_text": "L'utente Mario Rossi ([HASH:91b629c2...]) ha chiamato il ******3456.",
  "actions": [
    {
      "entity_type": "NAME",
      "applied_action": "KEEP",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'I NAME (nomi propri) sono considerati pubblici nel nostro caso, quindi KEEP.'"
    },
    {
      "entity_type": "EMAIL",
      "applied_action": "HASH",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'Le EMAIL devono essere convertite usando HASH per permettere analisi anonime.'"
    },
    {
      "entity_type": "PHONE",
      "applied_action": "MASK_LAST_4",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'I numeri di PHONE devono essere parzialmente oscurati usando MASK_LAST_4 per verifica operatore.'"
    }
  ]
}
```

### 6.2 Scenario 2: Cliente "BETA" (Policy Eccezioni)
Regola: Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP. Output: Nome e Email oscurati, Telefono in chiaro.
#### Request (Input)
```json
{
 "customer_id": "BETA",
 "policy_version": "gen",
 "content": {
    "text": "L'utente Mario Rossi (mario@beta.com) ha chiamato il 333-123456.",
    "entities": [
       { "type": "NAME", "value": "Mario Rossi", "start": 9, "end": 20 },
       { "type": "EMAIL", "value": "mario@beta.com", "start": 22, "end": 36 },
       { "type": "PHONE", "value": "333-123456", "start": 53, "end": 63 }
    ]
  }
}
```
#### Output - Response Body
``` json
{
  "original_text_length": 64,
  "redacted_text": "L'utente [REDACTED] ([REDACTED]) ha chiamato il 333-123456.",
  "actions": [
    {
      "entity_type": "NAME",
      "applied_action": "REDACT",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    },
    {
      "entity_type": "EMAIL",
      "applied_action": "REDACT",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    },
    {
      "entity_type": "PHONE",
      "applied_action": "KEEP",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    }
  ]
}
```
### 6.3 Scenario 3: Cliente Sconosciuto (Fallback Globale)
Regola: Nessuna regola specifica trovata -> Applica standard massimo. Output: Tutto oscurato ([REDACTED]) perché scatta la policy POL-GLOBAL.
#### Request (Input)
```json
{
  "customer_id": "PIPPO_CORP",
  "content": {
     "text": "Il CEO Luigi Bianchi (ceo@pippo.com) è qui.",
     "entities": [
       { "type": "NAME", "value": "Luigi Bianchi", "start": 7, "end": 20 },
       { "type": "EMAIL", "value": "ceo@pippo.com", "start": 22, "end": 35 }
    ]
  }
}
```
#### Output - Response Body
``` json
{
  "original_text_length": 43,
  "redacted_text": "Il CEO [REDACTED] ([REDACTED]) è qui.",
  "actions": [
    {
      "entity_type": "NAME",
      "applied_action": "REDACT",
      "policy_source": "POL-GLOBAL",
      "justification": "Matched snippet: 'Se non viene trovata alcuna regola specifica per il cliente, applicare lo standard di sicurezza massimo: REDACT.'"
    },
    {
      "entity_type": "EMAIL",
      "applied_action": "REDACT",
      "policy_source": "POL-GLOBAL",
      "justification": "Matched snippet: 'Se non viene trovata alcuna regola specifica per il cliente, applicare lo standard di sicurezza massimo: REDACT.'"
    }
  ]
}
```
### 6.4 Scenario 4: Endpoint Bonus 
Obiettivo: Debugging/Audit. Capire cosa farebbe il sistema senza eseguire la modifica.

```json
{
  "customer_id": "BETA",
  "entity_type": "EMAIL"
}
```
#### Output - Response Body
``` json
{
  "action": "REDACT",
  "source": "POL-BETA-GEN",
  "snippet": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
}
```
---

## 7. Limitazioni Note e Sviluppi Futuri

Visto che questo è un esercizio tecnico, ho fatto alcune semplificazioni consapevoli per mantenere il progetto leggero:

### 7.1  **Le entità devono arrivare già pronte**
Il sistema non legge il testo per cercare autonomamente "Mario Rossi" . Si aspetta che qualcun altro lo abbia già fatto e gli passi gli indici esatti (`start` e `end`); se gli passi indici sbagliati, l'offuscamento potrebbe "rompere" le parole.

### 7.2  **Il database "dimentica" tutto al riavvio**
Per evitare configurazioni complesse, il database vettoriale viene creato nella memoria RAM ogni volta che lanci il programma. In uno scenario diverso, lo salverei su disco per non dover ricaricare le regole ogni volta che si riavvia il server.

### 7.3 **Scalabilità**
Attualmente il servizio è pensato per girare in locale e gestisce le richieste in modo semplice. Se dovessimo gestire il traffico reale di una azienda con migliaia di utenti, bisognerebbe configurare un server più potente per parallelizzare il lavoro.

