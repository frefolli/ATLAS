# Changelog

Le modifiche rilevanti di ogni versione di ATLAS. Le versioni seguono il [versionamento semantico](https://semver.org/lang/it/):
finché ATLAS è in sviluppo (versioni 0.x), il formato dei progetti e l'interfaccia possono cambiare tra una versione e
l'altra.

## [Non rilasciato]

## [0.9.3] - 2026-11-06

### Aggiunto
- **L'approvazione di una riallocazione sposta le voci.** La DA approva con «Approva e sposta le voci» nella scheda
  dell'ADR: una sezione (es. 3.8.1) o una clausola (es. 3.8.1.4) passa al dominio proposto, con i contributori proposti.
  Una clausola può passare a un dominio che non ha la sua sezione: è un'eccezione, e la sezione non cambia. Prima di
  confermare, ATLAS mostra cosa passa, le clausole interne che restano al loro dominio per una decisione precedente e
  le funzioni di altri domini che tracciano quelle voci, che non si spostano da sole. L'ADR approvata resta com'era,
  per la tracciabilità: «Dominio principale attuale» e «Contributori attuali» continuano a mostrare i domini di allora,
  e l'ADR resta nelle tabelle delle schede del dominio di origine.
  - Non si approva senza un dominio principale proposto. Si spostano solo clausole intere: un punto di elenco o una
    riga di tabella segue la sua clausola; da solo si gestisce derivandone un requisito.
  - Le ADR già decise e mai applicate si trovano con il controllo A4-10 e si applicano con «Applica la riallocazione».
- **Liste delle ADR per esito.** La pagina delle ADR ha le schede «Tutte», «In revisione», «Approvate», «Respinte» e
  «Superate», ciascuna con il suo conteggio. La ricerca vale dentro la scheda scelta.
- **Clausole ricevute e cedute nelle schede dei domini.** Due elenchi, con il riferimento all'ADR, separati da «Sezioni
  SRS principali».

### Rimosso
- **Indicatore «Vista da N» delle ADR.** Nella testata della scheda non compare più chi ha letto l'ADR. Le notifiche
  restano uguali, con «Nuova» e «Letta» per il singolo utente.

### Modificato
- **Controllo A4-04.** Non segnala una clausola fuori dalla sua sezione se c'è un'ADR decisa che la giustifica; altrimenti
  dice se l'ADR è ancora da decidere o se manca.

## [0.9.2] - 2026-11-05

### Aggiunto
- **Indicazione di salvataggio in corso.** Ogni salvataggio (la barra in alto, la scheda o la vista, lo stato di una
  scheda, un messaggio di discussione) e la pubblicazione non bloccano più la finestra: se durano più di un istante
  compare una finestra con la barra animata, «Salvataggio in corso…» o «Pubblicazione in corso…». Quando le verifiche
  si rieseguono dopo il salvataggio, la barra di stato scrive «Aggiornamento delle verifiche…».
- **Pulsante «Scarta» prima di «Salva».** Compare nella barra in alto quando ci sono modifiche locali (non salvate, o
  salvate e non pubblicate) e riporta il modello all'ultima versione pubblicata del ramo.
- **Finestra delle modifiche che verranno scartate.** Quando si scartano le modifiche locali, dal nuovo pulsante, da
  *Versioni Modello*, al cambio di ramo o alla chiusura del progetto senza salvare, una finestra simile a «Pubblica»
  mostra cosa si perde e permette di annullare.
- **Deriva requisiti dalla scheda di una funzione.** Nella sezione «Clausole SRS mappate» (ex «Allocazione alle voci
  SRS e ai requisiti derivati») di una funzione di sistema o logica, il clic destro su una clausola mappata offre
  «Deriva requisiti…». I requisiti creati sono mappati sulla funzione e compaiono nel suo elenco dei requisiti derivati.

### Corretto
- **Registro di tracciabilità sempre aggiornato quando si deriva.** Il registro SA-3 della voce si creava o aggiornava
  solo con «Deriva…» del catalogo Voci SRS. Ora vale anche per un requisito creato da *SA-4 Requisiti derivati* nel
  menu laterale, per «Deriva requisito da…» del catalogo e per la derivazione dalle finestre di tracciabilità.
- **Cancellare un requisito derivato aggiorna il registro di tracciabilità.** Il requisito esce dall'elenco del
  registro SA-3. Con l'ultimo requisito derivato si cancella anche il registro della voce; se contiene altro (funzioni,
  voci di dizionario, note, ADR) resta, con esito e domanda B5 da scegliere di nuovo.

### Modificato
- **Derivabili tutte le voci SRS tranne capitoli e sezioni.** Si derivano requisiti (SA-4) da ogni clausola
  (es. 3.8.1.1), dalle sue sottoclausole e anche dai punti di elenco e dalle righe di tabella (es. 3.4.4.2.3 b),
  4.5.2-R18), che prima non avevano il pulsante «Deriva…» né «Deriva più requisiti…». Non sono derivabili i capitoli
  e le sezioni (tre numeri, es. 3.8.1): sulle loro righe «Deriva» non compare più, e nella scelta della voce madre
  non si possono spuntare.
  - Un punto di elenco si traccia alle funzioni di sistema con la sua clausola: ha solo «Deriva…».
  - Il pulsante «Funzioni…» delle righe delle clausole si chiama ora «Mappa a Funzione».
  - Report di copertura: un requisito derivato da un punto di elenco, o da una riga di tabella, copre la clausola
    che lo contiene.

## [0.9.1] - 2026-11-05

### Aggiunto
- **Integrazione dei rami in ATLAS.** Nella finestra *Versioni › Rami*, «Integra nel ramo in uso…» unisce le
  versioni del ramo selezionato in quello in uso, con la stessa unione di «Ricevi»: per scheda e per campo, con gli
  identificativi automatici doppi rinumerati e le tracciature riallineate. È l'alternativa all'unione con Git, che
  unisce i file riga per riga e non sa né rinumerare né riallineare le tracciature.
  - **Anteprima e annullamento:** la finestra mostra il modello del ramo in uso prima e dopo l'integrazione, come
    «Pubblica». Quello che si unisce da solo è già unito; restano da scegliere solo i conflitti, e l'anteprima segue
    le scelte. «Annulla integrazione» chiude senza cambiare nulla.
  - **Cancellazione del ramo integrato:** dopo l'integrazione ATLAS chiede se cancellare il ramo integrato. Il ramo
    sparisce subito da questo PC e dalla finestra Rami, e dal repository con il prossimo invio. «Pubblica» e
    «Invia» lo indicano. Se nel frattempo un collega vi ha inviato versioni non integrate, il ramo resta sul
    repository e l'invio lo segnala. Il ramo principale non si cancella.
  - **Rami senza storia in comune**, cioè progetti nati separatamente: non si integrano, perché raddoppierebbero
    voci SRS, domini, funzioni e team. La finestra lo spiega.
  - **Unioni fatte con Git:** le unioni fatte da ATLAS sono marcate nel messaggio della versione. Se fra le versioni
    ricevute o integrate c'è un'unione fatta fuori da ATLAS, un avviso invita a eseguire «Verifica modello»
    (GEN-02, ID duplicati).
- **Ramo principale riservato alla Design Authority.** Il ramo principale (master o main) lo modifica solo la DA:
  pubblicare, inviare, integrare (anche con «Ricevi») e riportarlo a una versione con il checkout forzato. Chi non è
  della DA lavora su un ramo suo, che la DA poi integra; può sempre integrare il ramo principale nel proprio, per
  aggiornarlo. Finché il team DA non ha membri, il ramo principale lo modifica chiunque.
  - **Pubblica:** sul ramo principale è disattivata la scelta del ramo in uso; la versione va su un nuovo ramo.
  - **Invia e Ricevi:** se ci sono versioni non inviate sul ramo principale, ATLAS propone «Sposta le mie versioni
    su un nuovo ramo…»: le versioni passano a un ramo nuovo, da inviare, e il ramo principale torna come sul
    repository.

### Modificato
- **Tracciature riallineate dopo ogni unione.** Dopo «Ricevi» e «Integra», le schede unite campo per campo
  riapplicano le regole delle schede collegate, come quando la modifica si fa nella scheda: il team di un dominio e
  i domini del team, le funzioni di un record SA-3 e le loro voci SRS, le esclusioni. Ad esempio, se un ramo
  assegna un dominio a FBK e l'altro a UniMiB e si sceglie FBK, UniMiB non lo elenca più tra i suoi.

## [0.9.0] - 2026-11-04

