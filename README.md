# Rick — assistente vocale per videogiochi

<p align="center"><img src="Programma/assets/rick_cover.png" alt="Rick, il gatto mago / Rick, the wizard cat" width="384"></p>

<p align="center">
  <a href="https://github.com/rullintello/rick-voice-assistant/actions/workflows/tests.yml"><img src="https://github.com/rullintello/rick-voice-assistant/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <a href="https://github.com/rullintello/rick-voice-assistant/releases/latest"><img src="https://img.shields.io/github/v/release/rullintello/rick-voice-assistant" alt="release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rullintello/rick-voice-assistant" alt="license"></a>
  <a href="https://www.virustotal.com/gui/file/2a4a1288cc2b2f514c4ca0e279ed0e8a5e2f98f5bba97a956f768c0f93e5a430"><img src="https://img.shields.io/badge/VirusTotal-0%2F66%20(v1.0.0)-brightgreen" alt="VirusTotal 0/66"></a>
</p>

*[Read this in English](#rick--voice-assistant-for-video-games)*

Gratuito, open source (licenza [GPLv3](LICENSE)). Se Rick ti piace e vuoi
offrirmi un caffe (facoltativo): [ko-fi.com/rullintello](https://ko-fi.com/rullintello).

Rick e' un assistente che gira in background mentre giochi. Premi **Alt+R**
per attivare il microfono, fai la tua domanda ("come si sconfigge questo
boss?", "dove trovo la spada leggendaria?", ...) e Rick ti risponde a voce.

## Come funziona

1. Premi `Alt+R` (funziona anche se il gioco e' in primo piano) → senti un
   **bip acuto** e parte la registrazione dal microfono.
2. Premi di nuovo `Alt+R` → senti un **bip piu' grave** e la registrazione si
   ferma.
3. Rick trascrive quello che hai detto, cerca sul web (se hai configurato la
   ricerca, vedi sotto) e chiede a Google Gemini una risposta pensata per
   l'aiuto in-game, e te la legge ad alta voce.

I due bip servono a farti capire quando la registrazione parte/finisce anche
mentre il gioco e' in primo piano: se giochi in vero schermo intero
esclusivo, nessuna finestra (nemmeno quella di Rick) e' visibile sopra al
gioco, quindi restano l'unico modo per saperlo con certezza. Se invece giochi
in finestra o a schermo intero senza bordi, puoi anche vedere la finestra di
Rick.

Se Rick sta ancora parlando e vuoi interromperlo per fargli una nuova
domanda, premi di nuovo `Alt+R`: smette subito di parlare e ricomincia ad
ascoltarti (stesso bip acuto di sempre), senza dover aspettare che finisca.

Rick ricorda le ultime domande/risposte della sessione, quindi puoi dirgli
una volta sola a che gioco stai giocando e in che punto ti trovi.

## La finestra di Rick

Invece di una console nera, Rick si presenta come un libro: a sinistra i
**raccoglitori**, uno per ogni gioco per cui gli hai fatto domande; a destra
la "pagina" aperta, con la conversazione di quel raccoglitore.

- In alto a sinistra c'e' il campo **"Gioco attuale"**: scegliendo un gioco
  gia' usato dal menu a tendina ci passi subito sopra. Se invece ci scrivi un
  nome nuovo, resta solo una bozza finche' non premi **💾 Salva**: a quel
  punto il raccoglitore aperto (con tutta la sua cronologia) viene rinominato
  con quel nome. Se esiste gia' un raccoglitore con quel nome, Rick ti chiede
  prima se vuoi unire le due cronologie.
- **🆕 Nuova chat** apre una pagina vuota per iniziare una conversazione da
  zero (Rick dimentica quella di prima), senza cancellare quella che stavi
  guardando.
- **🗑️ Elimina** cancella per sempre il raccoglitore aperto (te lo chiede
  prima di conferma).
- **Cancella tutti i tuoi dati** (in basso a destra) cancella da questo PC
  tutto quello che Rick ha salvato: raccoglitori, chiavi, cache e registro
  errori. Te lo chiede prima, poi Rick si chiude (vedi "Privacy e dati").
- Cliccando su un raccoglitore nella lista a sinistra lo riapri e lo rendi
  quello attivo, per rivedere le domande passate o continuare a fargliene di
  nuove su quel gioco.
- Tutto viene salvato in automatico sul tuo PC (`~/.rick/history.json`, fuori
  dal progetto, non condiviso su GitHub): chiudi e riapri Rick quando vuoi, i
  raccoglitori restano li'.

Rick rilegge anche le risposte gia' date per quel gioco (fino a 10, le piu'
recenti) prima di risponderti di nuovo: se gli hai gia' chiesto una cosa
simile, magari in una sessione passata, puo' rispondere subito invece di
dover ricercare tutto da capo — utile anche per non doverti ripetere sul
gioco e sul punto in cui sei. Questo non vale per il raccoglitore "Senza
titolo", che puo' mescolare giochi diversi: dai un nome alla chat con
**💾 Salva** per attivarlo.

Se qualcosa va storto e Rick non parte, non essendoci una console non vedrai
un messaggio d'errore a schermo: comparira' invece un piccolo popup con
scritto dove trovare i dettagli tecnici, salvati in `~/.rick/rick.log`. Se
invece il problema arriva mentre Rick e' gia' aperto (microfono staccato,
connessione assente, Gemini sovraccarico...), lo trovi scritto nella barra in
basso della finestra: risolto il problema, premi di nuovo Alt+R per riprovare.

## Installazione e avvio (Windows, consigliato)

Richiede solo [Python](https://www.python.org/downloads/), dalla 3.10 alla
3.14 (se l'installazione te lo chiede, spunta "Add python.exe to PATH").

Fatto questo, **fai doppio click su `Run Rick.bat`**. Al primo avvio compare
un avviso con il link al sito ufficiale di Python: quando l'hai installato,
spunta "Ho scaricato e installato Python" e premi OK, e l'avviso non
comparira' piu'. Poi Rick installa da solo tutto il necessario (crea un
ambiente Python isolato dentro la cartella `Programma` e scarica le
librerie: ci mette qualche minuto, e' normale) e si avvia. Le volte
successive parte subito, senza ricontrollare niente.

Lo zip della release 1.0.0 e' stato controllato da 66 antivirus su
VirusTotal: nessuna segnalazione ([vedi il risultato](https://www.virustotal.com/gui/file/2a4a1288cc2b2f514c4ca0e279ed0e8a5e2f98f5bba97a956f768c0f93e5a430)).

Le librerie installate sono sempre le stesse versioni gia' provate con Rick
(elencate in `Programma/requirements.txt`), non l'ultima uscita del giorno:
cosi' un aggiornamento difettoso o manomesso di una libreria non arriva da
solo sul PC di chi usa Rick.

Nella cartella principale trovi solo quello che serve per usare Rick
(`Run Rick.bat`, `Settings.bat`); tutto il resto (il codice, le librerie, i
file di configurazione) e' dentro la cartella `Programma`, per non creare
confusione a chi apre la cartella per la prima volta.

Il modulo usato per lo shortcut globale (`Alt+R`) su Windows a volte richiede
di eseguire il file **come amministratore** per funzionare anche quando un
gioco e' in primo piano: tasto destro su `Run Rick.bat` → "Esegui come
amministratore" se lo shortcut non risponde.

Al primo avvio, se non hai gia' una chiave, Rick apre una finestra che ti
chiede anche la **lingua** (Italiano/English — cambia il prompt di Rick, la
voce e il riconoscimento vocale) e la chiave Gemini (con link diretto per
crearne una gratis in 30 secondi, senza carta di credito), poi ricorda
entrambe le scelte per le volte dopo — utile se passi il progetto a
qualcun altro: gli basta scegliere la sua lingua e incollare la sua chiave
alla prima apertura.

Per cambiare lingua o chiavi **dopo** la prima configurazione, fai doppio
click su `Settings.bat`: riapre la stessa finestra gia' precompilata con
quello che avevi scelto, senza doverlo rifare da zero.

Nella stessa finestra c'e' anche un campo **facoltativo** per una chiave
Tavily: se la incolli, Rick cerca davvero sul web (wiki, guide aggiornate)
prima di risponderti, invece di affidarsi solo alla sua conoscenza di base —
molto piu' preciso su oggetti rari e missioni specifiche. Se salti questo
campo, Rick funziona lo stesso, solo un po' meno preciso sui dettagli piu'
di nicchia. Le ricerche vengono anche salvate in una piccola cache locale:
se qualcuno chiede la stessa cosa una seconda volta, Rick non ricerca di
nuovo, risparmiando la quota gratuita.

## Installazione manuale (Linux/Mac, o per personalizzare)

```bash
cd Programma
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Richiede Python 3.10+ con Tkinter (su Debian/Ubuntu potrebbe servire
`sudo apt install python3-tk`, su Windows e macOS e' gia' incluso). Le
impostazioni in `.env` hanno gia' dei default gratuiti:

- **Riconoscimento vocale**: usa `faster-whisper` in locale, gratis e
  offline dopo il primo avvio (scarica il modello la prima volta).
- **Sintesi vocale**: usa `edge-tts`, gratuito e senza chiave (richiede
  connessione internet).

Su Linux `keyboard` (lo shortcut globale) legge gli eventi da `/dev/input` e
di norma serve eseguire lo script con `sudo` (oppure aggiungere il proprio
utente al gruppo `input`).

## Personalizzazione

- Cambia la scorciatoia modificando `RICK_HOTKEY` in `.env` (es. `ctrl+shift+r`).
- **Lingua**: scegli Italiano/English nella finestra al primo avvio, oppure
  imposta `RICK_LANGUAGE=it` o `=en` in `.env`. Cambia il prompt di Rick
  (risponde in quella lingua), la voce di default e la lingua suggerita al
  riconoscimento vocale.
- La voce di default e' femminile adulta (`it-IT-ElsaNeural` in italiano,
  `en-US-JennyNeural` in inglese). Le uniche due voci femminili italiane
  gratuite con `edge-tts` sono Elsa e `it-IT-IsabellaNeural` (piu'
  giovanile/da bambina) — forzane una diversa con `RICK_EDGE_VOICE` in
  `.env`.
- Il "carattere" e le istruzioni di Rick sono nel prompt di sistema in
  `Programma/rick/brain.py` (`SYSTEM_PROMPT_IT` / `SYSTEM_PROMPT_EN`),
  modificabile liberamente.
- Il carattere gotico del testo (font UnifrakturMaguntia, licenza SIL Open
  Font License in `Programma/assets/fonts/OFL.txt`) e i colori sono definiti
  in `Programma/rick/gui.py`. Su Windows il font viene caricato solo per la
  sessione di Rick (nessuna installazione): se non e' disponibile, la
  finestra usa semplicemente il carattere di default del sistema.

Le chiavi e la lingua vengono salvate in `~/.rick/config.json` (nella tua
cartella utente, fuori dal progetto): non finiscono mai su GitHub ne'
vengono condivise se mandi la cartella a qualcun altro. Per cambiarle,
cancella quel file e Rick te le richiedera' di nuovo al prossimo avvio.

## Velocizzare Rick (gratis)

Rick e' gia' ottimizzato per risposte brevi e veloci di default, ma se hai
ancora bisogno di piu' velocita', queste leve sono tutte gratuite:

- **GPU per la trascrizione**: se hai una scheda video Nvidia con CUDA/cuDNN
  installati, imposta `RICK_WHISPER_DEVICE=cuda` in `.env` — la trascrizione
  diventa molto piu' veloce a parita' di precisione. Se CUDA non e'
  installato o qualcosa non va, Rick se ne accorge da solo e torna alla CPU
  senza bloccarsi.
- **Disattiva la ricerca web**: `RICK_ENABLE_WEB_SEARCH=false` in `.env`
  toglie il tempo della chiamata a Tavily su ogni domanda nuova (le domande
  gia' fatte restano comunque veloci grazie alla cache). In cambio Rick
  risponde solo dalla sua conoscenza generale, senza guide/wiki aggiornate.
- **Modello di trascrizione piu' piccolo**: `RICK_WHISPER_MODEL_SIZE=base`
  (invece di `small`) trascrive piu' in fretta ma capisce un po' peggio —
  il contrario di `medium`, che e' piu' preciso ma piu' lento. Scegli in
  base a cosa ti serve di piu' tra i due.
- **Meno cronologia salvata nella domanda**: di default Rick rilegge le
  ultime 10 risposte date per quel gioco. `RICK_MAX_SAVED_HISTORY_ENTRIES=5`
  (o `=0` per spegnere del tutto questa memoria) rende ogni richiesta a
  Gemini un po' piu' leggera, a costo di ricordare meno le sessioni passate.

## Privacy e dati

**Rick non ha un server e non invia nessun dato allo sviluppatore.** Gira
interamente sul tuo PC: gli unici dati che escono sono quelli descritti sotto
in "Cosa va online", e vanno direttamente ai servizi che usi con le tue
chiavi.

**Cosa resta solo sul tuo PC**, nella cartella `.rick` dentro la tua
cartella utente:

- la tua **voce**: viene trascritta in locale e non viene mai mandata online.
  La registrazione esiste solo per i pochi secondi della domanda, poi viene
  cancellata (se chiudi Rick proprio in quel momento, la cancella da solo a
  un avvio successivo);
- i **raccoglitori** con la cronologia (`history.json`);
- le **chiavi API** e la lingua (`config.json`). Nella finestra delle
  impostazioni le chiavi sono nascoste da pallini, cosi' non si vedono se
  sei in live o condividi lo schermo;
- la cache delle ricerche web e il registro errori (`rick.log`, al massimo
  circa 3 MB). Rick non ci scrive ne' le chiavi ne' le tue domande.

**Cosa va online**, e solo quando fai una domanda:

- a **Google Gemini**: il testo della domanda, i messaggi precedenti della
  chat in corso e, se la chat ha il nome di un gioco, fino alle ultime 10
  risposte salvate per quel gioco;
- a **Tavily** (solo se hai messo la chiave): la domanda con il nome del
  gioco, per la ricerca web;
- al servizio vocale di **Microsoft** (edge-tts): il testo della risposta di
  Rick, per leggerla ad alta voce.

Con il piano gratuito di Gemini, Google puo' usare i contenuti che riceve per
migliorare i suoi servizi; le regole possono cambiare da paese a paese:
trovi quelle ufficiali nei [termini dell'API Gemini](https://ai.google.dev/gemini-api/terms).
Quindi **non dire a Rick dati personali** (nomi, indirizzi, password...).

L'uso di Gemini e Tavily e' regolato dai loro termini di servizio, che accetti
quando crei le chiavi, compresi eventuali requisiti come l'eta' minima:
[termini dell'API Gemini](https://ai.google.dev/gemini-api/terms) e i termini
sul sito di [Tavily](https://tavily.com).

La voce di Rick usa gratuitamente il servizio di lettura ad alta voce del
browser Microsoft Edge, tramite la libreria open source `edge-tts`. Non e' un
servizio ufficiale pensato per altri programmi: e' molto diffuso e tollerato,
ma Microsoft potrebbe cambiarlo o bloccarlo in qualsiasi momento. In quel caso
Rick smetterebbe di parlare, ma continuerebbe a scrivere le risposte nel libro.

**Per cancellare**: **🗑️ Elimina** cancella un raccoglitore; **Cancella
tutti i tuoi dati** cancella tutto quello elencato sopra, e al prossimo
avvio Rick ti chiedera' di nuovo le chiavi. Per disinstallare Rick del tutto,
premi prima quel pulsante e poi cancella la cartella di Rick. Resta solo il
modello di trascrizione scaricato la prima volta (in `.cache\huggingface`
dentro la tua cartella utente): non contiene dati tuoi, ma puoi cancellarlo
per liberare spazio.

**Attenzione: il pulsante cancella solo i dati su questo PC.** Quello che e'
gia' stato inviato a Google, Tavily e Microsoft (vedi "Cosa va online") e'
conservato e gestito da ciascuna piattaforma in modo indipendente, secondo le
sue regole sulla privacy: Rick non puo' cancellarlo. Allo stesso modo, le
tue chiavi API restano valide anche dopo averle cancellate da Rick: per
disattivarle davvero, eliminale dal sito dove le hai create
([Google AI Studio](https://aistudio.google.com/apikey),
[Tavily](https://app.tavily.com)).

## Limiti

Rick risponde basandosi sulla sua conoscenza generale dei giochi (Google
Gemini) piu', se hai configurato Tavily, sui risultati di ricerca web reali:
non legge pero' lo schermo ne' ha accesso al salvataggio di gioco, quindi per
risposte precise conviene dirgli il nome del gioco, il capitolo/area e i
dettagli utili nella domanda. I piani gratuiti di Gemini e Tavily hanno un
limite di richieste al giorno: per un uso normale da giocatore singolo non lo
raggiungerai quasi mai (e le ricerche ripetute vengono servite dalla cache
locale, non contano una seconda volta).

## Licenza e contributi

Rick e' distribuito sotto licenza [GPLv3](LICENSE): puoi usarlo, modificarlo
e ridistribuirlo liberamente, anche dentro altri progetti, a patto che
restino open source con la stessa licenza. Contributi, segnalazioni di bug
e richieste di nuove funzionalita' sono benvenuti tramite Issue/Pull Request
su GitHub.

Prima di proporre una modifica, lancia i test automatici dalla cartella
`Programma`:

```
python -m unittest discover -s tests
```

Non servono microfono, casse, chiavi o internet (sono tutti simulati). I
test della finestra hanno bisogno di uno schermo: su Linux senza schermo
lanciali con `xvfb-run -a python -m unittest discover -s tests`.

Rick resta gratuito per chiunque. Se lo usi e ti va di ringraziare, puoi
offrirmi un caffe (del tutto facoltativo) su
[ko-fi.com/rullintello](https://ko-fi.com/rullintello).

---

# Rick — voice assistant for video games

*[Leggi questo in italiano](#rick--assistente-vocale-per-videogiochi)*

Free, open source ([GPLv3](LICENSE) license). If you like Rick and want to
buy me a coffee (optional): [ko-fi.com/rullintello](https://ko-fi.com/rullintello).

Rick is an assistant that runs in the background while you play. Press
**Alt+R** to activate the microphone, ask your question ("how do I beat this
boss?", "where's the legendary sword?", ...) and Rick answers out loud.

## How it works

1. Press `Alt+R` (works even while the game is focused) → you'll hear a
   **high-pitched beep** and the microphone starts recording.
2. Press `Alt+R` again → you'll hear a **lower beep** and the recording
   stops.
3. Rick transcribes what you said, searches the web (if you've set up
   search, see below) and asks Google Gemini for an answer tailored to
   in-game help, then reads it to you out loud.

The two beeps let you know when recording starts/stops even while the game
is focused: in true exclusive fullscreen, no window (not even Rick's own) is
visible over the game, so they're the only reliable way to know. If you play
windowed or borderless fullscreen instead, you can also see Rick's window.

If Rick is still talking and you want to interrupt him with a new question,
press `Alt+R` again: he stops talking immediately and starts listening right
away (same high beep as usual), no need to wait for him to finish.

Rick remembers the last few questions/answers of the session, so you only
need to tell him once which game you're playing and where you are.

## Rick's window

Instead of a black console, Rick looks like a book: on the left, **binders**,
one per game you've asked about; on the right, the open "page" with that
binder's conversation.

- Top left is the **"Current game"** field: picking a game you've already
  used from the dropdown switches to it right away. Typing a new name
  instead is just a draft until you press **💾 Save**: that renames the open
  binder (history included) to that name. If a binder with that name
  already exists, Rick asks first whether to merge the two histories.
- **🆕 New chat** opens a blank page to start a fresh conversation (Rick
  forgets the previous one), without deleting the one you were looking at.
- **🗑️ Delete** permanently removes the open binder (asks for confirmation
  first).
- **Delete all your data** (bottom right) erases everything Rick has saved
  on this PC: binders, keys, cache and error log. It asks first, then Rick
  closes (see "Privacy and data").
- Clicking a binder in the list on the left reopens it and makes it the
  active one, to review past questions or keep asking new ones about that
  game.
- Everything is saved automatically on your PC (`~/.rick/history.json`,
  outside the project, never shared on GitHub): close and reopen Rick
  whenever you want, the binders are still there.

Rick also re-reads its own past answers for that game (up to 10, the most
recent) before answering again: if you've asked something similar before,
maybe in an earlier session, it can answer right away instead of having to
search everything from scratch - also handy so you don't have to re-explain
the game and where you are. This doesn't apply to the "Untitled" binder,
which can mix different games: name the chat with **💾 Save** to turn it on.

If something goes wrong and Rick won't start, since there's no console
you won't see an error message on screen: instead, a small popup tells you
where to find the technical details, saved to `~/.rick/rick.log`. If the
problem comes up while Rick is already open (microphone unplugged, no
connection, Gemini overloaded...), it's written in the bar at the bottom of
the window: once it's sorted, press Alt+R again to retry.

## Installation and setup (Windows, recommended)

You only need [Python](https://www.python.org/downloads/), 3.10 to 3.14
(if setup asks, check "Add python.exe to PATH").

Once that's done, **double-click `Run Rick.bat`**. On the first start a
notice shows the link to Python's official site: once it's installed, tick
"I've downloaded and installed Python" and press OK, and the notice won't
show again. Then Rick installs everything it needs on its own (creates an
isolated Python environment inside the `Programma` folder and downloads the
libraries: takes a few minutes, that's normal) and starts. After that it
starts right away, without re-checking anything.

The release 1.0.0 zip was checked by 66 antivirus engines on VirusTotal:
no detections ([see the report](https://www.virustotal.com/gui/file/2a4a1288cc2b2f514c4ca0e279ed0e8a5e2f98f5bba97a956f768c0f93e5a430)).

The libraries installed are always the same versions already tested with
Rick (listed in `Programma/requirements.txt`), not whatever came out today:
so a broken or tampered library update never reaches Rick's users on its
own.

The top-level folder only has what you actually need to use Rick
(`Run Rick.bat`, `Settings.bat`); everything else (the code, libraries,
config files) lives inside the `Programma` folder, so the folder doesn't
look confusing the first time you open it.

The library used for the global shortcut (`Alt+R`) on Windows sometimes
needs to run **as administrator** to keep working while a game is focused:
right-click `Run Rick.bat` → "Run as administrator" if the shortcut stops
responding.

On first launch, if you don't have a key yet, Rick opens a window asking for
your **language** (Italian/English — changes Rick's prompt, voice, and
speech recognition) and your Gemini key (with a direct link to create a free
one in 30 seconds, no credit card needed), then remembers both choices for
next time — handy if you're sharing the project with someone else: they just
pick their language and paste their own key the first time they open it.

To change your language or keys **after** the initial setup, double-click
`Settings.bat`: it reopens the same window pre-filled with what you chose
before, so you don't have to start from scratch.

The same window also has an **optional** field for a Tavily key: if you
paste one in, Rick actually searches the web (wikis, up-to-date guides)
before answering instead of relying only on its base knowledge — much more
accurate for rare items and specific quests. If you skip this field, Rick
still works, just a little less precise on niche details. Searches are also
cached locally: if someone asks the same thing a second time, Rick won't
search again, saving the free quota.

## Manual installation (Linux/Mac, or to customize)

```bash
cd Programma
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Requires Python 3.10+ with Tkinter (on Debian/Ubuntu you may need
`sudo apt install python3-tk`; already included on Windows and macOS). The
settings in `.env` already have free defaults:

- **Speech recognition**: uses `faster-whisper` locally, free and offline
  after the first run (it downloads the model the first time).
- **Text-to-speech**: uses `edge-tts`, free and keyless (needs an internet
  connection).

On Linux, `keyboard` (the global shortcut) reads events from `/dev/input`
and usually needs the script run with `sudo` (or add your user to the
`input` group).

## Customization

- Change the shortcut by editing `RICK_HOTKEY` in `.env` (e.g. `ctrl+shift+r`).
- **Language**: pick Italian/English in the first-run window, or set
  `RICK_LANGUAGE=it` or `=en` in `.env`. Changes Rick's prompt (answers in
  that language), the default voice, and the language hint for speech
  recognition.
- The default voice is an adult female voice (`it-IT-ElsaNeural` for
  Italian, `en-US-JennyNeural` for English). The only two free Italian
  female voices with `edge-tts` are Elsa and `it-IT-IsabellaNeural` (more
  youthful/childish) — force a different one with `RICK_EDGE_VOICE` in
  `.env`.
- Rick's "personality" and instructions live in the system prompt in
  `Programma/rick/brain.py` (`SYSTEM_PROMPT_IT` / `SYSTEM_PROMPT_EN`), free
  to edit.
- The gothic text style (UnifrakturMaguntia font, SIL Open Font License in
  `Programma/assets/fonts/OFL.txt`) and colors are defined in
  `Programma/rick/gui.py`. On Windows the font is loaded only for Rick's own
  session (no installation); if it's unavailable, the window just falls
  back to the system's default font.

Keys and language are saved in `~/.rick/config.json` (in your user folder,
outside the project): they never end up on GitHub, and they're not shared if
you send the folder to someone else. To change them, delete that file and
Rick will ask for them again next time it starts.

## Making Rick faster (free)

Rick is already tuned for short, fast answers by default, but if you still
need more speed, these levers are all free:

- **GPU for transcription**: if you have an Nvidia GPU with CUDA/cuDNN
  installed, set `RICK_WHISPER_DEVICE=cuda` in `.env` — transcription
  becomes much faster at the same accuracy. If CUDA isn't installed or
  something goes wrong, Rick notices on its own and falls back to the CPU
  without breaking.
- **Turn off web search**: `RICK_ENABLE_WEB_SEARCH=false` in `.env` removes
  the time spent calling Tavily on every new question (repeated questions
  stay fast thanks to the cache either way). In exchange, Rick answers only
  from its general knowledge, without up-to-date guides/wikis.
- **Smaller transcription model**: `RICK_WHISPER_MODEL_SIZE=base` (instead
  of `small`) transcribes faster but understands a bit worse — the opposite
  of `medium`, which is more accurate but slower. Pick whichever you need
  more.
- **Less saved history in each question**: by default Rick re-reads the last
  10 answers it gave for that game. `RICK_MAX_SAVED_HISTORY_ENTRIES=5` (or
  `=0` to turn this memory off entirely) makes every Gemini request a bit
  lighter, at the cost of remembering less from past sessions.

## Privacy and data

**Rick has no server and sends no data to its developer.** It runs entirely on
your PC: the only data that leaves it is described below in "What goes
online", and it goes straight to the services you use with your own keys.

**What stays on your PC only**, in the `.rick` folder inside your user
folder:

- your **voice**: it's transcribed locally and never sent online. The
  recording only exists for the few seconds of the question, then it's
  deleted (if you close Rick right at that moment, it's deleted on its own
  at a later start);
- the **binders** with your history (`history.json`);
- the **API keys** and language (`config.json`). In the settings window the
  keys are hidden behind dots, so they don't show if you're streaming or
  sharing your screen;
- the web search cache and the error log (`rick.log`, about 3 MB at most).
  Rick writes neither your keys nor your questions to it.

**What goes online**, and only when you ask a question:

- to **Google Gemini**: the text of your question, the earlier messages of
  the current chat and, if the chat is named after a game, up to the last
  10 answers saved for that game;
- to **Tavily** (only if you added its key): the question with the game's
  name, for the web search;
- to **Microsoft**'s speech service (edge-tts): the text of Rick's answer,
  to read it aloud.

On Gemini's free tier, Google may use the content it receives to improve its
services; the rules can differ by country: the official ones are in the
[Gemini API terms](https://ai.google.dev/gemini-api/terms). So **don't tell
Rick personal information** (names, addresses, passwords...).

Using Gemini and Tavily is governed by their terms of service, which you
accept when you create the keys, including any requirements such as a
minimum age: [Gemini API terms](https://ai.google.dev/gemini-api/terms) and
the terms on [Tavily](https://tavily.com)'s site.

Rick's voice uses, free of charge, the read-aloud service of the Microsoft
Edge browser, through the open source `edge-tts` library. It isn't an
official service meant for other programs: it's widely used and tolerated,
but Microsoft could change or block it at any time. If that happened, Rick
would stop speaking but would keep writing its answers in the book.

**To delete**: **🗑️ Delete** removes one binder; **Delete all your data**
erases everything listed above, and next time Rick will ask for your keys
again. To uninstall Rick completely, press that button first, then delete
Rick's folder. The only thing left is the transcription model downloaded the
first time (in `.cache\huggingface` inside your user folder): it holds none
of your data, but you can delete it to free up space.

**Note: the button only deletes the data on this PC.** Whatever was already
sent to Google, Tavily and Microsoft (see "What goes online") is kept and
handled by each platform independently, under its own privacy rules: Rick
can't delete it. Likewise, your API keys stay valid after you delete them
from Rick: to really disable them, delete them on the site where you created
them ([Google AI Studio](https://aistudio.google.com/apikey),
[Tavily](https://app.tavily.com)).

## Limitations

Rick answers based on its general knowledge of games (Google Gemini) plus,
if you've set up Tavily, real web search results: it doesn't read your
screen or access your save file, so for accurate answers it helps to tell it
the game's name, the chapter/area, and any useful details in your question.
Gemini's and Tavily's free plans have a daily request limit: for normal
single-player use you'll almost never hit it (and repeated searches are
served from the local cache, so they don't count a second time).

## License and contributions

Rick is distributed under the [GPLv3](LICENSE) license: you're free to use,
modify, and redistribute it, even inside other projects, as long as they
stay open source under the same license. Contributions, bug reports, and
feature requests are welcome via GitHub Issues/Pull Requests.

Before proposing a change, run the automated tests from the `Programma`
folder:

```
python -m unittest discover -s tests
```

They need no microphone, speakers, keys or internet (all of that is
simulated). The window tests need a screen: on a headless Linux machine run
them with `xvfb-run -a python -m unittest discover -s tests`.

Rick stays free for everyone. If you use it and want to say thanks, you can
buy me a coffee (entirely optional) at
[ko-fi.com/rullintello](https://ko-fi.com/rullintello).
