import unittest
from unittest.mock import MagicMock
import sys
import os

# Aggiunge la directory genitore al path per poter importare i moduli (logic, database)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic import RedactionEngine

class TestRedactionEngine(unittest.TestCase):

    def setUp(self):
        """
        Questo metodo viene eseguito PRIMA di ogni singolo test.
        Serve a preparare l'ambiente pulito.
        """
        # Creiamo un "Mock" del Vector Store.
        self.mock_vector_store = MagicMock()
        
        # Inizializziamo il motore iniettando il finto database.
        self.engine = RedactionEngine(self.mock_vector_store)

    def test_hashing_strategy_acme(self):
        """
        Testa se il sistema applica HASH quando la regola testuale contiene 'HASH'.
        """
        # istruire il mock: "Quando ti viene chiesta una policy, rispondi così:"
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": "Le EMAIL devono essere convertite usando HASH per analisi.",
            "source": "POL-TEST-ACME"
        }

        # ESECUZIONE
        result = self.engine.process_entity("ACME", "EMAIL", "mario@acme.com")

        # VERIFICA : che abbia scelto l'azione giusta
        self.assertEqual(result["applied_action"], "HASH")
        # Verifichiamo che il valore sia effettivamente cambiato (inizi con [HASH:)
        self.assertTrue(result["redacted_value"].startswith("[HASH:"))
        # Verifichiamo che la giustificazione citi il testo che abbiamo inventato
        self.assertIn("Le EMAIL devono essere convertite", result["justification"])

    def test_masking_strategy_phone(self):
        """
        Testa se il sistema applica MASK_LAST_4 quando la regola dice 'oscurati'.
        """
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": "I numeri devono essere parzialmente oscurati.",
            "source": "POL-TEST-PHONE"
        }

        result = self.engine.process_entity("ACME", "PHONE", "333-123456")

        self.assertEqual(result["applied_action"], "MASK_LAST_4")
        self.assertEqual(result["redacted_value"], "******3456")

    def test_exception_logic_beta(self):
        """
        Testa la logica 'ECCETTO': Tutto REDACT tranne PHONE che è KEEP.
        """
        policy_text = "Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP."
        
        self.mock_vector_store.retrieve_policy.return_value = {
            "text": policy_text,
            "source": "POL-BETA-GEN"
        }

        # Test di un PHONE (Dovrebbe essere KEEP)
        result_phone = self.engine.process_entity("BETA", "PHONE", "333-55555")
        self.assertEqual(result_phone["applied_action"], "KEEP")
        self.assertEqual(result_phone["redacted_value"], "333-55555")

        # Test di una EMAIL (Non è nell'eccezione -> Fallback a REDACT)
        
        result_email = self.engine.process_entity("BETA", "EMAIL", "test@beta.com")
        self.assertEqual(result_email["applied_action"], "REDACT")
        self.assertEqual(result_email["redacted_value"], "[REDACTED]")

    def test_fallback_when_no_policy_found(self):
        """
        Testa cosa succede se il Database non trova nessuna regola (return None).
        Deve applicare il massimo standard di sicurezza (REDACT).
        """
        # Il DB restituisce None
        self.mock_vector_store.retrieve_policy.return_value = None

        result = self.engine.process_entity("UNKNOWN_CLIENT", "EMAIL", "segreto@test.com")

        self.assertEqual(result["applied_action"], "REDACT")
        self.assertEqual(result["policy_source"], "SYSTEM_DEFAULT")
        self.assertEqual(result["redacted_value"], "[REDACTED]")

if __name__ == '__main__':
    unittest.main()