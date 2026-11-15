"""What the fields of the sheets mean and how to fill them in (Field.guide, rich text): shown next to the field (the
«?» on its left) and in the window to choose its value."""

# --- SA-5: functional exchange ----------------------------------------------------------------------------------

FE_ID = (
    "Assegnato da ATLAS quando produttore e utilizzatore sono indicati: <b>FE-DFaa-DFbb-nn</b>, con il dominio del "
    "produttore, quello dell'utilizzatore e un progressivo (es. FE-DF02-DF06-01). Al posto del dominio di un attore "
    "esterno c'è il suo ID.<br>Non cambia da solo: se cambiano gli estremi, «Rinumera» lo riallinea (SA5-09).")
FE_NAME = (
    "Richiama l'<b>informazione trasportata</b>, non l'azione (B4): di solito è il nome dell'Exchange Item, es. "
    "«Movimento del treno».")
FE_SOURCE = (
    "La funzione (di sistema o logica) o l'attore esterno che <b>produce</b> il dato.<br>Ogni dato ha una sola "
    "funzione produttrice (D10): se l'Exchange Item ha già un produttore, lo scambio parte da lì. Produttore e "
    "utilizzatore sono diversi, dello stesso livello (SF con SF, LF con LF) e non entrambi attori esterni.")
FE_TARGET = (
    "La funzione (di sistema o logica) o l'attore esterno che <b>usa</b> il dato.<br>Uno scambio collega un "
    "produttore a un utilizzatore: con più utilizzatori si registra uno scambio per ciascuno, con lo stesso "
    "Exchange Item. Uno scambio si registra una volta e si riusa nelle catene (SA5-10).")
FE_ITEM = (
    "L'<b>Exchange Item</b> (SA-6) trasportato: che cosa passa dal produttore all'utilizzatore. Si sceglie dal "
    "dizionario: un dato si definisce una volta e si riusa.<br>Fuori dai domini di codifica si usano i dati "
    "logici, non la forma esterna di un'interfaccia (SA5-13).")
FE_NATURE = (
    "La natura del dato trasportato, <b>ereditata dall'Exchange Item</b>: si cambia nella sua scheda."
    "<ul style='margin-left:-20px'>"
    "<li><b>FLOW</b>: un valore sempre disponibile; conta l'ultimo valore.</li>"
    "<li><b>EVENT</b>: un fatto accaduto in un istante, da non perdere.</li>"
    "<li><b>OPERATION</b>: una richiesta di azione rivolta a un altro dominio.</li></ul>")
FE_CONDITION = (
    "<b>Quando</b> il produttore scrive il dato. Deve essere coerente con il tipo (SA5-08):"
    "<ul style='margin-left:-20px'>"
    "<li>FLOW: <b>Sempre</b> o <b>A ogni variazione</b>;</li>"
    "<li>EVENT: <b>Su evento</b>;</li>"
    "<li>OPERATION: <b>Su richiesta</b>.</li></ul>")
FE_CLAUSES = (
    "Le <b>voci SRS</b> che richiedono lo scambio. Devono essere tracciate dal produttore o dall'utilizzatore "
    "(SA5-12).")
FE_STATUS = (
    "<ul style='margin-left:-20px'>"
    "<li><b>Proposto</b>: ipotesi di un team, da discutere con l'altro dominio.</li>"
    "<li><b>Concordato</b>: i referenti del produttore e dell'utilizzatore ne hanno condiviso contenuto e "
    "condizione di produzione.</li>"
    "<li><b>Approvato</b>: confermato dalla Design Authority.</li></ul>"
    "Uno scambio tra domini non ancora concordato è segnalato (SA5-11); dove una catena cambia dominio serve uno "
    "scambio concordato (SA7-07).")

# --- the state of a sheet (SA-6, SA-7…) -------------------------------------------------------------------------

SHEET_STATUS = (
    "<ul style='margin-left:-20px'>"
    "<li><b>Bozza</b>: in compilazione.</li>"
    "<li><b>In revisione</b>: completa, da rivedere.</li>"
    "<li><b>Approvato</b>: rivista e confermata. Una scheda approvata deve avere i campi principali compilati "
    "(GEN-08).</li></ul>")

# --- SA-6: exchange item ----------------------------------------------------------------------------------------

EI_ID = (
    "<b>EI-Nome</b>: formato da ATLAS dal nome, senza articoli e preposizioni (es. «Evento di accensione» → "
    "EI-EventoAccensione). Compare mentre si scrive il nome e resta fisso dal primo salvataggio.<br>I dati con "
    "suffisso TIU o DMI sono la forma esterna di un dato; il dato logico corrispondente ha un EI distinto.")
