# Work Log — UnionismNetwork

## Project intent (1–3 sentences)
- Goal:
- Data sources involved (folders/repos):
- Current “pipeline” summary:

## Conventions / rules I’m using
- people_review actions:
  - keep = First and Last Names
  - merge = First and Last Name combinations that are clearly the same person (often an incorrect character, plural, or plural)
  - drop = Words that are clearly not names, characters, multiple names joined by '&', categories of people (editors, governors, grandchildren, etc.)
  - review = First or Last Name only
- Merge key: canonical_key
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