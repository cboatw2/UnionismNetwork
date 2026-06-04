# Work Log — UnionismNetwork

## Project intent (1–3 sentences)
- Goal: Create a temporal social network that is geographically grounded. The network will show coalescence and fracture between prominant South Carolina Unionists over socio-political issues from 1828-1860.

- Data sources involved (folders/repos): Benjamin Franklin Perry Letters; James Louis Petigru Letters and Speeches; various secondary sources

- Current “pipeline” summary: The Perry and Petigru letters were split and loaded from their digitized/transcribed sources. NER was run to identify person and location entities. People were loaded into respective CSVs and manaully reviewed. People were then loaded into the UnionismNetwork db.

## Conventions / rules I’m using
- people_review actions:
  - keep = First and Last Names
  - merge = First and Last Name combinations that are clearly the same person (often an incorrect character, plural, or plural)
  - drop = Words that are clearly not names, characters, multiple names joined by '&', categories of people (editors, governors, grandchildren, etc.)
  - review = First or Last Name only
- Merge key: canonical_key and person id
- Only keep/merge load into DB: yes/no

---
## 2026-05-03
### What I changed
- Combined UnionismNetwork, PerryLetters and Petigru folders into a single workspace

### Why / decision notes
- I was having difficulty with Copilot due to toggling back and forth between UnionismNetwork and PerryLetters. I needed to get the people the db in PerryLetters into UnionismNetwork.

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced: people_review.csv, unionism_aliases_staging.csv, unionism_people_staging.csv; I copied people_review.csv and created people_review_edited.csv per Copilot's suggestion to preserve the original file

### Checks / results
- Row counts:
- Any errors:

### Next
- Manual correction of people_review.csv

## 2026-06-01
### What I changed
- Restructured Petigru NER results into staging csv

### Why / decision notes
- Matched review process utitlized with Perry NER results; Petigru entities had a lot of junk compared to Perry in network

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced: petigru_ner_review.csv

### Checks / results
- Row counts:
- Any errors:

### Next
- Reevaluate current state of project and determine next steps

## YYYY-MM-DD
### What I changed
- 

### Why / decision notes
- 

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced:

### Checks / results
- Row counts:
- Any errors:

### Next
- 

## YYYY-MM-DD
### What I changed
- 

### Why / decision notes
- 

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced:

### Checks / results
- Row counts:
- Any errors:

### Next
- 