### Aggiunto
- **Pubblicazione selettiva.** Nella finestra «Pubblica» ogni modifica ha una spunta, e si pubblicano solo quelle
  spuntate. Ciò che resta fuori rimane come modifica locale, da pubblicare dopo.
  - **Dipendenze:** la versione pubblicata non fa mai riferimento a un elemento che non contiene.
    - Un elemento nuovo, o modificato, che usa un elemento nuovo si pubblica con lui. Ad esempio, una funzione
      nuova in un dominio nuovo.
    - L'eliminazione di un elemento si pubblica con le modifiche degli elementi che lo citavano.
    - Togliendo la spunta a una modifica si tolgono anche quelle che ne dipendono; spuntandone una si spuntano
      quelle che le servono. Una nota sotto l'elenco dice cosa è stato escluso o aggiunto e perché.
  - **Allegati e impostazioni:** gli allegati seguono gli elementi pubblicati, ad esempio il file di un messaggio
    si pubblica con il messaggio. Le impostazioni condivise del progetto si possono lasciare fuori con la loro
    spunta.
  - **Ingrandimento:** la finestra «Pubblica», come quelle delle versioni, del confronto e delle modifiche prima
    di «Ricevi», si può ingrandire.
- **Versione locale in «Versioni Modello».** Il pulsante «Cronologia» si chiama ora «Versioni Modello». Sul ramo in
  uso la finestra mostra, in cima alle versioni pubblicate, la riga «Versione locale» con le modifiche di questo PC
  non ancora pubblicate, ad esempio «2 modifiche non pubblicate (1 non ancora salvate)».
  - **Doppio clic:** le mostra, a confronto con l'ultima versione pubblicata.
  - **Pubblica…:** ne fa una nuova versione.
  - **Scarta le modifiche locali…:** dopo una conferma, riporta il modello all'ultima versione pubblicata del ramo
    in uso. Toglie tutto ciò che non ne fa parte: modifiche salvate e non salvate, schede in modifica, elementi
    nuovi (anche letture e messaggi) e allegati, compresi i file comparsi sul disco nel frattempo. Senza versioni
    pubblicate non c'è nulla a cui tornare, e il pulsante resta disattivato.
- **Discussione delle ADR e delle richieste di chiarimento (CQ).** In fondo alla scheda di ogni ADR e di ogni CQ, i
  membri dei team scrivono messaggi in fila, ciascuno con autore, team e data.
  - **Scrittura:**
    - con «Rispondi» un messaggio cita quello a cui risponde;
    - il testo accetta la formattazione Markdown;
    - chi è in più team sceglie per quale scrive.
  - **Allegati:** file fino a 20 MB, salvati nel progetto, da aprire o salvare con nome.
  - **Salvataggio:** il messaggio si salva subito, da solo, anche con la scheda in sola lettura o con modifiche in
    corso, che non vengono salvate con lui. Arriva ai colleghi con «Pubblica» e «Invia», e per loro con «Ricevi».
    Ogni messaggio è un file a sé, quindi due messaggi scritti in contemporanea su due rami si uniscono senza
    conflitti.
  - **Messaggi nuovi:**
    - nell'albero ogni ADR e CQ mostra quanti messaggi degli altri non sono ancora stati letti su questo PC;
    - aprendo la scheda diventano letti;
    - dopo «Ricevi», la barra di stato dice quanti messaggi nuovi sono arrivati e in quante discussioni;
    - nella discussione i messaggi nuovi e quelli non ancora pubblicati sono indicati come tali.
  - **Regole:**
    - l'autore modifica o elimina i propri messaggi; un messaggio eliminato resta come «messaggio eliminato»,
      senza testo né allegati;
    - la Design Authority può nascondere un messaggio agli altri;
    - la discussione si chiude, e resta in sola lettura, quando la DA approva l'ADR o quando la CQ è chiusa;
    - eliminando un'ADR o una CQ si elimina anche la sua discussione.

- **Notifiche delle ADR ai team di destinazione.** Quando un team propone un'ADR che coinvolge come destinazione un
  dominio di un altro team, tutti i membri di quel team ricevono una notifica.
  - **Destinazione:** cosa conta come destinazione dipende dal tipo di ADR, ad esempio il dominio principale o i
    contributori proposti per una riallocazione, il dominio proposto per lo spostamento di una funzione, i domini
    da fondere o il team proposto. Chi propone non riceve notifiche sulla propria ADR.
  - **Eventi:** l'ADR creata (se aperta), modificata in qualsiasi campo (con i campi cambiati) ed eliminata. Se la
    destinazione passa a un altro team, la notifica lo segue. Il pannello raccoglie anche i messaggi nuovi delle
    discussioni che riguardano l'utente.
  - **Dove si vedono:**
    - la campanella «Notifiche (N)» nella barra in alto apre il pannello delle notifiche, dove si aprono, si segnano
      come lette o di nuovo come non lette, per riesaminarle. La colonna «Stato» dice «Letta» se l'hai aperta su
      questo PC e «Nuova» se non l'hai ancora aperta o l'hai rimessa come non letta (le letture dei colleghi, anche
      dello stesso team, non contano). Cosa è successo (modificata, eliminata, un messaggio) è nel dettaglio; il
      pallino e il grassetto segnano ciò che è da vedere, anche una «Letta» cambiata dopo la lettura;
    - all'apertura del progetto e dopo «Ricevi» un avviso dice quante notifiche ci sono da leggere;
    - nell'albero un pallino blu a sinistra dell'ADR o della CQ segnala che c'è qualcosa da vedere (la notifica o
      messaggi nuovi, di cui è indicato il numero) e sparisce quando l'hai vista.
  - **Lettura:** aprire l'ADR ne segna la notifica come letta. Lo stato di lettura resta su questo PC, ma la lettura
    viene registrata anche nel progetto, con il membro, il team e la versione letta. Nella testata della scheda
    dell'ADR, accanto allo stato, un indicatore dice «Non ancora vista» o «Vista da N». È verde quando tutti i team
    attesi hanno letto la versione attuale, ambra altrimenti. Un clic apre un riquadro con chi ha letto, quando, se
    ha letto la versione attuale, e i team che non l'hanno ancora letta. Ogni lettura è un file a sé, quindi le
    letture fatte su rami diversi non vanno in conflitto.
  - **Nessun server:** le notifiche sono calcolate dal modello. Arrivano con l'ADR (Pubblica, Invia, Ricevi) e
    funzionano senza rete.
  - **Design Authority:** i suoi membri ricevono la notifica di ogni ADR, di qualsiasi team, tranne quelle aperte
    dalla DA stessa, cioè proposte dal team DA o da un suo membro. Per loro il dettaglio dice chi propone, verso
    quali domini e team, e lo stato, ad esempio «Proposta da T3 · verso DF04 (T2) · In revisione DA». La loro
    lettura viene registrata con il team DA, e l'indicatore della scheda segnala se la DA non l'ha ancora letta.
  - **Pannello diviso per motivo:** le notifiche sono separate in schede, ciascuna con le non lette, cioè «Tutte»,
    «Il mio team», «Design Authority» (solo per i suoi membri) e «Messaggi». Anche l'avviso e il suggerimento della
    campanella distinguono le notifiche per il proprio team, quelle da esaminare come DA e i messaggi.
  - **Prestazioni:** le notifiche si calcolano una volta per ogni stato del progetto e di ciò che è stato letto, e
    campanella, albero e pannello riusano il risultato. Su un progetto con 44 ADR l'aggiornamento dell'albero passa
    da circa 3,5 s a meno di 20 ms. Anche l'elenco dei file pubblicati, usato dalle discussioni, si legge una volta
    per versione.