EI_NAME = (
    "Il nome del dato: un sostantivo, non un'azione (es. «Stato dei banchi»).<br>Un dato si definisce una sola "
    "volta nel dizionario: due Exchange Item con lo stesso nome sono segnalati (SA6-08).")
EI_CONTENT = (
    "Che cosa <b>contiene</b> il dato: i suoi campi o valori, con l'unità se serve (es. «Banco A attivo/non attivo; "
    "banco B attivo/non attivo», «Pressione condotta generale (kPa)»).<br>Per un dato di interfaccia esterna vanno "
    "indicati (SA6-04). Le variabili del capitolo 7 (es. V_TRAIN, M_MODE) indicano una codifica esterna (SA5-13).")
EI_ORIGIN = (
    "Dove è definito il dato: le voci del SUBSET-026 (es. 4.6.3 [4]) o un'altra specifica (SUBSET-034/119, "
    "ERA_ERTMS_015560), oppure «Dipende dal veicolo» o «Dipende dall'impianto». Va indicata (SA6-07).")
EI_PRODUCER = (
    "<b>Calcolato da ATLAS</b>: chi produce il dato negli scambi funzionali (SA-5) che lo trasportano.<br>Deve "
    "essere uno solo (D10, SA6-01). Un dato che nessuno scambio trasporta non ha produttore né utilizzatori "
    "(SA6-02).")
EI_USERS = (
    "<b>Calcolati da ATLAS</b>: le funzioni e gli attori esterni che ricevono il dato negli scambi funzionali "
    "(SA-5) che lo trasportano.")
EI_NOTES = (
    "Osservazioni sul dato: il dato logico corrispondente a uno esterno (es. «Codifica esterna; il dato logico è "
    "EI-StatoBanchi»), le questioni aperte, i limiti d'uso.")

# --- SA-7: functional chain -------------------------------------------------------------------------------------

FC_ID = (
    "<b>FC-Nome</b>: formato da ATLAS dal titolo, senza articoli e preposizioni (es. «Isolamento dell'EVC» → "
    "FC-IsolamentoEVC). Compare mentre si scrive il titolo e resta fisso dal primo salvataggio.")
FC_TITLE = (
    "Che cosa fa la catena, dall'evento che la avvia all'effetto finale (es. «Test di avvio dei sottosistemi "
    "collegati»).")
FC_DOMAINS = (
    "I domini delle funzioni del percorso, aggiunti da ATLAS mentre si compilano i passi: restano finché una loro "
    "funzione è nel percorso.<br>Con «Seleziona» si spuntano gli altri domini coinvolti. Una chain senza domini è "
    "segnalata (SA7-13).")
FC_STARTABLE = (
    "Se la catena si può eseguire con il catalogo attuale delle funzioni di sistema:"
    "<ul style='margin-left:-20px'>"
    "<li><b>Avviabile</b>: tutte le funzioni ci sono;</li>"
    "<li><b>Avviabile completando DFnn</b>: manca una funzione di quel dominio;</li>"
    "<li><b>Bloccata</b>: mancano funzioni o decisioni prima di poterla percorrere.</li></ul>")
FC_TRIGGER = (
    "L'<b>evento che avvia</b> la catena, di solito uno scambio da un attore esterno (es. «Alimentazione di "
    "bordo: evento di accensione (FE-PWR-DF08-01)»).<br>La catena inizia su un attore esterno (SA7-04); il "
    "trigger va indicato (SA7-05).")
FC_EFFECT = (
    "Che cosa <b>si osserva all'esterno</b> alla fine: un messaggio, un comando o un'indicazione verso un attore "
    "esterno (es. «Treno: freno di emergenza revocato all'ingresso in SB»).<br>La catena finisce su un attore "
    "esterno (SA7-04); l'effetto va indicato (SA7-05).")
FC_PRECONDITIONS = (
    "Lo stato in cui deve trovarsi il sistema perché la catena parta: modo, livello, sessione, dati validi (es. "
    "«EVC non alimentato (NP)»).")
FC_POSTCONDITIONS = (
    "Lo stato del sistema alla fine della catena (es. «Modo SB, oppure SF; disponibilità dei sottosistemi nota»).")
FC_OUT_OF_SCOPE = (
    "Quello che la catena non copre e dove è trattato, con l'ID dell'altra catena (es. «Proseguimento in SB: "
    "FC-Accensione-SB»).")
