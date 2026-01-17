import hashlib
from typing import Dict, Callable

class RedactionEngine:
    """
    Gestisce la logica di offuscamento dei dati.
    Collega la regola testuale trovata nel database (es. 'Le email vanno hashate')  alla funzione Python che esegue la modifica.
    """

    def __init__(self, vector_store):
        self.kb = vector_store

        # Mappa le keyword delle policy alle funzioni Python reali.
        self._action_strategies: Dict[str, Callable[[str], str]] = {
            "REDACT": self._apply_redact,
            "HASH": self._apply_hash,
            "MASK_LAST_4": self._apply_mask_last_4,
            "KEEP": self._apply_keep
        }

    # Implementation Layer

    def _apply_redact(self, value: str) -> str:
        """Sostituzione totale standard."""
        return "[REDACTED]"

    def _apply_hash(self, value: str) -> str:
        """
        Hashing irreversibile (SHA-256). Tronca l'output per leggibilità nei log.
        """
        hashed = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"[HASH:{hashed[:8]}...]"

    def _apply_mask_last_4(self, value: str) -> str:
        """
        Mostra solo gli ultimi 4 caratteri.
        """
        if len(value) <= 4:
            return value
        return "*" * (len(value) - 4) + value[-4:]

    def _apply_keep(self, value: str) -> str:
        """Nessuna modifica"""
        return value

    # Semantic Layer

    def _derive_action_from_text(self, policy_text: str, entity_type: str) -> str:
        """
        Simula il componente 'Reasoning' di un LLM.
        Analizza il testo della policy recuperata per decidere quale funzione eseguire basandosi su keyworks e gestione delle eccezioni.
        """
        text_normalized = policy_text.upper()

        # Controlla Eccezioni: gestisce frasi complesse come "Tutto REDACT eccetto i PHONE..."
        # Se troviamo la parola 'ECCETTO' e il tipo di entità nella stessa frase, assumiamo che sia un'eccezione positiva (KEEP).
        if "ECCETTO" in text_normalized and entity_type in text_normalized:
            return "KEEP"

        # Mapping diretto delle Keyword
        # Ordine di priorità: HASH > MASK > KEEP > REDACT
        if "HASH" in text_normalized:
            return "HASH"
        
        if "MASK" in text_normalized or "OSCURATI" in text_normalized:
            return "MASK_LAST_4"
        
        if "KEEP" in text_normalized or "PUBBLICI" in text_normalized:
            return "KEEP"

        # Se la regola cita "REDACT" o se non capiamo l'istruzione, oscuriamo tutto.
        return "REDACT"

    # PUBLIC API 

    def process_entity(self, customer_id: str, entity_type: str, original_value: str) -> Dict:
        """
        1. Retrieval: Cerca la regola nel Vector Store.
        2. Reasoning: Interpreta il testo per scegliere l'azione.
        3. Execution: Applica l'azione al dato.
        """
        
        # Retrieval: uso del metodo search_rule che gestisce già il fallback GLOBAL
        rule_data = self.kb.retrieve_policy(customer_id, entity_type)

        if not rule_data:
            # se il DB è vuoto o irraggiungibile
            action_name = "REDACT"
            policy_source = "SYSTEM_DEFAULT"
            justification = "No policy found in Knowledge Base. Applying maximum safety."
        else:
            # Reasoning
            policy_text = rule_data["text"]
            policy_source = rule_data["source"]
            
            action_name = self._derive_action_from_text(policy_text, entity_type)
            justification = f"Matched snippet: '{policy_text}'"

        # Execution: recupero la funzione dalla mappa e la eseguo
        action_function = self._action_strategies.get(action_name, self._apply_redact)
        redacted_value = action_function(original_value)

        # Costruzione della risposta tracciabile 
        return {
            "entity_type": entity_type,
            "original_value": original_value,
            "redacted_value": redacted_value,
            "applied_action": action_name,
            "policy_source": policy_source,
            "justification": justification
        }