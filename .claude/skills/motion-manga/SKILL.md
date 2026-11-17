---
name: motion-manga
description: Stile e procedura di MangaAnimeted per trasformare tavole manga in video "motion manga" (vignette animate, camera, clip AI, musica/SFX o audio dell'episodio). Usala ogni volta che si crea, modifica o corregge un video da tavole manga, si scrive una regia in regie/, o si tocca engine/.
---

# Motion manga: stile della casa

Ogni video si fa con **un file di regia** (`regie/<nome>.yaml`) letto dal **motore unico** (`engine/`).
Non scrivere un nuovo script per ogni manga: se manca una funzione, aggiungila al motore e a `engine/stile.yaml`.

## Procedura

1. **Tavole.** Metti le pagine in `demo/<serie>/pages/NN.png|jpg` (cartella ignorata da git). Ricava i box delle
   vignette con `python demo/panels.py demo/<serie>/pages/*.png`: controlla i `.boxes.jpg` e correggi a mano i box
   sbagliati. Ordine di lettura giapponese: righe dall'alto in basso, nella riga da destra a sinistra.
2. **Regia.** Copia `regie/deathnote_t01-02.yaml` e compila una riga per vignetta: `tavola`, `box`, `tag`, `dur`,
   `nota` (cosa succede o cosa si dice). Metti solo i valori che si discostano dal tag; il resto viene dallo stile.
3. **Audio.** Una delle due:
   - `sorgente` + `da`/`a`: audio originale dell'episodio, preso in un pezzo unico (mai tagliare dentro la musica).
     Le durate delle vignette seguono le battute: misurale sull'audio (Whisper per i tempi delle parole).
   - `musica` + `sfx_dir`: musica di sottofondo + effetti per tag (vedi `sfx.per_tag` nello stile).
4. **Controllo veloce.** `python -m engine info regie/x.yaml` (scaletta) e `python -m engine provini regie/x.yaml`
   (un fotogramma per inquadratura in un'immagine sola). Guarda i provini **prima** di renderizzare.
5. **Render.** `python -m engine render regie/x.yaml`. Va a spezzoni (uno per inquadratura) in parallelo e li tiene
   in cache in `demo/output/.spezzoni/`: dopo una correzione si rifanno solo gli spezzoni cambiati.
   `--rifai 3,7` forza il rifacimento di inquadrature precise.
6. **Revisione.** `python -m engine anteprima regie/x.yaml` e apri http://127.0.0.1:8765 (solo sullo stesso PC;
   per telefono o per mandarla: `--file` crea un unico HTML, note nel browser + bottone "Copia note"): la regia si vede subito
   nel browser (stessa camera del motore, senza grana), si mette in pausa e si scrivono note (tasto N).
   Le note finiscono in `regie/<nome>.note.md` come `- [ ] minuto #inquadratura testo`. Leggile, correggi la regia
   e spunta `[x]` le note risolte: la pagina si aggiorna da sola. Renderizza solo quando l'anteprima va bene.
   Se cambi la camera in `engine/motore.py`, cambia uguale `engine/anteprima.html` (le due devono coincidere).
   **Se la stessa nota torna in due video diversi, correggi lo stile (`engine/stile.yaml` o il motore) e aggiungi
   una riga in "Errori gia' risolti" qui sotto**: non correggere solo il video.

## Regole di stile (in numeri: mai "rendilo cinematografico")

| Cosa | Regola |
|---|---|
| Formato | 1280x720, 30 fps, crf 21 |
| Durata minima di una vignetta | 1,2 s (sotto non si legge) |
| Spinta lenta standard | zoom 1,00 -> 1,06 nell'arco della vignetta, con curva morbida (smoothstep) |
| Reazione muta (`listen`) | zoom indietro 1,04 -> 1,00, 1,4-2,6 s |
| Tensione (`tense`) | 1,00 -> 1,10 |
| Buio / chiusura (`dark`) | 1,00 -> 1,12, 4-4,5 s |
| Colpo (`hit` / `big`) | 1,00 -> 1,18, scossa 18 / 26 px che si spegne in 0,6 s, flash negativo 0,06 s + lampo 0,08 s |
| Corsa (`run`) | zoom fisso 1,12, panoramica da destra a sinistra |
| Vignetta alta | panoramica dall'alto in basso (pan `auto`) |
| Vignetta larga (L/A > 1,45) | riempie lo schermo; sotto quella soglia sta al 92% x 94% su sfondo sfocato al 25% |
| Stacchi | taglio netto di default; dissolvenza 0,2 s solo dove la scena prosegue (`entrata: dissolvenza`) |
| Apertura / chiusura | 0,6 s da nero / 1,2 s a nero |
| Finitura | vignettatura forza 0,55, tinta fredda RGB 0,93/0,97/1,0, grana 3 livelli |
| Clip AI | lette a 16 fps, andata e ritorno (loop senza scatti), ridimensionate esattamente sul box della vignetta |
| Effetti sonori | volume massimo 0,8, musica 0,6, limiter a 0,95. Pochi e diversi tra loro: effetti forti e tutti uguali fanno subito "video fatto con l'IA" |
| Testo | niente sottotitoli: i testi sono gia' nei balloon |

## Tag disponibili

`calm`, `listen`, `dialog`, `tense`, `dark`, `hit`, `big`, `run`, `title`, `final`. I valori stanno in
`engine/stile.yaml`. Un nuovo tag si aggiunge li', non nella regia.

## Risparmio

- 2D e 2.5D, non 3D: meno token, meno errori di continuita'.
- Una sessione nuova per ogni video: la regia e questa skill portano avanti cio' che serve.
- Controlla sui provini, non renderizzando di continuo.

## Errori gia' risolti

Ogni riga e' un errore visto in revisione e ora impedito dallo stile o dal motore.

- Musica dell'episodio tagliata a meta' frase: l'audio sorgente si prende sempre in un pezzo unico, le vignette
  finali senza dialogo vanno su una coda di silenzio con dissolvenza (motore: `audio.sorgente`).
- Clip AI che "saltano" a fine loop: le clip si leggono avanti e indietro.
- Vignette piccole su fondo nero piatto: sfondo con la vignetta stessa sfocata e scurita.
- Zoom che mostra il bianco oltre il bordo della vignetta: la camera non esce mai dai bordi quando l'immagine e' piu'
  grande dello schermo.