### Modificato
- **Menu «Info» e «Chiudi Progetto».** Il menu «Aiuto» si chiama «Info» e ha la nuova voce «Versione Corrente…», che
  mostra la versione di ATLAS in uso e le novità della sua release (il CHANGELOG è incluso nell'installazione).
  Nella barra in alto, accanto a «Salva», c'è il pulsante «Chiudi Progetto».
- **Barra in alto e finestra Rami.** «Versioni Modello» viene prima di «Rami». La finestra Rami non ha più i
  pulsanti «Cronologia», «Confronta con il mio stato attuale» e «Cosa ha cambiato rispetto a main»: le versioni di
  un ramo sono in «Versioni Modello», e il doppio clic su un ramo le apre.
  Anche «Versioni Modello» non ha più i pulsanti di confronto: si confronta con «Confronta» della barra in
  alto, e il doppio clic su una versione, o su quella locale, mostra cosa ha cambiato.
- **Avviso delle notifiche.** All'apertura del progetto e dopo «Ricevi» dice solo quante notifiche ci sono da
  leggere, per tipo, e chiede se aprire le Notifiche, senza elencarle.

### Corretto
- **Chiusura delle finestre Confronta e Rami durante il download dei rami.** La finestra «Confronta» scarica i
  rami del repository appena si apre, e finché il download era in corso la X (ed Esc) non la chiudevano: con
  una rete lenta restava aperta. Ora si chiude subito, come la finestra Rami durante «Aggiorna dal
  repository»; il download finisce da solo in background e aggiorna i rami.
- **Eliminazione di un'ADR di esclusione.** Eliminando un'ADR «Esclusione di sezione o clausola», durante la sessione
  veniva tolta dal modello l'ultima voce SRS esclusa al posto dell'ADR, che restava visibile. Su disco veniva
  cancellato il file dell'ADR, quindi alla riapertura del progetto tutto tornava a posto. Ora l'ADR si elimina
  subito e le voci restano.
- **Riavvio dopo l'aggiornamento automatico.** Alla fine dell'installazione ATLAS veniva riaperto subito, mentre
  l'installer stava ancora chiudendo il lavoro. Su alcuni PC le librerie appena installate erano ancora bloccate e
  compariva l'errore «DLL load failed while importing QtWidgets: … il file è utilizzato da un altro processo»,
  anche se l'aggiornamento era riuscito. Ora ATLAS si riapre una volta sola, qualche secondo dopo la fine
  dell'installazione, e Windows non lo riavvia per conto suo.

## [0.8.0] - 2026-11-02

### Aggiunto
- **Import delle ADR da Excel.** Clic destro sulle ADR nell'albero del modello, poi «Importa ADR…», e si scelgono
  uno o più file.
  - **File:** le schede X-1 dei team (un file per ADR) o il file delle ADR generato da ATLAS (un foglio per ADR),
    nei template di tutti i 14 tipi e in quello delle prime versioni («Riallocazione di sezione»).
  - **Tipo e campi:** il tipo si riconosce da «Tipo di decisione», altrimenti dal modello della scheda. Ogni riga si
    abbina al campo del tipo con la stessa etichetta, anche nelle varianti delle prime versioni («Sezione o
    clausola da riallocare», «Dominio principale proposto (destinazione)»). I testi guida si ignorano.
  - **Riferimenti:** voci SRS con le sottovoci, domini per ID o nome, team per ID, nome o sigla, membri anche come
    «G. Ioele», funzioni, exchange item, catene e ADR. I campi calcolati da ATLAS, come il dominio principale
    attuale, si confrontano con il modello e si segnalano se diversi.
  - **Membro proponente:** se il file non indica un membro del team proponente, ad esempio riporta solo «Unimib»
    come autore, si usa il referente del team, indicato così nell'anteprima.
  - **ID e stato:** l'ID è quello del nome del file (ADR-0010 diventa ADR-010) o del titolo, se nel modello è
    libero, altrimenti lo genera ATLAS. Lo stato è sempre «Proposta». La data e la decisione della DA non si
    importano.
  - **Anteprima:** prima di creare le ADR, una finestra le elenca con la spunta «Applica», i campi importati e gli
    avvisi. Sono avvisi, ad esempio, il titolo con un altro ID, più domini di destinazione, un dominio «da
    definire», un tipo non previsto o voci di sezioni diverse in una riallocazione. Ciò che non si imposta così
    com'è scritto resta nelle note della motivazione. Le ADR già nel modello o ripetute nei file non si importano.
  - **Report dell'importazione:** alla fine ATLAS chiede se salvarlo in Excel. Ha tre fogli:
    - *Riepilogo:* file letti e non letti, ADR importate, già nel modello, ripetute, non riconosciute o escluse
      nell'anteprima;
    - *ADR:* una riga per scheda, con l'ID nel file e nel modello, il tipo, il proponente, l'esito e il numero di
      avvisi;
    - *Dettaglio:* per ogni ADR i campi importati, le scelte fatte (da dove vengono l'ID, il tipo, il team e il
      membro proponente, come per il referente, e lo stato) e gli avvisi, con quelli riportati nelle note della
      motivazione.
- **Checkout di una versione del modello.** Nella finestra *Versioni › Rami*, «Checkout di una versione…» porta il
  modello completo a una versione scelta di un ramo, di questo PC o del repository (dopo «Aggiorna dal
  repository»). Il progetto passa su quel ramo, anche se non è ancora su questo PC.
  - **Ripristino (consigliato):** il ramo resta alla sua ultima versione; ciò che differisce è una modifica da
    pubblicare, inviata al repository come le altre.
  - **Riporto forzato del ramo:** il ramo di questo PC torna alla versione scelta e le successive non ne fanno più
    parte. Il repository non cambia, e ricevendo le versioni tornano. Prima della conferma ATLAS indica quante
    versioni escono dal ramo e avvisa se alcune, mai inviate, vanno perse.
  - **Modifiche in sospeso:** come per il cambio di ramo, prima si pubblicano o si scartano.

### Modificato
- **Più ID account per membro del team (più postazioni).** Chi lavora su più PC ha un account locale, e un ID, su
  ciascuno. Nella finestra del membro la DA li tiene in una lista: incolla un ID nel campo e preme «Aggiungi» (o
  Invio), anche con i trattini, e «Rimuovi» toglie quello selezionato. ATLAS riconosce
  la persona da qualunque delle sue postazioni, per l'accesso al progetto, i permessi della DA e le versioni
  pubblicate.
  - **Controlli:** un ID non valido, o già di un altro membro del team, viene segnalato.
  - **Tabella dei membri:** mostra il primo ID e quanti altri ce ne sono («87d54dd9… (+1)»); il suggerimento li
    elenca tutti.
  - **Confronto tra versioni e schede Excel:** riportano tutti gli ID.
  - **File del team:** un solo ID resta scritto come prima; più ID sono una lista. Le versioni precedenti di ATLAS
    non leggono una lista, quindi chi usa una postazione con più ID deve aggiornare ATLAS.
- **Registro SA-3: più funzioni primarie per voce.**
  - **Scheda:** il campo «Funzione primaria» diventa «Funzioni primarie», con una o più funzioni scelte a spunta e
    raggruppate per dominio, come le «Funzioni secondarie». La voce viene allocata a tutte.
  - **Progetti esistenti:** quelli salvati con una sola funzione primaria sono convertiti all'apertura.
  - **Verifiche e documenti:** le verifiche SA-3 (SA3-05, 10, 11, 12, 13, 14) considerano ciascuna funzione primaria.
    La colonna del template e della scheda SA-3 generata si chiama «Funzioni primarie».
- **Import delle funzioni SA-2: clausole una volta sola, anteprima per clausola, ID solo di ATLAS.**
  - **Clausole:** ognuna si alloca una volta sola per funzione. Le sottovoci e le ripetizioni della stessa clausola
    contano una volta; una clausola contenuta in una sezione anch'essa nel file passa per la sezione; una clausola
    numerata sotto un'altra clausola (3.6.5.1.4.1 sotto 3.6.5.1.4) resta un requisito a sé.
  - **Anteprima:** una riga per clausola, con quanto scritto nel file e cosa succede: «Si alloca», «Già allocata
    alla funzione: invariata», «Contenuta nella sezione…», «Non più nel file». Il riepilogo conta anche i
    riferimenti già contati.
  - **ID:** gli ID del file non si importano più, nemmeno come riferimento: li genera ATLAS. Le funzioni importate
    con le versioni precedenti perdono l'«ID nel catalogo SA-2» e restano riconosciute come importate.
- **Ricevi dal repository: prima le modifiche locali.** Se sul ramo in uso ci sono modifiche non pubblicate, ATLAS
  le mostra elemento per elemento, come nella finestra «Pubblica», e chiede cosa farne:
  - **Pubblica…:** vengono integrate con le versioni ricevute;
  - **Scarta le modifiche:** il progetto torna all'ultima versione pubblicata, poi riceve quelle del repository.

### Corretto
- **Membri di un team modificati con la scheda in sola lettura.** Nella scheda di un team non in modalità modifica,
  la matita, il doppio clic su un membro e «Aggiungi membro…» aprivano comunque la finestra del membro. La tabella
  mostrava il nuovo ID account, ma la modifica non arrivava al modello: niente «Salva», e «Pubblica» non la
  vedeva. Ora ATLAS chiede prima di passare in modalità modifica.
- **Pubblica e Ricevi con schede non salvate.** Le modifiche di una scheda ancora in modalità modifica, ad esempio
  l'ID account di un membro del team cambiato senza premere «Salva» nella scheda, non erano viste da «Pubblica», che
  segnalava «nulla da pubblicare». Ora ATLAS chiede prima se salvarle o scartarle.

## [0.7.0] - 2026-10-30

### Aggiunto
- **Aggiornamento automatico di ATLAS.**
  - **Quando:** all'avvio, al massimo una volta al giorno, e a richiesta da *Aiuto › Verifica aggiornamenti…*.
    ATLAS legge l'ultima release su GitHub. Senza rete non segnala nulla.
  - **Finestra:** mostra le note della nuova versione e tre scelte: «Aggiorna ora», «Più tardi» e «Salta questa
    versione». Una versione saltata non viene più proposta all'avvio.
  - **Installazione:**
    - il file viene scaricato con una barra di avanzamento e verificato con l'impronta SHA-256 della release;
    - ATLAS chiede di salvare le modifiche e si chiude;
    - l'installer gira in modo silenzioso e riapre ATLAS già aggiornato;
    - su Linux viene sostituita la cartella dell'archivio, se è modificabile dall'utente.
  - **Controllo all'avvio:** si disattiva da *Aiuto › Controlla gli aggiornamenti all'avvio*.
- **Requisiti derivati (SA-4) mappati sulle funzioni di sistema (SA-2).**
  - **Finestra:** nella scheda della funzione, il pulsante «Mappa requisiti derivati…» apre una finestra con le sole
    clausole da cui sono derivati dei requisiti e, sotto ciascuna, i suoi derivati da spuntare. Ci sono la ricerca,
    i capitoli e il filtro «Solo requisiti mappati». Il pulsante è sempre attivo, anche se nel modello non ci sono
    ancora requisiti derivati; nella scheda l'elenco dei derivati mappati sta sotto quello delle voci SRS.
  - **Regole:** un derivato ha una sola funzione di sistema. Se è già mappato su un'altra funzione, ATLAS chiede se
    spostarlo. Un derivato di un altro dominio prende il dominio della funzione, dopo una conferma.
  - **Schede:** quella della funzione elenca i derivati mappati; quella del derivato ha «Funzione di sistema (SA-2)»,
    scelta a spunta, accanto alla funzione logica.
  - **Verifiche:** SA4-11 (derivato non mappato su una funzione di sistema) e SA4-12 (funzione logica che non
    raffina la funzione di sistema del derivato).
  - **Report e documenti:** nel report di copertura, la voce da cui il derivato è derivato risulta coperta anche
    al livello «funzione di sistema». SA-2 e SA-4 (template e documenti generati) hanno le colonne «Requisiti
    derivati» e «Funzione di sistema».
- **Sezioni e clausole escluse da un dominio (A4)** con la nuova ADR **«Esclusione di sezione o clausola»**.
  - **Come si esclude:** la scheda del dominio ha il pulsante **«Escludi sezioni e clausole…»**, tra l'elenco delle voci
    a cui contribuisce e quello delle escluse, separato da «Traccia sezioni e clausole SRS…» (che resta con
    «Principale» e «Contribuisce»). Apre una finestra dello stesso aspetto
    con le sole sezioni principali del dominio, le loro sottosezioni e clausole, e la sola colonna «Esclusa».
  - **Sezione principale con voci escluse:** finché ha voci escluse non si toglie da «Principale»; prima si tolgono
    le esclusioni.
  - **ADR:** al clic su «Esclusa» ATLAS apre subito, in una finestra, l'ADR di esclusione in modifica, per
    scrivere il motivo della non tracciatura. L'ADR riporta le voci escluse, il dominio, le sezioni principali che
    le contengono (calcolate) e il dominio che eventualmente le traccia al suo posto.
  - **Quando la voce è esclusa:** solo quando l'ADR è salvata: la spunta resta e voce e ADR sono scritte su disco.
    Con «Annulla», o chiudendo la finestra senza salvare, l'ADR sparisce e la spunta non si mette. Eliminando
    l'ADR, le sue voci non sono più escluse.
  - **Più voci nella stessa ADR:** le ulteriori sezioni e clausole da escludere si aggiungono nella scheda dell'ADR,
    scelte a spunta tra quelle delle sezioni principali del dominio. Salvata l'ADR, risultano escluse anche quelle.
  - **Esclusione tolta** dalla scheda del dominio: la voce esce dalla sua ADR, se l'ADR esclude anche altre voci.
    Se era l'ultima e l'ADR è ancora «Proposta», ATLAS chiede se eliminarla.
  - **Scheda del dominio:** elenca anche le voci escluse. I tre elenchi (principali, a cui contribuisce, escluse)
    stanno uno sotto l'altro.
  - **Report di copertura:** una voce esclusa non risulta coperta dal dominio della sua sezione.
  - **Documenti:** il documento SA-1 riporta le voci escluse con la loro ADR, e il tipo ha il suo template
    (`Template_X-1.11_…`; i tre tipi che venivano dopo sono rinumerati da X-1.12 a X-1.14).
  - **Verifiche:** SA1-09 (voce esclusa senza ADR di esclusione) e SA1-10 (ADR di esclusione senza motivo).
- **Elenco delle funzioni di sistema:** il doppio clic su «SA-2 Funzioni di sistema» nell'albero apre, come per i
  domini, una tab con ID, nome, dominio, numero di sezioni e clausole SRS, numero di requisiti derivati e stato. Lo
  stato si cambia su ogni riga da un menu a tendina ed è salvato subito.
- **Lista delle ADR:** la colonna «DF impattati», ordinabile. Riporta i domini che l'ADR indica (da eliminare, da
  fondere, proposti…) e quelli letti dal modello (delle clausole da riallocare, della funzione da spostare).

