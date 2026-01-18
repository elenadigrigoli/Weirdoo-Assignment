# Policy-Aware PII Redaction Service (Dynamic Policy Guard)

**Dynamic Policy Guard** è un microservizio HTTP progettato per disaccoppiare la logica di business dalle regole di privacy (policy). Il sistema gestisce l'offuscamento di dati sensibili (PII) per clienti enterprise con requisiti conflittuali (es. una banca vuole hashare le email, un ospedale vuole oscurarle completamente).

Invece di utilizzare logiche condizionali hardcoded (es. `if customer == 'ACME'`), il servizio implementa un'architettura **RAG (Retrieval-Augmented Generation)** locale. Recupera dinamicamente le regole da un Vector Store e le interpreta per decidere come trattare ogni singola entità, garantendo flessibilità e tracciabilità totale.

---

## Funzionalità Chiave
* **Context-Aware Retrieval:** Recupera la policy corretta basandosi sulla combinazione di Cliente (`customer_id`) e Tipo di Entità (`entity_type`).
* **Gerarchia e Fallback:** Se non esiste una regola specifica per il cliente, il sistema applica automaticamente una policy globale di sicurezza ("Safety First: REDACT").
* **Tracciabilità (Audit Trail):** Ogni risposta include non solo il testo oscurato, ma anche la giustificazione tecnica (`justification`) e la fonte della policy applicata.
* **Esecuzione Locale:** Funziona interamente offline utilizzando `ChromaDB` e `SentenceTransformers`.
* **Ricostruzione Precisa:** Utilizza il *Reverse Index Slicing* per modificare il testo originale senza corrompere gli indici delle entità, garantendo precisione anche con parole ripetute.

---

## Architettura e Scelte Progettuali

### 1. Strategia RAG (Retrieval)
Per gestire i conflitti tra regole specifiche e standard globali, ho implementato un meccanismo di **Priority Retrieval** a due livelli:
1.  **Level 1 (Specifico):** Cerca nel Vector Store filtrando esattamente per `customer_id`.
2.  **Level 2 (Fallback):** Se non trova risultati pertinenti, esegue una query per `customer="GLOBAL"`.

**Stack Tecnologico:**
* **ChromaDB:** Utilizzato in modalità in-memory per semplicità di deployment e velocità.
* **Modello `all-MiniLM-L6-v2`:** veloce per inferenza su CPU e capace di comprendere semanticamente query come "Policy for PHONE".

### 2. Logic Engine (Reasoning)
Poiché il requisito vietava l'uso di LLM generativi pesanti, il `RedactionEngine` utilizza un approccio euristico basato su **Keyword Spotting** e **Strategy Pattern**:
* Analizza il testo della policy (es. *"Tutto REDACT eccetto i PHONE..."*).
* Mappa le intenzioni semantiche a funzioni Python concrete (`_apply_hash`, `_apply_mask`, ecc.).

### 3. Text Reconstruction (Safe Slicing)
Per evitare errori comuni con `str.replace()` (che rischia di sostituire omonimie non desiderate), il sistema ricostruisce il testo usando le coordinate `start` ed `end` fornite in input.
Le sostituzioni vengono applicate in ordine **decrescente** (dalla fine della stringa all'inizio) per mantenere validi gli indici delle entità precedenti durante la manipolazione.

---

## Installazione e Avvio

### Prerequisiti
* Python 3.10 o superiore
* pip

### 1. Setup dell'ambiente
Uso virtual environment per isolare le dipendenze.

```bash
# Crea il virtual environment
python -m venv venv

# Attiva su Windows
.\venv\Scripts\activate

# Installa le librerie necessarie
pip install -r requirements.txt
```

### 2. Avvio del Server
L'applicazione utilizza FastAPI servita da Uvicorn.

```bash

uvicorn main:app --reload
```
Il server sarà accessibile su: http://127.0.0.1:8000

La documentazione Swagger è disponibile su: http://127.0.0.1:8000/docs

All'avvio, il sistema caricherà automaticamente le policy dimostrative nel database.

### 3. Esempi di Test e Risultati
Scenario 1: Cliente "ACME" (Policy Custom)
Regola: Email -> HASH, Telefono -> MASK, Nome -> KEEP. Output: Nome in chiaro, Email hashata, Telefono mascherato.

#### Request (Input)
```json
{ "customer_id": "ACME",
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
      "original_value": "Mario Rossi",
      "redacted_value": "Mario Rossi",
      "applied_action": "KEEP",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'I NAME (nomi propri) sono considerati pubblici nel nostro caso, quindi KEEP.'"
    },
    {
      "entity_type": "EMAIL",
      "original_value": "mario@acme.com",
      "redacted_value": "[HASH:91b629c2...]",
      "applied_action": "HASH",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'Le EMAIL devono essere convertite usando HASH per permettere analisi anonime.'"
    },
    {
      "entity_type": "PHONE",
      "original_value": "333-123456",
      "redacted_value": "******3456",
      "applied_action": "MASK_LAST_4",
      "policy_source": "POL-ACME-V2",
      "justification": "Matched snippet: 'I numeri di PHONE devono essere parzialmente oscurati usando MASK_LAST_4 per verifica operatore.'"
    }
  ]
}
```

Scenario 2: Cliente "BETA" (Policy Eccezioni)
Regola: "Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP". Output: Nome e Email oscurati, Telefono in chiaro.
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
      "original_value": "Mario Rossi",
      "redacted_value": "[REDACTED]",
      "applied_action": "REDACT",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    },
    {
      "entity_type": "EMAIL",
      "original_value": "mario@beta.com",
      "redacted_value": "[REDACTED]",
      "applied_action": "REDACT",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    },
    {
      "entity_type": "PHONE",
      "original_value": "333-123456",
      "redacted_value": "333-123456",
      "applied_action": "KEEP",
      "policy_source": "POL-BETA-GEN",
      "justification": "Matched snippet: 'Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti.'"
    }
  ]
}
```
Scenario 3: Cliente Sconosciuto (Fallback Globale)
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
      "original_value": "Luigi Bianchi",
      "redacted_value": "[REDACTED]",
      "applied_action": "REDACT",
      "policy_source": "POL-GLOBAL",
      "justification": "Matched snippet: 'Se non viene trovata alcuna regola specifica per il cliente, applicare lo standard di sicurezza massimo: REDACT.'"
    },
    {
      "entity_type": "EMAIL",
      "original_value": "ceo@pippo.com",
      "redacted_value": "[REDACTED]",
      "applied_action": "REDACT",
      "policy_source": "POL-GLOBAL",
      "justification": "Matched snippet: 'Se non viene trovata alcuna regola specifica per il cliente, applicare lo standard di sicurezza massimo: REDACT.'"
    }
  ]
}
```
### Struttura del Progetto
main.py: Entry point dell'API FastAPI.

logic.py: Logica di business e Strategy Pattern.

database.py: Gestione ChromaDB e Retrieval RAG.

requirements.txt: Dipendenze Python. adesso mi riscrivi tutto il read me che attualmente è cosi come ti ho incollato aggiungendo tutta questa altra cosa che abbiamo fatto piu le limitazioni
