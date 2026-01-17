import chromadb
from chromadb.utils import embedding_functions

# Uso 'all-MiniLM-L6-v2' 
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "pii_redaction_policies"

class PolicyVectorStore:
    """
    Gestisce il database vettoriale (ChromaDB) per l'archiviazione e il recupero
    delle policy di privacy per il sistema RAG.
    """

    def __init__(self):
        # Inizializzo il client ChromaDB in memoria 
        print(f"Inizializzazione Vector Store con modello: {EMBEDDING_MODEL_NAME}...")
        self.client = chromadb.Client()
        
        # Imposto la funzione di embedding che trasforma il testo in vettori numerici
        self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )

        # Creo la collezione o la recupero se già esiste
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_func
        )

        # Caricamento iniziale del corpus delle policy nel vector store
        self._seed_knowledge_base()

    def _seed_knowledge_base(self):
        """
        Carica il database con le regole hardcoded richieste.
        """
        
        # Definisco il testo della policy
        # NOTA: Le stringhe qui sotto DEVONO essere testo attivo, non commenti.
        policy_documents = [
            # POLICY GLOBALE (Fallback)
            "Se non viene trovata alcuna regola specifica per il cliente, applicare lo standard di sicurezza massimo: REDACT.",
            
            # POLICY CLIENTE: ACME
            "Le EMAIL devono essere convertite usando HASH per permettere analisi anonime.",
            "I numeri di PHONE devono essere parzialmente oscurati usando MASK_LAST_4 per verifica operatore.",
            "I NAME (nomi propri) sono considerati pubblici nel nostro caso, quindi KEEP.",
            
            # POLICY CLIENTE: BETA
            "Tutto deve essere REDACT, eccetto i PHONE che devono essere KEEP per esigenze di contatto urgenti."
        ]

        # Metadati associati per il filtering durante la ricerca
        metadatas = [
            {"customer": "GLOBAL", "scope": "DEFAULT", "source": "POL-GLOBAL"},
            {"customer": "ACME",   "scope": "EMAIL",   "source": "POL-ACME-V2"},
            {"customer": "ACME",   "scope": "PHONE",   "source": "POL-ACME-V2"},
            {"customer": "ACME",   "scope": "NAME",    "source": "POL-ACME-V2"},
            {"customer": "BETA",   "scope": "ALL",     "source": "POL-BETA-GEN"}
        ]

        # ID univoci per i record nel DB
        ids = ["glob_1", "acme_email", "acme_phone", "acme_name", "beta_all"]

        # Caricamento nel vector store
        self.collection.add(
            documents=policy_documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Knowledge Base caricata con {len(policy_documents)} regole.")

    def retrieve_policy(self, customer_id: str, entity_type: str):
        """
        Esegue la RAG, cercando la regola migliore da applicare.
        Prima cerca una regola SPECIFICA per quel Cliente e quel tipo di dato, se non trova nulla, cerca la regola GLOBALE (Fallback).
        """
        
        # Costruisco una query semantica semplice.
        search_query = f"Policy handling for {entity_type}"

        # Filtro esplicitamente per customer_id nei metadati per evitare che le regole di un cliente contaminino quelle di un altro.
        specific_results = self.collection.query(
            query_texts=[search_query],
            n_results=1,
            where={"customer": customer_id}
        )

        # Se ho trovato un match valido per questo cliente, lo restituisco.
        if specific_results["documents"] and specific_results["documents"][0]:
            return {
                "text": specific_results["documents"][0][0],
                "source": specific_results["metadatas"][0][0]["source"]
            }

        # Se arrivo a questo punto, il cliente non ha una regola specifica per questa entità.
        # Cerco le regole GLOBAL.
        global_results = self.collection.query(
            query_texts=[search_query],
            n_results=1,
            where={"customer": "GLOBAL"}
        )

        if global_results["documents"] and global_results["documents"][0]:
            return {
                "text": global_results["documents"][0][0],
                "source": global_results["metadatas"][0][0]["source"]
            }

        # caso in cui non c'è nessuna regola trovata nemmeno nel globale.
        return None