### Modificato
- **Installazione su Windows per il solo utente**, in `%LOCALAPPDATA%\Programs\ATLAS`, senza privilegi di
  amministratore. Così gli aggiornamenti non chiedono la password di un amministratore.
  - Se sul PC c'è una versione installata per tutti gli utenti (in *Programmi*), l'installer avvisa di
    disinstallarla.
  - L'installer e l'archivio Linux sono accompagnati dalla loro impronta SHA-256 (`.sha256`).
- **Elenchi di voci nelle schede** (per esempio «Sezioni o clausole da riallocare» di un'ADR, «Voci SRS
  interessate»): il doppio clic su una voce SRS o su un requisito derivato apre una finestra con il suo testo
  completo, compresi elenchi e figure, con il pulsante per aprirne la scheda. Il doppio clic su un altro elemento
  ne apre la scheda. Funziona anche con la scheda in sola lettura.
- **Tabelle dei domini e delle funzioni:** cambiando lo stato su una riga, la tabella resta dov'era, alla stessa
  posizione di scorrimento e con la riga selezionata, invece di tornare alla prima riga.

### Rimosso
- **«Disponibilità nei modi (X / O)» delle funzioni di sistema:** tolta dalla scheda, dai template e dai documenti
  SA-2. I valori salvati con le versioni precedenti si tolgono all'apertura del progetto.
- **Verifiche SA2-12, SA2-13 e SA2-14**, che controllavano la disponibilità nei modi. Escono anche dai profili
  salvati, così «Verifica modello» non le segnala come sconosciute.

## [0.6.0] - 2026-10-30

### Aggiunto
- **Progetto › Genera**: genera in Excel gli artefatti SA-1…SA-7 e le ADR, compilati dal modello con il disegno
  dei template.
  - **«Schede Arcadia»** genera ciò che dicono le impostazioni. Se non sono valide (mai salvate, senza cartella,
    nessun artefatto con dati) spiega perché e propone di aprirle.
  - **«Impostazioni…»** apre la finestra in cui si sceglie cosa generare e dove:
    - gli artefatti, tutti o uno per uno; quelli senza dati nel modello non si possono scegliere ora;
    - i domini da includere;
    - la cartella di destinazione.

    «Salva» salva le impostazioni; «Salva e genera» genera anche.
  - **Dove si salvano le impostazioni:** la scelta è nel progetto (`project.yaml`), condivisa con il team; la
    cartella vale per questo PC. Un artefatto senza dati resta tra quelli voluti e si genera quando il modello ne
    avrà. «Tutte le ADR» comprende anche quelle create dopo.
  - **File:** uno per artefatto.
    - SA-1 e SA-2 hanno un foglio per dominio e si possono rileggere con «Importa clausole principali» e «Importa
      funzioni».
    - SA-3 è un foglio unico con tutte le voci tracciate e i loro requisiti derivati; SA-4, SA-5 e SA-6 sono fogli
      unici; SA-7 ha un foglio per chain.
    - Le ADR stanno in un file con il registro delle aperte e un foglio per ADR, con la decisione della DA.

    Se un file esiste già, ATLAS chiede prima di sostituirlo; alla fine il riepilogo ha «Apri cartella».
