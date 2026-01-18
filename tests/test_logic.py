import unittest
from unittest.mock import MagicMock
import sys
import os


# Aggiunge la directory al system path per poter importare 'logic'.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic import RedactionEngine

class TestRedactionEngine(unittest.TestCase):
    """
    Utilizza i MOCK per isolare la logica di business dal database vettoriale.
    """

    def setUp(self):
        """
        Metodo di setup seguito automaticamente prima di ogni singolo test per creare un ambiente pulito e riproducibile.
        """
        # Crea un "Mock" (finto oggetto) che simula il Vector Store.
        # Non usiamo il vero ChromaDB qui, per rendere i test veloci e indipendenti dai dati.
        self.mock_vector_store = MagicMock()
        
        # Inizializza il motore (RedactionEngine) iniettando il finto database; il motore non sa che il DB è finto.
        self.engine = RedactionEngine(self.mock_vector_store)

    def test_hashing_strategy_acme(self):
        """
        Policy ACME per le Email --> verificare che se la policy contiene la parola 'HASH', il sistema applichi l'hashing.
        """
        
        # Istruisce il finto DB: quando viene chiamato il metodo retrieve_policy, 
        # restituisce questo dizionario specifico invece di cercare nel DB reale.
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": "Le EMAIL devono essere convertite usando HASH per analisi.",
            "source": "POL-TEST-ACME"
        }

        
        # Chiamo il metodo principale process_entity come farebbe l'API.
        result = self.engine.process_entity("ACME", "EMAIL", "mario@acme.com")

        # Controlliamo che la strategia scelta sia 'HASH'.
        self.assertEqual(result["applied_action"], "HASH")
        
        # Controlliamo che il valore sia stato trasformato (deve iniziare con il prefisso dell'hash).
        self.assertTrue(result["redacted_value"].startswith("[HASH:"))
        
        # Controlliamo che la giustificazione deve citare il testo della policy mockata.
        self.assertIn("Le EMAIL devono essere convertite", result["justification"])

    def test_masking_strategy_phone(self):
        """
        Policy generica per i numeri di telefono --> verificare che parole come 'oscurati' o 'MASK' attivino la strategia MASK_LAST_4.
        """
        # ARRANGE
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": "I numeri devono essere parzialmente oscurati.",
            "source": "POL-TEST-PHONE"
        }

        
        result = self.engine.process_entity("ACME", "PHONE", "333-123456")

        # Verifichiamo che l'azione sia corretta
        self.assertEqual(result["applied_action"], "MASK_LAST_4")
        # Verifichiamo il risultato esatto (ultime 4 cifre visibili)
        self.assertEqual(result["redacted_value"], "******3456")

    def test_exception_logic_beta(self):
        """
        Policy BETA con eccezione ("Tutto X, eccetto Y") --> verificare che il 'Semantic Layer' capisca la logica dell'eccezione.
        """
        policy_text = "Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP."
        
        # Istruiamo il mock a restituire sempre questa regola complessa
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": policy_text,
            "source": "POL-BETA-GEN"
        }

        # Test sull'eccezione (PHONE -> KEEP)
        result_phone = self.engine.process_entity("BETA", "PHONE", "333-55555")
        self.assertEqual(result_phone["applied_action"], "KEEP")
        self.assertEqual(result_phone["redacted_value"], "333-55555") # Il dato deve rimanere in chiaro

        # Test su un altro tipo (EMAIL) che NON è nell'eccezione (-> REDACT)
        # Anche se la policy è la stessa, il motore deve capire che 'EMAIL' non è 'PHONE'.
        result_email = self.engine.process_entity("BETA", "EMAIL", "test@beta.com")
        self.assertEqual(result_email["applied_action"], "REDACT")
        self.assertEqual(result_email["redacted_value"], "[REDACTED]")

    def test_fallback_when_no_policy_found(self):
        """
        Nessuna policy trovata (DB vuoto o cliente sconosciuto) --> verificare che il sistema vada in sicurezza applicando REDACT.
        """
        
        # Simuliamo il caso in cui il DB non trova nulla (nemmeno la Global Policy).
        self.mock_vector_store.retrieve_policy.return_value = None

        result = self.engine.process_entity("UNKNOWN_CLIENT", "EMAIL", "segreto@test.com")

        # Deve applicare la protezione massima
        self.assertEqual(result["applied_action"], "REDACT")
        # La fonte deve indicare che è un default di sistema
        self.assertEqual(result["policy_source"], "SYSTEM_DEFAULT")
        self.assertEqual(result["redacted_value"], "[REDACTED]")

if __name__ == '__main__':
    # Avvia l'esecuzione di tutti i test definiti nella classe
    unittest.main()