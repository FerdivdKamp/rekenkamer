# Data ingestion & data quality check pipeline

## Introduction
The project has two main folders

One for the analysis part which is more of a Jupyter Notebook and one for the implementation, which is a python project.

Each has its own virtual environment (`.venv`), which is intentionally ignored
by Git.

```
rekenkamer/
├── data/             # source Excel files
├── analysis/         # Jupyter-based exploration and validation
│   ├── notebooks/
│   └── src/
└── implementation/   # installable Python ingestion/quality-check project
    ├── src/
    └── tests/
```

See the README in each workspace for its setup commands.

## Architecture

The target architecture and its implementation assumptions are recorded in
[ADR 0001: Target architecture for workbook ingestion and analysis](docs/adr/0001-target-architecture.md).

## Agentic AI example: LocalForge

[LocalForge](https://github.com/FerdivdKamp/local-forge) is a separate project
that I set up as an example of applying agentic AI to software delivery. It
uses GitHub issues as the work backlog, selects issues marked ready for AI work,
and prepares an isolated coding task for a local AI coding agent. Successful
work is delivered on a branch and reviewed through a pull request; the agent
does not merge directly into the main branch.

It is not part of this pipeline's runtime architecture. Instead, it illustrates
how generative AI can be introduced with practical controls around credentials,
task state, test results, and human review.



## Original vacancy

### Wat ga je doen?
Jij gaat het fundament leggen voor de dataverwerking en bijbehorende infrastructuur binnen de Algemene Rekenkamer. De Algemene Rekenkamer doet kwalitatief en kwantitatief onderzoek naar een grote verscheidenheid aan onderwerpen die impact hebben op het functioneren en presteren van het Rijk. De data die die we hiervoor nodig hebben willen we verwerken volgens moderne principes. De oplossingen hiervoor bedenk jij samen met het ontwikkelteam, waarbij je alle vrijheid hebt om jouw eigen ideeën aan te dragen. Sterker nog, dat verwachten we van jou! Hiervoor werk je samen met stakeholders binnen en buiten de organisatie. Je bedenkt concrete plannen voor het verwerken van data die aansluiten bij onze business en applicaties, stemt deze af met collega’s en voert deze uit. Vanuit je creatieve denkvermogen kom je met oplossingen. Het liefst gebruik je bestaande (open) standaarden en oplossingen en als die niet geschikt zijn ontwikkel je zelf oplossingen. Je ontwikkelt met moderne tools van het ontwikkelteam en deployt je code via onze eigen CI/CD-straat naar onze Openshift Kubernetes infrastructuur. Toepassing van generatieve AI? Je bent een data-engineer, maar ook hier zie je kansen voor dataverwerking. Een webapplicatie bouwen voor data-uploads? Ja, voor de afwisseling pak je dat graag op. Uitleggen aan stakeholders waarom goede dataverwerking zo belangrijk is? Je bent onvermoeibaar! De komende jaren heb je de kans om als full-stack data engineer aan de dataverwerking bij de Algemene Rekenkamer te werken en alles wat daar volgens jouzelf, je collega’s en stakeholders bij komt kijken.

### Functie-eisen
* Afgeronde HBO-/WO-opleiding en aantoonbare ervaring op het gebied van computer/data science
* Minimaal 5 jaar ervaring in een soortgelijke functie
* Je hebt ervaring met het ontwerpen, ontwikkelen, bouwen, bevragen en beheren van API’s t.b.v. data-analyse en softwareapplicaties en gebruikt daarbij graag open standaarden zoals bijvoorbeeld REST-API Design rules van de Rijksoverheid.
* Je hebt ervaring met meerdere onderdelen van CI/CD op basis van GitOps. Bijvoorbeeld Git, Automated Testing, Packaging, Helm, Containers, Kubernetes en/of ArgoCD. Of vergelijkbaar!
* Je ontwikkelt in Python en TypeScript (pré) maar je laat je niet beperken door taal en tool.
Ervaring met de inzet van (generatieve) AI is een pré.
* Je gaat een inhoudelijke discussie met je collega’s niet uit de weg. Sterker nog daar geniet je van! Samen kom je tot nog een beter plan.
* Je kunt zelfstandig werken, bent analytisch sterk en kunt complexe problemen tot hun essentie terugbrengen.
* Je hebt een mening en visie over dataverwerking en draagt deze uit.
* je bent goed op de hoogte van de laatste trends en ontwikkelingen binnen je vakgebied.

### Interesse?
Mocht je interesse hebben, dan kun je solliciteren door te drukken op solliciteren en het formulier in te vullen. Je solliciteert via het uitvoeren van een technische opdracht, motivatiebrief en cv. We beoordelen je skills en probleemoplossend vermogen aan de hand van de technische opdracht en cv. Bij de eerste selectie weegt de technische opdracht (zie hieronder) het zwaarst. De vacature staat open tot deze is ingevuld. Na het beoordelen van de technische opdracht nemen we zo snel mogelijk contact met je op. Hierna volgt bij goed resultaat een gesprek.

### Technische opdracht
De Financial Audit (FA) afdeling van de Algemene Rekenkamer beoordeelt o.a. de rechtmatigheid van uitgaven en ontvangsten van de rijksoverheid. FA ontvangt hier per rijksonderdeel een overzicht van de rechtmatigheidsoverschrijdingen in één Excel per ministerie. Dit zijn in totaal 28 bestanden en deze zijn opgesteld door de interne Auditors van het rijk. FA controleert deze en vult aan waar nodig. Bij ontvangst worden deze bestanden door ons op een netwerkschijf opgeslagen. Een dashboard leest deze Excels direct in van de schijf en toont figuren en tabellen voor verdere analyses. Ook worden deze Excelbestanden gebruikt om via scripts in R figuren te generen voor zowel intern als extern gebruik.

FA heeft de wens om ook meerjarige analyses uit te voeren op deze Excelbestanden en hiervan figuren te maken. Met de Excelbestanden op de netwerkschijf is dit erg bewerkelijk. Het sjabloon van de Excels wijzigt regelmatig en er zijn veel problemen met de datakwaliteit van de Excelbestanden.

Maak een voorstel voor een software-architectuur (doelarchitectuur) met het hierboven beschreven proces en producten als uitgangspunt. Het doel is om de betrouwbaarheid van analyses te vergroten, datakwaliteit inzichtelijk te maken en meerjarige analyses eenvoudiger te maken. Lever dit op als een system architecture diagram met toelichting.