- **Import delle funzioni di sistema dal catalogo Excel SA-2 dei team** (un foglio per dominio): con «Importa
  funzioni da Excel SA-2…» nella scheda di una funzione di sistema, accanto ad «Alloca a sezioni e clausole SRS…»,
  oppure con «Importa funzioni…» nel menu del clic destro su «SA-2 Funzioni di sistema» nell'albero del modello.
  - **Cosa crea:** ogni funzione va nel dominio del suo foglio, con l'ID dato da ATLAS, allocata alle clausole della
    sua riga; si importano anche le funzioni senza clausole. Le sottovoci scritte dopo una clausola («3.5.3.4 b) f)»)
    sono tracciate con la clausola, e i gruppi come 4.8.1–4.8.3 valgono per tutte le clausole del gruppo.
  - **Altre colonne:** «Stato Sezione» «Nuova» segna la funzione come nuova, le note a margine vanno nelle note e lo
    stato «Proposto» diventa «Proposta».
  - **Re-import dello stesso file:** una funzione già nel dominio con lo stesso nome non si sovrascrive; solo le sue
    clausole si allineano al file. Le funzioni dei domini del file che nel file non ci sono più si eliminano; quelle
    create in ATLAS, mai importate, sono proposte senza spunta.
  - **Riepilogo:** prima di applicare mostra cosa cambia nel modello, con la spunta «Applica» per ogni funzione:
    funzioni nuove, aggiornate (clausole allocate e tolte), eliminate (con i riferimenti e le viste impattati) e
    senza modifiche.
- **ADR**:
  - **«Proponente (membro del team)»** in tutti i tipi, scelto tra i membri del team proponente; compare anche nel
    registro delle ADR aperte e nei template.
  - In tutti i tipi una sezione **«Decisione della DA»** con l'esito («Commenti DA», «Accolta», «Accolta con
    modifiche», «Respinta») e le osservazioni; solo i membri della Design Authority possono modificarla. Con
    «Commenti DA» l'ADR torna al proponente e resta attiva.
  - Gli stati **«In revisione DA»** e **«Revisionato DA»**: l'ADR è ancora aperta, senza data della decisione, e la
    DA può approvare un nuovo dominio.
- Schede di **dominio funzionale** e di **funzione di sistema**: in «Relazioni», al posto di «Decisioni collegate»,
  c'è la tabella delle ADR che li riguardano (esito, ID, titolo, tipo, stato, decisione DA), ordinate per esito.
  - **Quali compaiono:** attive, approvate, respinte e superate; sono le ADR che li citano o che ne leggono il
    dominio, più quelle collegate a mano nelle versioni precedenti.
  - **Azioni:** doppio clic apre l'ADR; «Nuova ADR…» ne crea una che li riguarda.
  - **Verifiche:** SA2-11 e SA2-14 tengono conto di tutte queste ADR.

### Modificato
- **Template SA-1…SA-7** allineati alle schede di ATLAS e generati dal codice (`scripts/make_sa_templates.py`),
  come quelli delle ADR. Tra le modifiche:
  - SA-1 ha le sezioni Identificazione, Descrizione, Tracciabilità e Relazioni, e la tabella delle ADR;
  - SA-2 ha descrizione, disponibilità nei modi, note, ADR e stato;
  - SA-3 è una tabella unica con sezione e dominio principale;
  - SA-4 ha nome sintetico e motivazione della derivazione;
  - SA-5 ha nome e accordi di produttore e utilizzatore;
  - SA-6 ha natura e significato;
  - SA-7 ha dato prodotto e natura separati, e lo stato.

  I template ADR usano lo stesso disegno, con la decisione della DA nella sua sezione.
- **ADR di riallocazione:** più clausole nella stessa ADR, purché della stessa sezione. Al clic su una voce di
  un'altra sezione la finestra di scelta avvisa che servono ADR separate. Le ADR salvate con una sola voce sono
  convertite all'apertura del progetto.
- **Lista delle decisioni architetturali (X-1):**
  - le colonne «Team proponente», «Membro proponente» e «Decisione DA» sostituiscono «Ambito» e «Data della
    decisione»;
  - la lista è ordinata per ID; un clic sull'intestazione di ID, Tipo, Team, Membro, Stato o Decisione DA la ordina
    per quella colonna.
- **Report di copertura:** una barra di caricamento mostra la fase, e la generazione è passata da circa 8 secondi a
  meno di uno.
- **Catalogo delle voci SRS:** alla prima apertura una barra di caricamento mostra quante voci sono pronte; durante
  una ricerca non compare. Con le 4540 voci del SUBSET-026 l'apertura è passata da circa 14 secondi a meno di 5:
  le figure si impaginano leggendone solo le dimensioni.
- **Import SA-2:** riconosce anche il catalogo generato da ATLAS. Nelle note mette solo le colonne senza
  intestazione.

### Corretto
- **Dominio principale e contributori attuali di una clausola** nelle ADR e nei documenti generati: una clausola
  senza dominio principale proprio prende quello della sezione che la contiene (A4), indicata accanto («da
  3.11.6»). Prima risultava «Nessuno».
- **Vista complessiva SA-2:** le funzioni mostravano 0 clausole anche se allocate; ora si contano le loro voci SRS.
- **Impostazioni delle verifiche:** il clic sul quadratino di un singolo controllo non lo attivava né disattivava.

## [0.5.0] - 2026-10-29

### Aggiunto
- **Viste grafiche della System Analysis**, dal pannello a sinistra, separate dagli elementi: il pannello ha le
  schede «Modello» e «Viste grafiche», con i diagrammi raggruppati per tipo e per SA.
  - **Vista complessiva** di SA-1 (un blocco con il nome di ogni dominio) e di SA-2 (i domini aperti sulle loro
    funzioni di sistema e sulle clausole tracciate; si chiudono e si riaprono con un clic sulla barra del titolo o
    sulla spunta).
  - Viste dei **domini funzionali** (SA-1) e delle **funzioni per dominio** (SA-2) create dagli utenti, con i soli
    domini e funzioni scelti; la vista ricorda quali domini sono aperti.
  - **Dataflow funzionale** (SA-5), **catena funzionale** e **scenario di scambio** (SA-7), creati con «Nuova vista…»
    o con il clic destro su un gruppo, quanti ne servono. Si compongono con gli elementi già presenti nel modello
    (trascinati dall'elenco a lato o con doppio clic); ATLAS disegna da solo gli scambi tra gli elementi della vista,
    i dati scambiati, i rimbalzi della catena (D4) e i messaggi dello scenario per ciclo.
  - «Salva vista» (o Ctrl+S) salva la vista nel modello; fino ad allora le modifiche restano nella tab (●). Le viste
    si pubblicano e si integrano come le altre schede ed esportano come immagine PNG o SVG.
- **Modifica del modello dalle viste**:
  - dalle viste di SA-1 si creano **domini funzionali** («Nuovo dominio…»), da quelle di SA-2 **funzioni di
    sistema** («Nuova funzione…»; in entrambe anche con il clic destro su un dominio), con l'ID dato da ATLAS;
  - **connettori nel dataflow** (FLOW, EVENT, OPERATION, nella scheda Strumenti): tracciati da una funzione di
    sistema a un'altra (o con un attore esterno) creano lo scambio funzionale e il suo dato di interfaccia, nuovo o
    del dizionario. Partono e arrivano su punti di attacco (dodici per elemento, di più quando un lato è pieno),
    mostrati al passaggio del mouse; le estremità di una freccia si spostano su altri punti trascinandone le
    maniglie. Un connettore con lo stesso dato tra gli stessi elementi è rifiutato con un avviso; un EVENT è prodotto
    «Su evento». Canc o clic destro su una freccia elimina lo scambio e chiede se togliere dal dizionario il dato non
    più usato (tenuto, viene riproposto per primo);
  - il **clic destro su un dominio**, in tutte le viste, mostra le azioni sul dominio: scheda, apri/chiudi, funzioni
    da mostrare o aggiungere alla vista, nuova funzione, nuovo dominio, elimina. Il clic destro su una funzione la
    apre o la elimina;
  - l'**eliminazione chiede sempre** se togliere l'elemento solo dalla vista o anche dal modello (per una funzione,
    dal catalogo delle funzioni) ed elenca nella stessa finestra gli elementi impattati: riferimenti che resteranno
    senza destinazione e viste da cui sparirà. Per un dominio si può scegliere di eliminare anche le sue funzioni.
    Vale anche per Canc sugli elementi selezionati.
- **Disegno delle viste**:
  - frecce del dataflow **instradate in automatico** a tratti orizzontali e verticali intorno agli altri elementi,
    ricalcolate quando si spostano funzioni o blocchi; le etichette non si coprono;
  - i blocchi dei domini trascinati si **allineano** a quelli vicini (bordi con bordi, centro con centro), con linee
    guida; altrimenti si posano sulla griglia di puntini (20 px) della tela bianca, che compare solo durante lo
    spostamento. Più elementi selezionati (clic, Ctrl+clic, Maiusc + riquadro) si spostano insieme;
  - la tela va **oltre l'area visibile** e si allarga con gli elementi; con la mano si trascina uno spazio vuoto (o si
    usa il tasto centrale) per spostarsi; un elemento portato verso il bordo fa scorrere la vista;
  - **zoom** dal menu del clic destro sulla tela (avanti, indietro, dimensione reale, adatta alla finestra), con
    Ctrl + rotella attorno al puntatore e con Ctrl++, Ctrl+-, Ctrl+0 (dal 20% al 400%). Dallo stesso menu si sceglie
    se mostrare le maniglie dei connettori su tutte le frecce o solo su quella selezionata;
  - **Ctrl+Z / Ctrl+Y** in tutte le viste annullano e ripetono le ultime operazioni sul disegno e sugli elementi del
    modello creati o eliminati dalla vista; **Ctrl+A** seleziona tutti gli elementi.
