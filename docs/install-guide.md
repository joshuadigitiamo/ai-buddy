# Guida all'installazione di AI Buddy

AI Buddy risponde alle domande sul manuale aziendale e sulle Guide tecniche di Digitiamo, sempre con la fonte e la data di revisione. Funziona dentro Claude: un connettore (il server) fornisce i contenuti e una Skill (`digitiamo-buddy`) insegna a Claude come usarli.

## Prima di iniziare

- Un account Google Digitiamo (`@digitiamo.com`): è l'unico account che può accedere.
- L'indirizzo del server: `https://<server-host>/mcp`. Il valore reale sarà noto quando verrà scelto l'hosting (Fase 4).

## claude.ai

1. Apri Customize > Connectors > Add custom connector e inserisci `https://<server-host>/mcp`.
2. Accedi con il tuo account Google Digitiamo.
3. Piani Team o Enterprise: un Owner aggiunge il connettore in Organization settings > Connectors, poi ogni collega preme Connect.
4. Skill: dalla cartella del repository esegui `cd skills && zip -r digitiamo-buddy.zip digitiamo-buddy`, poi carica `digitiamo-buddy.zip` in Customize > Skills.

## Claude Desktop

Usa lo stesso account e gli stessi connettori di claude.ai: aggiungi il connettore e carica la Skill come sopra. I server remoti non si configurano nel file locale `claude_desktop_config.json`.

## Claude Code

1. Aggiungi il server:

   ```bash
   claude mcp add --transport http digitiamo-buddy https://<server-host>/mcp
   ```

2. Scrivi `/mcp` in Claude Code e accedi con Google.
3. Copia la Skill: la cartella `skills/digitiamo-buddy` va in `~/.claude/skills/digitiamo-buddy/`.

## Verifica

Chiedi: "come si richiedono le ferie?". La risposta deve contenere Fonte e Data di revisione, oppure "Non lo so, chiedi a ...". Se Claude risponde senza fonte, la Skill non è attiva: ricontrolla l'installazione.

## Cosa aspettarsi

Per questioni personali (stipendio, salute, contratto, conflitti) AI Buddy indica solo la regola generale scritta nel manuale e ti rimanda al ruolo giusto, di solito HR.