FC_STEPS = (
    "Ogni riga è un <b>passo</b>: la funzione riceve un dato (<b>Ingresso</b>), fa una cosa (<b>Cosa fa</b>) e "
    "produce un dato (<b>Dato prodotto</b>), che esce con lo <b>Scambio in uscita</b>. «#», «Dominio» e «Nome "
    "funzione» li calcola ATLAS."
    "<ul style='margin-left:-20px'>"
    "<li>Tra due cicli (C0, C1…) va una riga di attesa: «—» in Ciclo, «Attesa: …» in Cosa fa, il resto vuoto "
    "(SA7-11).</li>"
    "<li>Natura «Interno» per un dato che resta nella funzione, senza scambio in uscita.</li>"
    "<li>Ogni cambio di dominio passa da uno scambio concordato (SA7-07), continuo con i passi (SA7-06).</li>"
    "<li>Ogni passo cita le voci SRS di bordo tracciate dalla sua funzione (SA7-09, SA7-10).</li></ul>")
FC_USED = (
    "<b>Calcolati da ATLAS</b> dal percorso: gli scambi ricevuti e prodotti dai passi, una volta ciascuno, con "
    "produttore, utilizzatore, dato, natura, tipo (tra domini o con attore esterno) e stato.")

# --- SA-1: functional domain ------------------------------------------------------------------------------------

DF_ID = (
    "<b>DFnn</b>: assegnato da ATLAS in ordine. Se un dominio viene eliminato, i successivi scalano di numero "
    "insieme agli ID delle loro funzioni e dei loro scambi.")
DF_NAME = (
    "Il nome dell'area funzionale (es. «Odometria», «Gestione dei modi»). Un dominio raggruppa responsabilità, non "
    "è un pezzo di software: non porta il nome di un componente logico (SA1-07).")
DF_MISSION = (
    "Lo <b>scopo</b> del dominio in una o due frasi (D1, SA1-01): che cosa garantisce al resto del sistema.<br>Se "
    "non sta in una frase, va valutata una scissione o una ridefinizione dello scopo con un'ADR.")
DF_TEAM = (
    "Il team (EPBS-1) che sviluppa il dominio, assegnato dalla Design Authority. Resta allineato con i «Domini» "
    "della scheda del team (SA1-02); ogni dominio ha un solo team (SA1-03).")
DF_REFERENT = (
    "Il membro del team che <b>risponde</b> del dominio e riceve le notifiche che lo riguardano. Quando si assegna "
    "il team, è proposto il referente del team (SA1-04).")
DF_COMPONENTS = (
    "I componenti logici (LA-1) che si prevede realizzino le funzioni del dominio. Devono corrispondere "
    "all'allocazione delle sue funzioni logiche (SA1-08).")
DF_ADRS = (
    "<b>Calcolate da ATLAS</b>: le ADR che riguardano il dominio (nuovo dominio, eliminazione, fusione, "
    "riallocazione di clausole…), per esito. Doppio clic su una riga per aprirla.")

# --- SA-2: system function --------------------------------------------------------------------------------------

SF_ID = (
    "<b>SF-DFnn-mm</b>: assegnato da ATLAS con il dominio e il primo numero libero. Se la funzione passa a un altro "
    "dominio, «Rinumera» lo riallinea (SA2-02).")
SF_NAME = (
    "<b>Verbo all'infinito + oggetto</b> (D5, SA2-03), es. «Supervisionare lo standstill».<br>Senza sigle di modo o "
    "livello né numeri di paragrafo (SA2-04). Una funzione non si duplica per modo, livello o versione (SA2-05) e "
    "il nome è unico (SA2-06).")
SF_DOMAIN = (
    "Il dominio a cui appartiene la funzione (D2, SA2-01). Le voci SRS che traccia sono del suo dominio (SA2-09). "
    "Spostarla in un altro dominio richiede un'ADR di spostamento.")
SF_DESCRIPTION = (
    "Che cosa fa la funzione: che cosa riceve, che cosa ne fa, che cosa produce. Va compilata per salvare la "
    "scheda.")
SF_ROWS = (
    "Le righe della tabella 4.5.2 (in quali modi la funzione è attiva), nel formato <b>4.5.2-Rnn</b>. Una riga "
    "appartiene a una sola funzione (SA2-15).")
SF_COMPONENT = (
    "Il componente logico (LA-1) che si propone realizzi la funzione. Deve corrispondere all'allocazione delle "
    "funzioni logiche che la raffinano (SA2-17).")