- **Pannelli laterali in stile VS Code**: a sinistra una barra di icone sempre visibile sceglie la scheda («Modello»,
  «Viste grafiche»); un clic sull'icona della scheda aperta chiude il pannello, un clic su un'icona lo riapre
  (anche Ctrl+Maiusc+B o trascinando il divisore). Lo stesso per il pannello a destra delle viste, con le schede
  **Strumenti** (la mano «Sposta» e i connettori) ed **Elementi** del modello da aggiungere (Ctrl+Alt+B). Stato e
  larghezza restano tra le sessioni.
- **Tabella dei domini funzionali**: il doppio clic su «SA-1 · Domini funzionali» nell'albero apre una tab con ID,
  nome, team assegnatario, responsabile e stato di ogni dominio e il pulsante per aprirne la scheda; lo stato si
  cambia su ogni riga da un menu a tendina, nel colore dello stato, e si salva subito (solo quel dominio).
- **Importa clausole principali…** nella scheda di un dominio, accanto a «Traccia sezioni e clausole SRS…»: legge la
  riga «Sezioni SRS principali» del foglio del dominio in un file Excel SA-1 (riconosciuto dall'ID o dal nome, o
  scelto a mano; i gruppi come 4.8.1–4.8.5 valgono da 4.8.1 a 4.8.5) e mostra un riepilogo delle voci con titolo,
  tipo e categoria: da importare, già principali, non trovate, riferimenti ad altri documenti (SUBSET-027,
  ERA_ERTMS_015560). Ogni voce da importare ha la spunta nella colonna «Importa»; quelle allocate anche ad altri
  domini (nel modello o in altri fogli dell'Excel) sono indicate. I contributi del dominio restano.
- **Report di copertura** delle voci SRS, dal pulsante della pagina delle voci SRS: la copertura del subset e una
  scheda per le clausole di **bordo** e una per quelle di **definizione**, coperte e scoperte. La copertura è prima
  di tutto a livello di dominio (della voce o della sezione che la contiene, A4); per ogni voce sono indicate anche
  le funzioni di sistema (SA-2) e i requisiti derivati (SA-4) che la coprono, con la percentuale di ogni livello.
  Due viste: **Per sezione** e **Per clausola** (le sezioni con le loro clausole fino all'ultima, con la categoria
  del cap. 9). Filtri, ricerca, esportazione in Excel; il doppio clic mostra il testo della voce in una finestra a
  parte, con il pulsante «Apri la scheda della voce».
- **Tab**: il clic destro su una tab offre **Chiudi**, **Chiudi le altre**, **Chiudi tutte** (per quelle con
  modifiche non salvate ATLAS chiede se salvarle).

### Modificato
- **Due salvataggi distinti**: «Salva» nella barra in alto (ora **Ctrl+Maiusc+S**) salva tutte le modifiche del
  modello, comprese quelle delle schede e delle viste aperte; il «Salva» di una scheda, «Salva vista» e **Ctrl+S**
  (la tab corrente) scrivono solo le modifiche fatte da quella pagina. Gli elementi creati o eliminati da una vista e
  le voci SRS tracciate o importate da una scheda si scrivono da soli.
- Le schede, la tela delle viste e le barre di icone arrivano fino al pannello «Analisi del modello» in fondo alla
  finestra.

### Corretto
- **Import delle voci SRS**: le sezioni che nel SUBSET-026 non hanno un'intestazione propria (le clausole seguono
  direttamente il capitolo: 3.20.1, 3.5.1, 4.11.1, 5.13.1, 6.3.1, i gruppi di variabili 7.5.0 e 7.5.1) vengono
  aggiunte con il titolo del capitolo e una nota d'import, e le loro clausole vi sono agganciate; le sezioni
  dell'appendice (A.3.1…A.3.11) sono classificate come Sezione e non come Capitolo (le intestazioni A.3.4.1,
  A.3.6.1… come Titolo); un punto ripetuto negli ID del capitolo 9 («7..4.2.20.1») non crea più una voce a parte.
  Nei progetti già importati basta reimportare i capitoli: le allocazioni ai domini restano.

## [0.4.0] - 2026-10-28

### Aggiunto
- *Versioni › Ricevi dal repository*: riceve le versioni pubblicate dai colleghi sul ramo di lavoro.
  - Se solo il repository ha versioni nuove, il progetto le prende; le modifiche salvate e non ancora pubblicate
    restano da pubblicare.
  - Se anche questo PC ha pubblicato versioni nuove, le due storie vengono integrate in una nuova versione, da
    inviare poi al repository. Se ci sono anche modifiche non pubblicate, ATLAS chiede di pubblicarle prima.
- Integrazione semantica a tre vie:
  - le schede cambiate da una sola parte prendono quella modifica;
  - le schede cambiate da entrambe le parti si integrano campo per campo; nei riferimenti ad altre schede
    (per esempio le voci tracciate) si tengono le aggiunte e le rimozioni di entrambi;
  - le impostazioni del progetto e delle verifiche si integrano voce per voce;
  - lo stesso campo cambiato in modo diverso, o una scheda eliminata da una parte e modificata dall'altra, si
    sceglie riga per riga (o tutte insieme) nella finestra di ricezione.
- Gli identificativi automatici dati qui e già usati nelle versioni ricevute (per esempio due `SF-DF06-03`)
  vengono rinumerati automaticamente, insieme a quelli che ne dipendono (le funzioni logiche della funzione
  rinumerata). La scheda ricevuta mantiene il proprio identificativo.
- Quando l'invio viene rifiutato perché il repository ha versioni non ancora ricevute, la finestra di invio
  propone «Ricevi ora».
