from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

# Import dei moduli locali 
from database import PolicyVectorStore
from logic import RedactionEngine

# Inizializzazione di FastAPI
app = FastAPI(
    title="Policy-Aware PII Redaction Service",
    description="Microservizio per l'offuscamento dinamico di dati sensibili basato su policy RAG.",
    version="1.0.0"
)

# AVVIO DEL SISTEMA
# Carico il database e il motore di redazione appena l'app parte.
print("Avvio del sistema in corso...")

# Inizializzazione senza try/except per vedere subito eventuali errori
vector_store = PolicyVectorStore()
redaction_engine = RedactionEngine(vector_store)

print("Sistema pronto. Database caricato correttamente.")

    
# Definisce i modelli di input/output per validazione automatica
class EntityItem(BaseModel):
    type: str = Field(..., description="Tipo di entità (es. EMAIL, PHONE, NAME)")
    value: str = Field(..., description="Il testo esatto dell'entità")
    start: int = Field(..., description="Indice di inizio nel testo originale")
    end: int = Field(..., description="Indice di fine nel testo originale")

class ContentData(BaseModel):
    text: str = Field(..., description="Il testo completo da analizzare")
    entities: List[EntityItem] = Field(..., description="Lista delle entità PII identificate")

class RedactRequest(BaseModel):
    customer_id: str = Field(..., description="Identificativo del cliente (es. ACME)")
    policy_version: Optional[str] = Field(None, description="Versione specifica della policy (opzionale)")
    content: ContentData

class RedactResponse(BaseModel):
    original_text_length: int
    redacted_text: str
    actions: List[dict]

# API ENDPOINTS 
@app.post("/redact", response_model=RedactResponse)
def redact_text(request: RedactRequest):
    """
    Endpoint principale: riceve testo ed entità, interroga le policy
    e restituisce il testo oscurato con le giustificazioni.
    """
    
    original_text = request.content.text
    planned_actions = []

    # FASE DI ANALISI (Decision Making)
    # Itera su ogni entità per decidere cosa farne.
    # Non modifica ancora il testo.
    for entity in request.content.entities:
        decision = redaction_engine.process_entity(
            customer_id=request.customer_id,
            entity_type=entity.type,
            original_value=entity.value
        )
        planned_actions.append(decision)

    # FASE DI APPLICAZIONE (Text Reconstruction)
    # Sostituisce le parti del testo originale con i valori redatti.
    
    # Lista di tuple (entità_originale, decisione_presa)
    replacements = list(zip(request.content.entities, planned_actions))

    # Ordino le sostituzioni in ordine DECRESCENTE di posizione (start index).
    # Se sostituisse dall'inizio, la lunghezza della stringa cambierebbe, 
    # invalidando gli indici delle entità successive. Partendo dalla fine, gli indici precedenti rimangono validi.
    replacements.sort(key=lambda x: x[0].start, reverse=True)

    final_text = original_text

    for entity, action_result in replacements:
        start_idx = entity.start
        end_idx = entity.end
        new_value = action_result["redacted_value"]

        # Slicing : [Testo Prima] + [Nuovo Valore] + [Testo Dopo]
        final_text = final_text[:start_idx] + new_value + final_text[end_idx:]

    # Costruzione della risposta finale
    return {
        "original_text_length": len(original_text),
        "redacted_text": final_text,
        "actions": planned_actions
    }

@app.get("/health", tags=["Monitoring"])
def healthcheck():
    """
    Endpoint per Liveness Probe (Kubernetes/Docker health check).
    """
    return {
        "status": "online",
        "service": "Dynamic Policy Guard",
        "version": "1.0.0"
    }
    
# --- SEZIONE BONUS ---

# L'obiettivo è permettere agli auditor di capire le regole senza dover processare dati reali.

class ExplainRequest(BaseModel):
    """
    Modello di input per la richiesta di spiegazione.
    Richiede solo il contesto (chi è il cliente?) e il tipo di dato.
    """
    customer_id: str = Field(..., description="ID del cliente (es. BETA)")
    entity_type: str = Field(..., description="Tipo di entità da verificare (es. EMAIL, PHONE)")

class ExplainResponse(BaseModel):
    """
    Modello di output standardizzato.
    Restituisce l'azione decisa, la fonte della policy e lo snippet di testo pertinente.
    """
    action: str
    source: str
    snippet: str
    
@app.post("/policy/explain", response_model=ExplainResponse, tags=["Debug"])
def explain_policy_decision(request: ExplainRequest):
    """
    Spiega quale regola verrebbe applicata per un dato cliente e tipo di entità, senza eseguire la redazione effettiva.
    (Utile per verificare la correttezza delle policy caricate nel Vector Store).
    """
    
    # Invece di duplicare la logica di retrieval e reasoning, utilizziamo 
    # lo stesso metodo 'process_entity' usato per la redazione vera e propria.
    
    # Il metodo process_entity richiede obbligatoriamente un 'original_value' per poter restituire il valore redatto. 
    # # Qui passo un valore fittizio ("X") poiché a fini di debug ci interessa solo la decisione, non la trasformazione del valore.
    decision = redaction_engine.process_entity(
        customer_id=request.customer_id,
        entity_type=request.entity_type,
        original_value="X"  # Dummy value
    )

    # Convertiamo il dizionario interno restituito dal motore nel modello Pydantic di risposta.
    return {
        "action": decision["applied_action"],
        "source": decision["policy_source"],
        "snippet": decision["justification"]
    }