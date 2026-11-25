# The Comeback Equation 🏀

Interactive analysis of NCAA women’s basketball comebacks, based on ESPN/SportsDataverse-derived women's college basketball data for seasons 2006–2026. Built for Purdue's Love Data Challenge.

## Features
- Observed win-rate heatmap by deficit size and time remaining
- Searchable game explorer with score timelines and key moments
- Historical 10+ point comeback frequencies
- Transparent methodology and limitations

## Run locally
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Data included
Only aggregated statistics, a reduced game metadata table, and 38 selected preliminary-validated game timelines are included; the raw multi-gigabyte input files are intentionally excluded.

## Methodological notes
51,814 of 54,925 play-by-play games passed the preliminary consistency rules; 5,401 contained an eventual winner that overcame a recorded 10+ point deficit. Win-rate percentages are historical conditional observations, not a live predictor. Data coverage differs by season. Automated validation checks do not establish that every record is complete or historically correct.

## Source
Purdue Love Data Week: https://www.purdue.edu/idata/lovedata/
SportsDataverse wehoop WBB, ESPN-derived data; see the competition's official dataset and data dictionary for source details.