- **Tipi di decisione architetturale (ADR, X-1)**: creando un'ADR si sceglie prima il tipo, con l'anteprima dei
  campi del suo modello; la scheda ha i campi comuni (contesto, voci SRS, opzioni, decisione, motivazione,
  conseguenze…) più la sezione «Dettagli» propria del tipo. Tipi: nuovo dominio funzionale, eliminazione di
  dominio, fusione di domini, scissione di dominio, ridefinizione dello scopo del dominio (estensione, riduzione o
  cambio totale), riallocazione di sezione o clausola, spostamento di una funzione tra domini, proprietà di
  un'informazione / confine, scelta lasciata all'implementazione, opzione di prodotto, decisione di architettura
  logica, deroga a una regola della metodologia, altro.
  - L'ADR nasce già compilata con ciò che si sa dall'elemento selezionato (es. dal dominio: dominio e missione
    attuale; dalla sezione: voce, principale e contributori attuali), con stato «Proposta».
  - Cambiando tipo, i campi del tipo precedente vengono svuotati dopo una conferma.
  - L'ADR di un **nuovo dominio funzionale** ha solo l'identificazione e i suoi dettagli: dominio proposto,
    missione proposta, perché si propone il nuovo dominio, vantaggi della proposta,
    **sezioni allocate al dominio** (scelte con le spunte, solo sezioni a tre numeri) e team proposto; niente
    relazioni, descrizione, opzioni, informazioni principali, criteri A2 o tabelle di sezioni e funzioni che
    cambiano dominio.
  - La finestra dei tipi si apre con la lista dall'inizio; senza un elemento selezionato propone il primo tipo.
  - L'ADR di **fusione di domini** ha solo l'identificazione e i dettagli: domini da fondere, nome del dominio
    risultante (l'ID sarà quello del dominio che resta, o assegnato dal tool), dominio che resta, missione
    proposta, team e le **voci SRS attribuite al dominio risultante**, calcolate dal tool come quelle dei domini
    fusi (principali o contributori) e aggiornate cambiando i domini.
  - L'ADR di **scissione di un dominio** è la duale della fusione: dominio da scindere, domini risultanti (per
    ciascuno nome, missione e team proposti, e quale mantiene l'ID del dominio scisso; gli altri ID li assegna il
    tool) e la **ripartizione delle voci SRS**: per ogni riga si sceglie una voce del dominio da scindere e uno dei
    domini risultanti scritti sopra, da elenchi che si aggiornano mentre si compila la scheda. Niente descrizione,
    opzioni o altri campi.
  - L'ADR di **ridefinizione dello scopo di un dominio** ha solo l'identificazione e i dettagli: dominio
    interessato, natura della modifica, missione attuale (letta dalla scheda del dominio), missione proposta,
    motivazione della modifica, sezioni acquisite e sezioni cedute (scelte con le spunte, solo sezioni).
  - L'ADR di **riallocazione di sezione o clausola** ha solo l'identificazione e i dettagli: la voce da
    riallocare (scelta con le spunte), il dominio principale e i contributori attuali (letti dalla voce), il
    dominio principale e i contributori proposti, la motivazione.
  - L'ADR di **spostamento di una funzione tra domini** ha solo l'identificazione e i dettagli: la funzione, il
    dominio attuale (letto dalla funzione), il dominio proposto e la motivazione dello spostamento.
  - Anche le ADR di **proprietà di un'informazione**, **scelta lasciata all'implementazione** e **opzione di
    prodotto** hanno solo l'identificazione e i dettagli, ciascuna con la propria motivazione: i produttori attuali
    dell'informazione (letti dagli scambi), il dominio principale della voce SRS (scelta con le spunte) e il dominio
    della funzione opzionale sono calcolati dal tool.
  - I tipi sono **raggruppati per ambito**: domini funzionali (SA), voci SRS, funzioni e scambi (SA), architettura
    logica (LA), generali. Nella finestra di scelta del tipo gli ambiti sono intestazioni; l'elenco X-1 ha la
    colonna «Ambito» ed è ordinato per ambito.
  - L'ADR di **eliminazione di un dominio** ha solo l'identificazione e la descrizione, con dominio interessato,
    motivazione e osservazioni della DA.
  - Nell'ADR di un nuovo dominio si indica solo il **nome**: l'ID (DFnn) lo assegna il tool all'approvazione.
  - **«Approva e crea il dominio»** (solo per i membri della Design Authority, sull'ADR proposta): dopo una
    conferma che riassume cosa cambia, crea il dominio con l'ID assegnato dal tool, la missione e il team
    proposti, lo rende dominio principale delle sezioni allocate (le sezioni che avevano un altro principale
    passano al nuovo dominio) e porta l'ADR a «Decisa», con la data e il dominio creato.
  - **Data della decisione** al posto di «Data e decisore»: la imposta il tool quando l'ADR diventa «Decisa»
    (dall'approvazione o dallo stato), resta se l'ADR viene superata, sparisce se torna «Proposta». Il decisore
    non si indica: è sempre la Design Authority. Le ADR esistenti conservano la data che avevano scritto.
  - L'elenco X-1 ha la colonna «Tipo»; le ADR delle versioni precedenti restano senza tipo, con i soli campi comuni.
- **Rami** (*Versioni › Rami…*, anche nella barra in alto, prima di «Pubblica»):
  - un elenco a scelta mostra tutti i rami, solo quelli di questo PC o solo quelli del repository;
  - elenco dei rami di questo PC e del repository, con ultima versione, autore, dove si trovano e quante versioni
    sono avanti o indietro rispetto a `main`; «Aggiorna dal repository» scarica i rami senza cambiare il progetto;
  - **nuovo ramo da una versione scelta** di qualsiasi ramo (anche dalla Cronologia, «Crea ramo da questa
    versione…»), con il nome proposto `att/<team>-…`, inviato subito al repository se richiesto;
  - **cambio di ramo**, anche verso un ramo che è solo nel repository; le modifiche non pubblicate vengono prima
    pubblicate o scartate, a scelta;
  - il ramo in uso è indicato nella barra di stato.
- **Cronologia di qualsiasi ramo**: nella Cronologia si sceglie il ramo (di questo PC o del repository); il
  dettaglio di una versione la confronta con la versione da cui deriva.
- **Pubblicazione su un nuovo ramo**: nella finestra *Pubblica* si sceglie se pubblicare sul ramo in uso o su un
  nuovo ramo, creato in quel momento dall'ultima versione del ramo in uso; il nuovo ramo diventa quello di lavoro
  e viene inviato al repository.
- **Confronto tra rami**: in *Confronta* ogni lato è un ramo e una sua versione, o lo stato attuale. I rami sono
  distinti per provenienza, «Questo PC › …» e «Repository › …», anche quando hanno lo stesso nome: si confrontano
  locale con locale, locale con remoto, remoto con remoto. All'apertura la finestra scarica i rami del repository
  (e c'è «Aggiorna dal repository»). L'opzione «Solo ciò che ha cambiato «A» dal punto di partenza comune» mostra solo le modifiche di un
  ramo da quando è nato, senza quelle entrate nel frattempo nell'altro. Dalla finestra dei rami: «Confronta con il
  mio stato attuale» e «Cosa ha cambiato rispetto a main».
- **Membri dei team** gestiti dalla scheda del team (EPBS-1) da un membro della Design Authority:
  - «Aggiungi membro…» apre la finestra del nuovo membro: nome e cognome e **ID dell'account** (obbligatori),
    e-mail, ruolo;
  - per ogni membro: modifica dei dettagli (anche con doppio clic) e rimozione;
  - la stessa persona, o lo stesso ID, non può essere aggiunta due volte allo stesso team.
- **Riconoscimento tramite l'ID dell'account**: ogni utente ha un solo ID, generato alla creazione dell'account
  locale e mostrato (con un pulsante per copiarlo) in *Utente › Modifica account*. La persona lo comunica alla DA,
  che lo inserisce aggiungendola al team: da quel momento l'account è riconosciuto come quel membro, anche se il
  nome è scritto in modo diverso.
  - La barra di stato indica i team di cui l'utente fa parte; la Design Authority è riconosciuta dall'ID.
  - Le versioni pubblicate da un membro riportano nel messaggio nome, team e ID dell'account.
- **Accesso al progetto riservato ai membri**: un progetto si apre solo se l'ID dell'account è tra i membri di un
  team. Chi non c'è vede il motivo, con il proprio ID da copiare e inviare alla Design Authority. Finché nessun
  membro ha un ID (progetto nuovo o delle versioni precedenti) il progetto si apre per tutti, per impostare i
  team. Se cambia l'utente con un progetto aperto e il nuovo utente non ne è membro, il progetto si chiude.
  Se un membro della Design Authority rimuove per errore il proprio ID (togliendo la propria riga, cambiando il
  proprio ID o eliminando il team che lo contiene), compare subito un messaggio di errore e l'ID non viene
  rimosso: altrimenti non potrebbe più aprire il progetto.
- I membri del team sono nella scheda subito dopo la sezione «Descrizione».
- **I team si modificano solo dalla Design Authority**: creazione, modifica ed eliminazione delle schede dei team
  (membri compresi) sono riservate ai membri della DA; per gli altri la scheda resta in sola lettura e il pulsante
  «Modifica» spiega perché. Finché nessun team DA ha membri, chiunque può modificare i team, per poterla
  impostare.
  Anche il «Team assegnatario» di un dominio lo cambia solo la DA: per gli altri il campo resta bloccato nella
  scheda del dominio (che per il resto si modifica come prima).
- Un **template Excel per ogni tipo di ADR** nella cartella `Templates/` (`Template_X-1.01_ADR_Nuovo_dominio_funzionale.xlsx`
  … `Template_X-1.13_ADR_Altro_decisione_trasversale.xlsx`), numerati nell'ordine degli ambiti. Hanno lo stile e
  l'intestazione del template X-1 generale e gli stessi campi della scheda del tipo in ATLAS: le tabelle (domini
  risultanti, ripartizione delle voci, produttori candidati, opzioni) con le loro colonne, gli elenchi a tendina
  per i campi a valori fissi e l'indicazione dei campi che ATLAS compila dal modello. Li scrive
  `scripts/make_adr_templates.py` a partire dallo schema, e un test verifica che restino allineati alle schede.
- Il **registro delle ADR aperte** (`Templates/Template_X-1.00_Registro_ADR_aperte.xlsx`): ID dell'ADR, breve
  descrizione, team proponente e stato, una riga per ogni ADR non ancora decisa dalla Design Authority (lo script
  dei template lo crea solo se manca, così le modifiche fatte a mano restano). Lo stesso
  elenco, già compilato dal progetto, si salva in Excel da ATLAS con «Esporta ADR aperte…» nell'elenco X-1.

### Corretto
- Su Linux ATLAS non si chiude più di colpo cambiando il tipo di un'ADR, ripristinando un controllo nelle
  impostazioni delle verifiche o eliminando un progetto dall'elenco dei recenti: la pagina che si ricostruisce
  viene distrutta dopo, non mentre il suo pulsante o la sua casella sta ancora gestendo la scelta.
- Un progetto scaricato su un PC con Git per Windows installato non risulta più sempre «modificato e non
  pubblicato»: Git per Windows imposta per tutto il sistema la conversione delle fine riga (`core.autocrlf`), che
  ATLAS applicava scaricando i file. Ora ogni progetto mantiene le fine riga delle versioni.
- All'avvio non viene più proposto il «Ripristino della sessione» dopo una chiusura normale: la copia di
  sicurezza delle modifiche, se nel frattempo erano state annullate (per esempio un elemento nuovo non salvato),
  restava e sembrava una chiusura imprevista.

### Modificato
- Il repository dello strumento è ora su GitHub (<https://github.com/salvodesi/ATLAS>), con le release di tutte
  le versioni. I test su Linux e l'archivio Linux sono compilati da GitHub Actions.
- Un elemento creato con «Nuovo…» (albero, elenchi X-1 e X-2) la cui scheda non viene mai salvata sparisce
  dal modello e dall'albero: con «Annulla», chiudendone la scheda o chiudendo il progetto. Non resta nulla da
  salvare.
- «Importa SRS…» non è più nella barra in alto: è la prima voce del menu del tasto destro su «Voci SRS»
  nell'albero del modello (e resta nel menu File).
- I membri dei team non sono più un elenco di nomi: all'apertura del progetto ogni nome diventa un membro senza
  ID, riconosciuto da nome e cognome finché la DA non ne indica l'ID dell'account.
- Gli identificativi automatici prendono il primo numero libero, anche quello lasciato da una scheda eliminata
  (prima non venivano mai riusati gli identificativi già pubblicati, e il numero era sempre l'ultimo più uno).

### Aggiornamento dalla 0.3.0
- I progetti della 0.3.0 si aprono senza interventi.
- I membri dei team scritti come nomi diventano membri senza ID dell'account, riconosciuti da nome e cognome:
  la Design Authority ne indichi l'ID dalla scheda del team. Chi non è tra i membri di un team non può aprire il
  progetto, quindi conviene che la DA completi i team prima di distribuire la nuova versione.
- Le ADR già scritte mantengono i propri dati: i campi che il loro tipo non ha più restano salvati ma non sono
  mostrati nella scheda.

## [0.3.0] - 2026-10-24

### Aggiunto

**Verifiche del modello**
- 171 controlli ricavati dalla metodologia:
  - regole D1–D10, attività A4–A6 e B1–B7;
  - checklist dei template;
  - relazioni tra campi di schede diverse.

  Sono divisi per scheda e di default nessuno è attivo.
- *Verifica modello* (F7, o il pulsante blu sotto l'albero del modello):
  - mostra l'avanzamento controllo per controllo;
  - si può interrompere;
  - resta aperta con l'esito fino a «Chiudi».
- Pannello delle segnalazioni in fondo alla finestra:
  - ridotto finché non si esegue una verifica, si può fissare aperto;
  - filtri per gravità e ricerca;
  - il doppio clic apre la scheda sul campo con il problema;
  - ogni scheda mostra in cima le proprie segnalazioni.
- Personalizzazione dei controlli in *Progetto › Impostazioni › Verifiche*:
  - **profili** di verifiche, con il profilo attivo scelto anche dalla barra in alto;
  - per ogni controllo **parametri** (soglie, formati degli ID, domini di codifica, dominio delle procedure…),
    **gravità** e **ambito** (stato e domini delle schede controllate);
  - «Ripristina valori della metodologia».
- **Eccezioni**: la Design Authority può accettare una segnalazione con una motivazione obbligatoria, registrata con
  autore e data. L'eccezione vale finché la scheda non cambia e si può revocare. Le eccezioni non sono contate negli
  errori.
- Il riepilogo delle verifiche è nella finestra *Pubblica*. Gli errori non bloccano la pubblicazione.

**Team e Design Authority**
- Un team (EPBS-1) può essere indicato come Design Authority, uno solo per progetto.
- I membri sono riconosciuti da nome e cognome dell'account e il ruolo è indicato nella barra di stato.

**Schede e modello**
- I campi collegati tra schede diverse restano allineati, per esempio dominio ↔ team e team ↔ domini.
- Editor formattato (grassetto, corsivo, elenchi) per tutti i campi di testo libero, salvato in Markdown. L'editor
  si allunga con il contenuto.
- Elenco in tabella delle richieste di chiarimento (X-2), con doppio clic sul nodo dell'albero:
  - colonne ID, destinatario e stato;
  - creazione, apertura ed eliminazione dall'elenco.
- Elenco in tabella degli ADR (X-1):
  - colonne ID, titolo, data e decisore, stato;
  - creazione ed eliminazione dall'elenco.
- Il destinatario di una CQ è la Design Authority o un team, scelto alla creazione. La clausola si sceglie a spunta.
- ADR:
  - voci SRS interessate scelte a spunta;
  - «Superata da» scelta da un elenco con ricerca;
  - sezione «Relazioni» prima di «Descrizione».

**Voci SRS**
- Il catalogo delle voci si apre anche in una finestra separata, con un pulsante o con «Apri in altra finestra» dal
  menu contestuale dell'albero.
- Azioni sulle righe:
  - le sezioni si allocano ai domini;
  - le clausole si allocano alle funzioni di sistema;
  - da una clausola si derivano uno o più requisiti (l'ID è mostrato subito, l'obbligo si scrive in un riquadro
    dedicato).

**Progetto**
- Nuovo file `checks.yaml`, versionato con il modello, con profili, profilo attivo ed eccezioni.
- Si possono pubblicare anche le sole impostazioni condivise del progetto, senza modifiche al modello.

### Modificato
- Nell'albero del modello «Attori esterni» viene prima di SA-1.
- Sotto l'albero il pulsante «Verifica modello» sostituisce «Nuovo» ed «Elimina», che restano nel menu contestuale.
- Le richieste di chiarimento del formato precedente, con il destinatario come testo, vengono convertite
  all'apertura del progetto:
  - un testo che nomina un team o la Design Authority diventa quel team;
  - un testo diverso resta come «Destinatario (testo)».
- I riferimenti alle voci SRS scritti nel testo degli ADR diventano voci SRS interessate.

### Aggiornamento dalla 0.2.0
- I progetti della 0.2.0 si aprono senza interventi.
- Le impostazioni delle verifiche delle prime versioni, se presenti in `project.yaml`, vengono lette e spostate in
  `checks.yaml` al primo salvataggio delle impostazioni.
- Dopo la pubblicazione delle verifiche con la 0.3.0, chi usa ancora la 0.2.0 non le vede: tutto il team deve
  aggiornare ATLAS.

## [0.2.0] - 2026-10-23

Prima versione pubblicata su GitLab.

### Aggiunto
- Modello ARCADIA secondo i template della metodologia:
  - System Analysis (SA-1…SA-7, attori esterni);
  - Logical Architecture (LA-1…LA-4);
  - team (EPBS-1), ADR (X-1) e richieste di chiarimento (X-2).
- Import delle voci SRS dai PDF del SUBSET-026, con testo, tabelle e figure, e lettore delle voci per capitolo.
- Registro di tracciamento (SA-3), requisiti derivati (SA-4) e finestre di tracciatura a spunta verso domini,
  funzioni di sistema e funzioni logiche.
- Versioni su repository Git remoto (HTTPS o SSH):
  - pubblicazione, download di un progetto e invio delle versioni;
  - cronologia e confronto semantico;
  - migrazione della storia tra server.
- Account locali obbligatori. Le credenziali Git sono salvate solo nel portachiavi del sistema.
- Ripristino delle modifiche non salvate e cache locale per i progetti grandi.
- Nome ATLAS (Arcadia Traceability, Logical Architecture Software), icona e logo.
- Installer Windows e archivio Linux. La pipeline GitLab esegue i test e compila la versione Linux.

[Non rilasciato]: https://github.com/salvodesi/ATLAS/compare/v0.9.3...main
[0.9.3]: https://github.com/salvodesi/ATLAS/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/salvodesi/ATLAS/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/salvodesi/ATLAS/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/salvodesi/ATLAS/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/salvodesi/ATLAS/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/salvodesi/ATLAS/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/salvodesi/ATLAS/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/salvodesi/ATLAS/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/salvodesi/ATLAS/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/salvodesi/ATLAS/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/salvodesi/ATLAS/releases/tag/v0.2.0