SF_NEW = (
    "Da spuntare se la funzione non è nel catalogo di riferimento ed è proposta dal team: va indicato il motivo "
    "(SA2-10) e, una volta approvata, va collegata un'ADR (SA2-11).")
SF_REASON = (
    "Perché serve una funzione nuova: quale voce SRS il catalogo non copre. Si compila solo per una funzione nuova "
    "(SA2-10).")
SF_NOTES = "Osservazioni, scelte fatte e dubbi da portare in revisione."
SF_ADRS = (
    "<b>Calcolate da ATLAS</b>: le ADR che riguardano la funzione (es. lo spostamento in un altro dominio), per "
    "esito. Doppio clic su una riga per aprirla.")
SF_STATUS = (
    "<ul style='margin-left:-20px'>"
    "<li><b>Proposta</b>: scritta dal team, da rivedere.</li>"
    "<li><b>Rivista</b>: esaminata in revisione, con le osservazioni recepite.</li>"
    "<li><b>Approvata</b>: confermata. Una funzione approvata deve avere i campi principali compilati "
    "(GEN-08).</li></ul>")

# --- SA-3: outcome of the tracing of an SRS item ----------------------------------------------------------------

TR_ITEM = (
    "La voce SRS di cui si registra l'esito di tracciatura. Una voce ha un solo esito (SA3-01, SA3-02); ogni voce "
    "di bordo deve averne uno (SA3-15).")
TR_CATEGORY = (
    "<b>Letta dalla voce SRS</b>: la sua categoria del capitolo 9 (Bordo, Terra, Definizione, Informativa…). "
    "Orienta la domanda B5 (SA3-04).")
TR_PRIMARY = (
    "Le funzioni di sistema che <b>realizzano l'obbligo</b> della voce (B5 domanda 6), del dominio a cui la voce è "
    "allocata (SA3-12). Obbligatorie per «Tracciata a funzione» (SA3-05); solo funzioni di sistema, non logiche "
    "(SA3-14).")
TR_SECONDARY = (
    "Le funzioni che <b>contribuiscono</b> all'obbligo senza esserne responsabili. Non ripetono le primarie "
    "(SA3-13); tra primarie e secondarie al più tre funzioni (SA3-06).")
TR_DERIVED = (
    "I <b>requisiti derivati</b> (SA-4) in cui la voce è scomposta, o gli <b>Exchange Item</b> (SA-6) che ne "
    "definiscono il formato. Servono per «Scomposta in requisiti derivati» (SA3-07) e «Tracciata al dizionario» "
    "(SA3-08); per «Ipotesi d'ambiente» il dato atteso (SA3-09).")
TR_B5 = (
    "Le domande della B5 si pongono in ordine: la <b>prima</b> a cui la voce risponde sì decide l'esito (SA3-03)."
    "<ol style='margin-left:-20px'>"
    "<li>Definizione, informativa o altro nel cap. 9 → <b>Non tracciata</b>.</li>"
    "<li>Solo terra → <b>Ipotesi d'ambiente / dato atteso</b>.</li>"
    "<li>Formato di dati → <b>Tracciata al dizionario</b>.</li>"
    "<li>Obblighi di domini diversi → <b>Scomposta in requisiti derivati</b>.</li>"
    "<li>Solo versione di sistema 1 → <b>Collegata alla voce nominale</b>.</li>"
    "<li>Altrimenti → <b>Tracciata a funzione</b>.</li></ol>"
    "Una voce di bordo risponde a una domanda da 3 a 6; uno scostamento dalla categoria va motivato nelle note "
    "(SA3-04).")
TR_OUTCOME = (
    "L'esito della tracciatura, quello della domanda B5 decisiva (SA3-03). «Coperta dalla clausola inclusa»: la "
    "voce include altre clausole, e per quella parte è coperta dalla loro tracciatura.")
TR_NOTES = (
    "Motivazioni e osservazioni: in particolare perché la domanda B5 si scosta da quella attesa per la categoria "
    "della voce (SA3-04).")
TR_ADRS = "Le ADR collegate all'esito (es. una scelta lasciata all'implementazione, B5 domanda 1)."
TR_STATUS = (
    "<ul style='margin-left:-20px'>"
    "<li><b>Da analizzare</b>: voce ancora da esaminare.</li>"
    "<li><b>Proposto</b>: esito scritto dal team.</li>"
    "<li><b>Rivisto</b>: esaminato in revisione.</li>"
    "<li><b>Approvato</b>: confermato.</li></ul>")
