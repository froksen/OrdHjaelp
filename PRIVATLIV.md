# Privatlivspolitik for Ordhjælp

*Senest ændret: 27. november 2026*

Ordhjælp er en dansk læse- og skrivehjælp til elever. Programmet kører på elevens egen
computer. **Ordhjælp indsamler ingen oplysninger og sender ingen tekst, lyd eller
oplysninger om brugeren nogen steder hen.** Der er ingen konto, ingen statistik, ingen
reklamer og ingen sporing.

## Det, Ordhjælp bruger på computeren

| Hvad | Hvorfor | Gemmes? |
|---|---|---|
| **Markeret tekst og tekst på skærmen** | For at læse den op, når eleven beder om det | Nej |
| **Mikrofonen** | Diktering: kun mens eleven har trykket på mikrofonen. Talen bliver til tekst på computeren | Nej. Lyden slettes, så snart den er skrevet |
| **Tastaturet** (kun når *ordforslag* eller *læs mens du skriver* er slået til) | For at se det ord, der skrives, og vise forslag eller læse det op | Kun ord, eleven bruger, huskes i en ordliste på computeren (`egne_ord.json`), så de foreslås oftere |
| **Indstillinger** | Elevens valg | Ja, i en fil på computeren (`config.toml`) |
| **Logfil** | Til fejlfinding. Den indeholder ikke elevens tekst | Ja, på computeren (`ordhjaelp.log`, højst ca. 2 MB) |

Alt ligger i Ordhjælps egen mappe på computeren (på Windows under `%LOCALAPPDATA%`). Det
slettes, når Ordhjælp afinstalleres fra Microsoft Store. Ordlisten med elevens ord kan
også slettes ved at slette filen `egne_ord.json`.

## Det, Ordhjælp henter fra internettet

Ordhjælp går kun på internettet for at hente sprogmodeller (stemmen og
talegenkendelsen). Det sker første gang, eller når eleven henter flere under
*Indstillinger → Sprogmodeller*. De hentes fra [Hugging Face](https://huggingface.co).
Hugging Face kan se computerens IP-adresse, som ved alle andre downloads, men Ordhjælp
sender ingen oplysninger om eleven med. Bagefter virker Ordhjælp uden internet.

## Børn

Ordhjælp er lavet til elever, også børn. Da Ordhjælp ikke indsamler eller deler
oplysninger, gælder det samme for børn som for voksne.

## Kontakt

Spørgsmål om privatliv kan stilles på
[github.com/froksen/OrdHjaelp/issues](https://github.com/froksen/OrdHjaelp/issues).

---

# Privacy policy for Ordhjælp (English)

Ordhjælp is a Danish reading and writing aid for students. It runs entirely on the
user's computer. **Ordhjælp does not collect any data and does not send any text, audio
or information about the user anywhere.** There is no account, no analytics, no ads and
no tracking.

- **Selected text and text on the screen** are read aloud on request and not stored.
- **The microphone** is used only while the student has started dictation. Speech is
  transcribed on the computer and the audio is discarded.
- **The keyboard** is observed only when *word suggestions* or *read while typing* is
  turned on (off by default in the Microsoft Store version), to see the word being
  typed. Only words the student uses are remembered in a local word list
  (`egne_ord.json`) to improve suggestions. Keystrokes are never stored or sent.
- **Settings and a log file** (which does not contain the student's text) are stored
  locally and removed when the app is uninstalled.
- **Network:** Ordhjælp only downloads language models (voice and speech recognition)
  from [Hugging Face](https://huggingface.co), the first time or when the user asks.
  No information about the user is sent.

Questions: [github.com/froksen/OrdHjaelp/issues](https://github.com/froksen/OrdHjaelp/issues).
