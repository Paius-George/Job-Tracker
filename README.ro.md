# 🚀 LinkedIn Discord Job Alert Bot

[_English version →_](README.md)

<img width="1024" height="572" alt="image" src="https://github.com/user-attachments/assets/ac0a7cdb-dd01-4074-8c41-17460eacd5f0" />

Un bot automatizat care monitorizează continuu anunțurile noi de pe LinkedIn conform filtrelor tale personalizate și trimite alerte în timp real, sub formă de embed-uri interactive, direct pe webhook-ul tău de Discord.

---

## ✨ Funcționalități

- **Fără Autentificare / Date de Conectare**: Utilizează API-ul public de căutare guest de pe LinkedIn — fără riscuri pentru contul tău personal.
- **Filtre Personalizate Detaliate**:
  - 🔍 **Cuvinte Cheie & Domeniu**: Caută după orice titlu, stack tehnologic sau industrie.
  - 📍 **Locație & Mod de Lucru**: Remote, Hibrid sau La birou (On-site) la nivel global.
  - 🎯 **Nivel de Experiență**: Internship, Entry level, Associate, Mid-Senior etc.
  - 💼 **Tip de Contract**: Full-time, Contract, Part-time, Internship.
  - 🚫 **Filtre Negative (Excludere din Titlu & Descriere)**: Filtrează automat nivelurile de senioritate nedorite (ex. exclude *"Senior"*, *"Lead"*, *"Staff"*, *"Principal"*), cerințele stricte de autorizații sau constrângerile de viză.
  - 🏢 **Blacklist & Whitelist Companii**: Blochează agențiile de recrutare sau concentrează căutarea pe anumite companii specifice.
- **Alerte Vizuale prin Embed-uri Discord**:
  - Titlul jobului cu link direct către formularul de aplicare.
  - Numele companiei și logo-ul acesteia în miniatură.
  - Badge pentru Locație & Mod de Lucru (🌐 Remote / 🏢 On-site / 🔀 Hibrid).
  - Senioritate, tipul contractului și salariul (dacă este specificat).
  - Eticheta filtrului potrivit și timpul relativ de la publicare (*"15 minutes ago"*).
  - Menționare opțională a unui ID de Rol Discord pentru notificări push.
- **Peste 6 Surse de Joburi (strategy.md)**: LinkedIn (guest API), eJobs.ro, BestJobs.eu, Hipo.ro, StagiiPeBune.ro, plus **scraping universal pentru platformele ATS** ale companiilor (API-urile Greenhouse & Lever) dintr-o simplă listă JSON — și **Google dorking** opțional pentru pagini de carieră personalizate.
- **Roluri Junior dedicate pentru București**: Locație configurată pentru București (sau Remote), nivel de experiență setat pe Internship/Entry level și cuvinte-cheie axate pe QA Tester, IT Support, Helpdesk, Pentester & Red Team.
- **Fereastră de Noutate de 30 de Minute**: LinkedIn este interogat folosind filtrul `r1800` (ultimele 30 de minute), iar fiecare rezultat este reverificat pe baza orei exacte a postării pentru a afișa doar anunțurile proaspete.
- **Filtru de Siguranță pentru Roluri Junior/Internship**: Elimină rolurile care conțin termeni de senioritate în titlu (*Senior*, *Lead*, *Manager*, *Principal*...) sau cerințe mari de experiență precum *"5+ years"* / *"5+ ani"* în descriere — evitând rezultatele fals-pozitive (cum ar fi rolurile de seniori care doar „mentorează juniori”).
- **Deduplicare pe Mai Multe Platforme**: Unifică anunțurile publicate pe platforme diferite de către aceeași companie dacă au titluri foarte similare (fuzzy matching), astfel încât să nu primești aceeași ofertă de două ori.
- **Prevenire Inteligentă a Alertelor Duplicate**: Înregistrează fiecare job notificat într-o bază de date locală SQLite pentru a preveni duplicatele între reporniri.
- **Scraping Etic și Protecție Anti-Rate-Limit**: Alternează User-Agent-uri de browser desktop, introduce întârzieri aleatorii (jitter) și gestionează automat erorile de tip `429 Too Many Requests` de la Discord și LinkedIn.

---

## 📁 Structura Proiectului

```text
Linkedin/
├── config.yaml          # Configurația activă (filtre, căutări, intervale)
├── config.example.yaml  # Șablon de configurare de referință
├── .env                 # Variabile de mediu (DISCORD_WEBHOOK_URL)
├── main.py              # Punctul de intrare CLI (run, scan-once, test-webhook, stats, jobs)
├── requirements.txt     # Dependențele Python
├── Dockerfile           # Configurația containerului Docker
├── docker-compose.yml   # Fișier de deployment Docker Compose
├── data/
│   ├── jobs.db          # Bază de date SQLite (istoric joburi / deduplicare)
│   └── ats_companies.json # Companii țintă pentru scraping ATS (Greenhouse/Lever)
├── src/
│   ├── config.py        # Validare și parsare fișier de configurare
│   ├── database.py      # Stocare SQLite, dedup & prevenire duplicate
│   ├── tracker.py       # Motor de filtrare roluri junior & modele de status
│   ├── discord_notifier.py # Formatare embed-uri Discord și client webhook
│   ├── runner.py        # Orchestrator și daemon de planificare (scheduler)
│   ├── utils.py         # Alternare User-Agent & utilitare de formatare
│   └── scraper/
│       ├── models.py    # Dataclasses pentru JobPost & SearchProfile
│       ├── base.py      # Interfața BaseScraper + tipar registry
│       ├── linkedin.py  # Scraper API guest LinkedIn și motor de filtrare
│       ├── ejobs.py     # Scraper eJobs.ro
│       ├── bestjobs.py  # Scraper BestJobs.eu
│       ├── hipo.py      # Scraper Hipo.ro
│       ├── stagiipebune.py # Scraper pentru internship-uri StagiiPeBune.ro
│       ├── ats.py       # Scraper ATS universal pentru Greenhouse/Lever
│       └── googledork.py # Google dorking opțional pentru pagini custom de cariere
└── tests/
    └── test_bot.py      # Suită de teste unitare
