# The search space

Every competition at which elite senior individual track races have been run, from the first
modern Olympics to today, every edition of each, the races run at it, and which of them Splits
holds: the denominator for "how much of what could exist do we have?". Researched on
2026-10-01.

A **series** is a family of competitions (the Olympic Games, the Diamond League, the US
championships); an **edition** is one competition in it (a Games, a meeting in a season); a
**race** is one heat, semi-final or final of one individual track event at an edition. Relays,
walks, combined events, road, cross country, field events and age-group, masters and para races
are outside the search space; series holding only those are listed as out of scope so the
boundary is visible.

## Files

| File | What it holds |
|---|---|
| `series.yaml` | 363 series: kind, setting, scope tier, years, frequency, predecessors and successors, sources |
| `sources.yaml` | Who has published split times, for which competitions, in which years, at what granularity and access |
| `availability.yaml` | Per elite series, era by era: whether per-runner splits were published, for which events and rounds, and where |
| `meetings.yaml` | 562 one-day meeting lineages, the circuits each belonged to, and how many all-time-list performances each hosted |
| `editions.csv` | Every edition found, with dates, place, World Athletics id and where it came from |
| `races.csv` | Races per edition, event and round, with how many Splits holds and where the count came from |
| `research/` | The edition and meeting-lineage research as it was returned, with the checker's corrections marked, and every Diamond League race analysis found from 2016 (`diamond-league-analyses.csv`) |
| `tools/` | The code that harvests, assembles and reports |

## Scope tiers

- **elite-core**: the top of the sport in its era: the Olympic Games, the World Championships
  and World Indoors, the World Cup, the circuit finals, the top one-day circuit of each era
  (the classic invitationals before 1985, the IAAF Grand Prix, the Golden League and Super Grand
  Prix, the Diamond League), the World Indoor Tour and the strongest pro leagues.
- **elite-secondary**: continental championships and games, the Commonwealth Games,
  second-tier circuits (Grand Prix II, permit meetings, World Challenge, Continental Tour Gold),
  national championships and trials whose fields are world class (USA, Jamaica, Kenya,
  Ethiopia, and the USSR, GDR and Russia in their time), the NCAA, the major relay carnivals and
  international matches.
- **sub-elite**: other national championships, lower circuit tiers, regional and student
  games, and World Athletics' ordinary meetings (ranking categories B to F).

## The elite one-day circuit through time

| Years | Circuit | Final |
|---|---|---|
| 1920s–1984 | Independent invitational meetings (Bislett, Weltklasse, DN-Galan, ISTAF, the US indoor circuit and European indoor meetings); IAAF Golden Events 1978–82 | — |
| 1985–2009 | IAAF Grand Prix (Mobil Grand Prix), with Grand Prix II (1994–2005) and permit meetings below it | Grand Prix Final 1985–2002 |
| 1993–1997 | Golden Four (Oslo, Zürich, Brussels, Berlin) within the Grand Prix | |
| 1998–2009 | IAAF Golden League above the Grand Prix; Super Grand Prix 2003–09 | World Athletics Final 2003–09 |
| 2010– | Diamond League; World Challenge 2010–19, then Continental Tour Gold from 2020 | Diamond League final(s) |
| 2016– | World Indoor Tour (indoor permit meetings 1997–2015 before it) | |

## How the numbers are made

- **World Athletics' calendar** (complete from 2018; before that the global championships, the
  European championships from 1934, the World Cup from 1998, the World Athletics Final and the
  Diamond League from 2010) is the spine: every heat of every individual track event at 5,575
  competitions is counted from its results. At one-day meetings, races in sections such as
  "National Events" or "Pre-Programme" are undercard when at least 80% of the field is from the
  host country, as in the catalog; youth, school and demonstration sections are always undercard.
  Undercard races are counted separately and are not in the totals.
- **Olympedia** gives every round and heat of the Olympic Games before 1996 (checked against
  World Athletics for 1996 and 2000: identical).
- **Research** fills what World Athletics does not hold: each elite series' editions, the
  events held and, where the sources give them, the heats per round; one-day meetings count one
  race per event. Each list comes from one researcher with a confidence per edition and a
  source URL; independent verification was planned but not run (see Known gaps).
- An edition whose events are known but whose rounds are not counts its **events** but no
  races; the tables show both.
- **Held** races are Splits' own, matched to editions through their World Athletics entries.
- **Published** races are those in a series, year, discipline and round for which the
  availability research found per-runner splits, publicly or on the Wayback Machine, plus every
  race Splits holds (it was read from a published document). Leader-only intermediate times do
  not count. Where the research listed every document that survives (the Diamond League from
  2016, in `research/diamond-league-analyses.csv`, each matched to a World Athletics race by its
  field), only the races those documents report count as published.

<!-- report -->
## Headline

Across the elite series (core and secondary) the survey counts **38,233 individual track races** whose number is known, at 3,496 editions. Splits holds **2,343 (6.1%)**. Of the 3,753 races whose per-runner splits are known to have been published, it holds 2,343 (62.4%).

## By scope

| Scope | Series | Editions | Events | Events held | With race counts | Races | Held | Share | Published | Published, not held |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| elite-core | 23 | 1,285 | 9,778 | 1,255 | 934 | 19,224 | 2,153 | 11.2% | 2,415 | 262 |
| elite-secondary | 71 | 2,211 | 24,131 | 59 | 663 | 19,009 | 190 | 1.0% | 1,338 | 1,148 |
| sub-elite | 100 | 3,878 | 40,485 | 0 | 3,795 | 99,092 | 0 | 0.0% | 0 | 0 |

## Elite-core series

| Series | Years | Editions | Events | Events held | With race counts | Races | Held | Share | Published | Published, not held |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Olympic Games (athletics) | 1896–2024 | 30 | 423 | 157 | 30 | 4,078 | 407 | 10.0% | 433 | 26 |
| IAAF (Mobil) Grand Prix | 1985–2009 | 425 | 3,175 | 0 | 374 | 3,707 | 0 | 0.0% | 56 | 56 |
| World Athletics Championships | 1983–2025 | 20 | 390 | 84 | 20 | 3,193 | 547 | 17.1% | 580 | 33 |
| Wanda Diamond League | 2010–2026 | 231 | 2,793 | 976 | 231 | 3,102 | 1,045 | 33.7% | 1,110 | 65 |
| World Athletics Indoor Championships | 1985–2026 | 22 | 286 | 25 | 22 | 1,837 | 125 | 6.8% | 143 | 18 |
| World Athletics Indoor Tour Gold | 2016–2026 | 71 | 683 | 0 | 71 | 1,003 | 0 | 0.0% | 0 | 0 |
| IAAF Golden League | 1998–2009 | 76 | 828 | 0 | 76 | 890 | 0 | 0.0% | 0 | 0 |
| IAAF Super Grand Prix | 2003–2009 | 44 | 355 | 0 | 31 | 362 | 0 | 0.0% | 0 | 0 |
| IAAF World Cup / Continental Cup | 1977–2018 | 13 | 245 | 1 | 13 | 245 | 1 | 0.4% | 1 | 0 |
| IAAF Grand Prix Final | 1985–2002 | 18 | 172 | 0 | 18 | 179 | 0 | 0.0% | 0 | 0 |
| IAAF World Athletics Final | 2003–2009 | 7 | 138 | 0 | 7 | 139 | 0 | 0.0% | 0 | 0 |
| Goodwill Games | 1986–2001 | 5 | 99 | 0 | 5 | 112 | 0 | 0.0% | 0 | 0 |
| Women's World Games | 1922–1934 | 4 | 20 | 0 | 4 | 104 | 0 | 0.0% | 0 | 0 |
| Grand Slam Track | 2025–2025 | 3 | 52 | 0 | 3 | 70 | 0 | 0.0% | 64 | 64 |
| IAAF Indoor Permit Meetings | 1997–2015 | 200 | 70 | 0 | 15 | 70 | 0 | 0.0% | 0 | 0 |
| World Athletics Ultimate Championship | 2026–2026 | 1 | 16 | 12 | 1 | 40 | 28 | 70.0% | 28 | 0 |
| Friendship Games 1984 (Druzhba-84) | 1984–1984 | 2 | 15 | 0 | 2 | 36 | 0 | 0.0% | 0 | 0 |
| 1906 Intercalated Games (Athens) | 1906–1906 | 1 | 5 | 0 | 1 | 35 | 0 | 0.0% | 0 | 0 |
| IAAF Golden Events (Golden Mile etc.) | 1978–1982 | 12 | 11 | 0 | 9 | 11 | 0 | 0.0% | 0 | 0 |
| IAAF World Championships 1976 (Malmo) and 1980 (Sittard) | 1976–1980 | 2 | 2 | 0 | 1 | 11 | 0 | 0.0% | 0 | 0 |
| European indoor invitational meetings (pre-permit era) | 1981–1996 | 19 | 0 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Classic international invitational meetings before the IAAF Grand Prix | 1921–1984 | 78 | 0 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| US/Canadian winter indoor invitational circuit (to 1996) | 1996–1996 | 1 | 0 | 0 | 0 | 0 | 0 | – | 0 | 0 |

## Elite-secondary series

| Series | Years | Editions | Events | Events held | With race counts | Races | Held | Share | Published | Published, not held |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| European Athletics Championships | 1934–2026 | 28 | 467 | 14 | 28 | 2,491 | 59 | 2.4% | 248 | 189 |
| European Athletics Indoor Championships | 1966–2025 | 42 | 515 | 0 | 38 | 2,485 | 0 | 0.0% | 48 | 48 |
| Commonwealth Games (athletics) | 1930–2026 | 23 | 384 | 20 | 23 | 1,957 | 105 | 5.4% | 134 | 29 |
| World Athletics Continental Tour Gold | 2020–2026 | 77 | 925 | 25 | 77 | 1,094 | 26 | 2.4% | 26 | 0 |
| Russian Indoor Championships | 1992–2026 | 35 | 498 | 0 | 9 | 887 | 0 | 0.0% | 0 | 0 |
| Russian Championships | 1908–2026 | 46 | 706 | 0 | 11 | 873 | 0 | 0.0% | 0 | 0 |
| USA Outdoor Championships (AAU / TAC / USATF) | 1876–2026 | 184 | 2,649 | 0 | 10 | 789 | 0 | 0.0% | 268 | 268 |
| Kenyan Athletics Championships | 2018–2026 | 8 | 148 | 0 | 8 | 628 | 0 | 0.0% | 0 | 0 |
| Drake Relays | 2018–2026 | 8 | 160 | 0 | 8 | 534 | 0 | 0.0% | 0 | 0 |
| Jamaican National Senior Championships / Trials | 2018–2026 | 8 | 116 | 0 | 8 | 519 | 0 | 0.0% | 0 | 0 |
| NCAA Division I Outdoor Championships | 1921–2026 | 104 | 1,408 | 0 | 8 | 512 | 0 | 0.0% | 192 | 192 |
| Millrose Games | 1908–2020 | 98 | 489 | 0 | 95 | 498 | 0 | 0.0% | 44 | 44 |
| NCAA Division I Indoor Championships | 1965–2026 | 61 | 850 | 0 | 8 | 416 | 0 | 0.0% | 224 | 224 |
| IAAF Grand Prix II | 1994–2002 | 54 | 372 | 0 | 38 | 372 | 0 | 0.0% | 0 | 0 |
| African Athletics Championships | 1979–2026 | 24 | 463 | 0 | 4 | 371 | 0 | 0.0% | 0 | 0 |
| European Athletics Team Championships (top division) | 2009–2025 | 11 | 216 | 0 | 11 | 359 | 0 | 0.0% | 0 | 0 |
| Asian Games (athletics) | 1951–2026 | 25 | 431 | 0 | 8 | 344 | 0 | 0.0% | 0 | 0 |
| USA Indoor Championships (AAU / TAC / USATF) | 1906–2026 | 136 | 1,337 | 0 | 8 | 322 | 0 | 0.0% | 125 | 125 |
| International Track Association (ITA) pro tour | 1973–1976 | 50 | 290 | 0 | 50 | 307 | 0 | 0.0% | 0 | 0 |
| IAAF outdoor permit meetings (GP era) | 1985–2002 | 164 | 222 | 0 | 47 | 242 | 0 | 0.0% | 0 | 0 |
| Mt. SAC Relays | 2023–2026 | 4 | 47 | 0 | 2 | 240 | 0 | 0.0% | 0 | 0 |
| Penn Relays | 2018–2025 | 6 | 104 | 0 | 5 | 222 | 0 | 0.0% | 13 | 13 |
| Asian Athletics Championships | 1973–2025 | 25 | 478 | 0 | 3 | 212 | 0 | 0.0% | 0 | 0 |
| African Games (athletics) | 1965–2024 | 13 | 220 | 0 | 3 | 196 | 0 | 0.0% | 0 | 0 |
| IAAF World Challenge | 2010–2019 | 121 | 171 | 0 | 17 | 191 | 0 | 0.0% | 0 | 0 |
| City-centre street athletics meetings | 2009–2025 | 28 | 182 | 0 | 28 | 189 | 0 | 0.0% | 0 | 0 |
| Finnkampen (Finland-Sweden international) | 1925–2026 | 96 | 1,695 | 0 | 9 | 176 | 0 | 0.0% | 2 | 2 |
| South American Championships in Athletics | 1918–2025 | 63 | 930 | 0 | 4 | 156 | 0 | 0.0% | 0 | 0 |
| Pacific Conference Games | 1969–1985 | 5 | 85 | 0 | 5 | 145 | 0 | 0.0% | 0 | 0 |
| Asian Indoor Athletics Championships | 2004–2026 | 11 | 134 | 0 | 4 | 135 | 0 | 0.0% | 0 | 0 |
| NACAC Championships | 2007–2025 | 5 | 99 | 0 | 3 | 128 | 0 | 0.0% | 2 | 2 |
| Oceania Athletics Championships | 1990–2026 | 18 | 295 | 0 | 4 | 125 | 0 | 0.0% | 0 | 0 |
| American Track League | 2021–2022 | 6 | 62 | 0 | 6 | 114 | 0 | 0.0% | 12 | 12 |
| Olympic stadium test events and pre-Olympic meets | 1965–2024 | 8 | 97 | 0 | 3 | 112 | 0 | 0.0% | 0 | 0 |
| Pan American Games (athletics) | 1951–2023 | 19 | 327 | 0 | 2 | 94 | 0 | 0.0% | 0 | 0 |
| South American Indoor Championships | 2020–2026 | 5 | 62 | 0 | 5 | 93 | 0 | 0.0% | 0 | 0 |
| European 10,000m Cup | 1997–2026 | 28 | 56 | 0 | 28 | 84 | 0 | 0.0% | 0 | 0 |
| USA-USSR Dual Meet | 1958–1985 | 26 | 371 | 0 | 7 | 68 | 0 | 0.0% | 0 | 0 |
| National Games of China (PRC) | 1959–2025 | 15 | 280 | 0 | 1 | 59 | 0 | 0.0% | 0 | 0 |
| Pan American Athletics Championships | 2026–2026 | 1 | 20 | 0 | 1 | 46 | 0 | 0.0% | 0 | 0 |
| Inter-Allied Games (1919) | 1919–1919 | 1 | 7 | 0 | 1 | 41 | 0 | 0.0% | 0 | 0 |
| Kenyan national trials | 2024–2024 | 1 | 18 | 0 | 1 | 34 | 0 | 0.0% | 0 | 0 |
| Olympics of Grace, Florence 1931 | 1931–1931 | 1 | 4 | 0 | 1 | 24 | 0 | 0.0% | 0 | 0 |
| wa-meeting-a | 2022–2025 | 3 | 9 | 0 | 3 | 20 | 0 | 0.0% | 0 | 0 |
| Athlos | 2024–2026 | 3 | 18 | 0 | 3 | 18 | 0 | 0.0% | 0 | 0 |
| The Match Europe v USA | 2019–2019 | 1 | 18 | 0 | 1 | 18 | 0 | 0.0% | 0 | 0 |
| Women's Olympiads (Monte Carlo) and 1924 London Women's Games | 1921–1924 | 4 | 16 | 0 | 4 | 16 | 0 | 0.0% | 0 | 0 |
| Athletics World Cup (London 2018) | 2018–2018 | 1 | 14 | 0 | 1 | 14 | 0 | 0.0% | 0 | 0 |
| Liberty Bell Classic (1980) | 1980–1980 | 1 | 14 | 0 | 1 | 14 | 0 | 0.0% | 0 | 0 |
| Ethiopian selection trials (Hengelo, Nerja etc.) | 2023–2024 | 2 | 10 | 0 | 2 | 11 | 0 | 0.0% | 0 | 0 |
| Festival of Empire Inter-Empire Championships 1911 | 1911–1911 | 1 | 5 | 0 | 1 | 5 | 0 | 0.0% | 0 | 0 |
| Stand-alone exhibition and record-attempt events | 2020–2025 | 2 | 3 | 0 | 2 | 3 | 0 | 0.0% | 0 | 0 |
| Enhanced Games | 2026–2026 | 1 | 2 | 0 | 1 | 2 | 0 | 0.0% | 0 | 0 |
| AAA Championships | 1880–2006 | 117 | 1,172 | 0 | 1 | 1 | 0 | 0.0% | 0 | 0 |
| USATF Golden Spike Tour / Visa Championship Series | 1999–2012 | 100 | 467 | 0 | 1 | 1 | 0 | 0.0% | 0 | 0 |
| Soviet Championships | 1920–1990 | 54 | 729 | 0 | 1 | 1 | 0 | 0.0% | 0 | 0 |
| Soviet Indoor Championships | 1971–1991 | 21 | 241 | 0 | 1 | 1 | 0 | 0.0% | 0 | 0 |
| Asian Indoor (and Martial Arts) Games | 2005–2017 | 4 | 48 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Baltic Games 1914 (Malmo) | 1914–1914 | 1 | 4 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| British Empire v USA match | 1924–1952 | 4 | 3 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Central American and Caribbean (CAC) Championships | 1967–2013 | 24 | 439 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| CIS Championships 1992 (indoor and outdoor) | 1992–1992 | 2 | 0 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Europe vs Americas match | 1967–1969 | 2 | 32 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| European Cup (top division) | 1965–2008 | 31 | 537 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| European Athletics Indoor Cup | 2003–2008 | 4 | 48 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| East German Championships | 1948–1990 | 43 | 733 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| East German Indoor Championships | 1964–1990 | 27 | 297 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Pan Africa v USA meet | 1971–1982 | 3 | 42 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| Spartakiad of the Peoples of the USSR (athletics) | 1956–1991 | 10 | 176 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| US Olympic Trials (track and field) | 1920–2016 | 31 | 319 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| USA national-team matches (other than USSR) | 1958–1982 | 22 | 345 | 0 | 0 | 0 | 0 | – | 0 | 0 |

## By decade (elite core and secondary)

| Decade | Editions | Events | Events held | With race counts | Races | Held | Share | Published | Published, not held |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1870s | 4 | 26 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| 1880s | 22 | 134 | 0 | 0 | 0 | 0 | – | 0 | 0 |
| 1890s | 21 | 124 | 0 | 1 | 13 | 0 | 0.0% | 0 | 0 |
| 1900s | 32 | 154 | 0 | 4 | 222 | 0 | 0.0% | 0 | 0 |
| 1910s | 48 | 162 | 0 | 13 | 189 | 0 | 0.0% | 0 | 0 |
| 1920s | 87 | 616 | 0 | 19 | 445 | 0 | 0.0% | 0 | 0 |
| 1930s | 98 | 912 | 2 | 21 | 545 | 2 | 0.4% | 2 | 0 |
| 1940s | 88 | 953 | 1 | 12 | 222 | 1 | 0.5% | 1 | 0 |
| 1950s | 149 | 1,711 | 7 | 18 | 773 | 7 | 0.9% | 8 | 1 |
| 1960s | 184 | 2,202 | 12 | 20 | 957 | 12 | 1.3% | 19 | 7 |
| 1970s | 272 | 2,948 | 14 | 95 | 1,984 | 14 | 0.7% | 45 | 31 |
| 1980s | 334 | 3,531 | 28 | 136 | 3,111 | 28 | 0.9% | 51 | 23 |
| 1990s | 560 | 5,185 | 18 | 313 | 5,458 | 18 | 0.3% | 50 | 32 |
| 2000s | 683 | 5,257 | 35 | 283 | 5,199 | 142 | 2.7% | 218 | 76 |
| 2010s | 538 | 5,154 | 191 | 291 | 7,597 | 310 | 4.1% | 646 | 336 |
| 2020s | 376 | 4,840 | 1,006 | 371 | 11,518 | 1,809 | 15.7% | 2,713 | 904 |

## By event (elite core and secondary)

| Event | Races | Held | Share | Races since 2010 | Held | Share | Published since 2010 | Published, not held |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 60m men | 883 | 0 | 0.0% | 528 | 0 | 0.0% | 1 | 1 |
| 60m women | 790 | 0 | 0.0% | 470 | 0 | 0.0% | 1 | 1 |
| 100m men | 3,140 | 113 | 3.6% | 1,489 | 93 | 6.2% | 109 | 16 |
| 100m women | 2,352 | 113 | 4.8% | 1,237 | 96 | 7.8% | 109 | 13 |
| 200m men | 2,717 | 131 | 4.8% | 1,202 | 110 | 9.2% | 121 | 11 |
| 200m women | 2,055 | 129 | 6.3% | 1,041 | 109 | 10.5% | 118 | 9 |
| 300m men | 28 | 0 | 0.0% | 23 | 0 | 0.0% | 0 | 0 |
| 300m women | 42 | 1 | 2.4% | 36 | 1 | 2.8% | 1 | 0 |
| 400m men | 2,974 | 177 | 6.0% | 1,468 | 153 | 10.4% | 257 | 104 |
| 400m women | 2,228 | 175 | 7.9% | 1,302 | 154 | 11.8% | 251 | 97 |
| 800m men | 2,572 | 216 | 8.4% | 1,251 | 199 | 15.9% | 393 | 194 |
| 800m women | 1,973 | 211 | 10.7% | 1,071 | 200 | 18.7% | 388 | 188 |
| 1000m men | 59 | 3 | 5.1% | 30 | 3 | 10.0% | 6 | 3 |
| 1000m women | 41 | 4 | 9.8% | 23 | 4 | 17.4% | 4 | 0 |
| 1500m men | 1,573 | 143 | 9.1% | 741 | 127 | 17.1% | 215 | 88 |
| 1500m women | 1,190 | 143 | 12.0% | 685 | 134 | 19.6% | 222 | 88 |
| mile men | 369 | 22 | 6.0% | 126 | 22 | 17.5% | 57 | 35 |
| mile women | 148 | 10 | 6.8% | 81 | 10 | 12.3% | 43 | 33 |
| 3000m men | 493 | 22 | 4.5% | 211 | 22 | 10.4% | 49 | 27 |
| 3000m women | 467 | 22 | 4.7% | 193 | 21 | 10.9% | 49 | 28 |
| 2-miles men | 114 | 5 | 4.4% | 18 | 5 | 27.8% | 6 | 1 |
| 5000m men | 793 | 63 | 7.9% | 326 | 63 | 19.3% | 106 | 43 |
| 5000m women | 487 | 59 | 12.1% | 283 | 58 | 20.5% | 100 | 42 |
| 10000m men | 319 | 13 | 4.1% | 156 | 13 | 8.3% | 33 | 20 |
| 10000m women | 221 | 16 | 7.2% | 140 | 14 | 10.0% | 34 | 20 |
| 60mh men | 704 | 1 | 0.1% | 419 | 1 | 0.2% | 1 | 0 |
| 60mh women | 643 | 0 | 0.0% | 419 | 0 | 0.0% | 0 | 0 |
| 80mh women | 140 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 100mh women | 1,605 | 90 | 5.6% | 910 | 81 | 8.9% | 89 | 8 |
| 110mh men | 1,900 | 89 | 4.7% | 877 | 79 | 9.0% | 86 | 7 |
| 400mh men | 1,605 | 123 | 7.7% | 768 | 116 | 15.1% | 126 | 10 |
| 400mh women | 1,202 | 114 | 9.5% | 713 | 105 | 14.7% | 117 | 12 |
| 3000msc men | 820 | 72 | 8.8% | 384 | 63 | 16.4% | 135 | 72 |
| 3000msc women | 407 | 59 | 14.5% | 354 | 59 | 16.7% | 128 | 69 |
| 1000y men | 65 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 100y men | 95 | 0 | 0.0% | 1 | 0 | 0.0% | 0 | 0 |
| 100y women | 57 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 120yh men | 40 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 150m men | 28 | 0 | 0.0% | 24 | 0 | 0.0% | 0 | 0 |
| 150m women | 22 | 0 | 0.0% | 20 | 0 | 0.0% | 0 | 0 |
| 220y men | 84 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 220y women | 45 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 3-miles men | 22 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 440y men | 97 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 440yh men | 26 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 600y men | 89 | 0 | 0.0% | 2 | 0 | 0.0% | 0 | 0 |
| 60y men | 45 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 60yh men | 30 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |
| 880y men | 122 | 0 | 0.0% | 0 | 0 | – | 0 | 0 |

## Published but not held, largest first

| Series | Era | Races | Status | Publisher | Where |
|---|--:|--:|--:|--:|--:|
| NCAA Division I Indoor Championships | 2008–2026 | 224 | public | Flash Results, Inc. | [link](https://www.flashresults.com/2008_Meets/indoor/NCAADI/evtindex.htm) |
| NCAA Division I Outdoor Championships | 2009–2026 | 192 | public | Flash Results, Inc. | [link](https://www.flashresults.com/2010_Meets/outdoor/NCAA/SplitResults4-1-1.htm) |
| USA Outdoor Championships (AAU / TAC / USATF) | 2016–2023 | 169 | public | Flash Results | [link](https://www.flashresults.com/2023_Meets/Outdoor/07-06_USATF/110-2-01.htm) |
| USA Outdoor Championships (AAU / TAC / USATF) | 2024–2026 | 99 | public | PrimeTime Timing (pttiming) for USATF | [link](https://results.usatf.org/2025Outdoors/) |
| European Athletics Championships | 1971–2001 | 78 | unofficial-splits | GDR sport science (Hess), Behm, Breizer, RFEA (Sanchez), Veney; collected by Ath | [link](https://www.athletefirst.org/wp-content/uploads/2023/12/M110H-by-time-20231113.pdf) |
| USA Indoor Championships (AAU / TAC / USATF) | 2024–2026 | 70 | public | PrimeTime Timing for USATF | [link](https://results.usatf.org/2024Indoors/) |
| Grand Slam Track | 2025–2025 | 64 | archived | Grand Slam Track (grandslamtrack.com results) | [link](https://web.archive.org/web/20250621143533/https://www.grandslamtrack.com/results/kingston/schedule-and-splits) |
| European Athletics Championships | 2022–2025 | 60 | public | European Athletics results books (directus) | [link](https://directus.european-athletics.com/downloads/be94a5e9-2ea6-4103-9b6f-d72e32e5140b/Results%20Book%20-Munich%202022%20European%20Athletics%20Championships%20v2.0.pdf) |
| IAAF (Mobil) Grand Prix | 2005–2009 | 56 | unofficial-splits | Flash Results (US meetings); IAAF (iaaf.org) elsewhere | [link](https://www.flashresults.com/2008results.htm) |
| USA Indoor Championships (AAU / TAC / USATF) | 2016–2023 | 55 | public | Flash Results | [link](https://www.flashresults.com/2016_Meets/Indoor/03-11_USATF/) |
| Wanda Diamond League | 2021–2026 | 48 | public | OMEGA (omegatiming.com); SportResult 2021-22, meeting sites 2023 | [link](https://www.omegatiming.com/Sport/String/AT/2021) |
| European Athletics Indoor Championships | 2023–2024 | 46 | public | European Athletics results book (directus) | [link](https://directus.european-athletics.com/downloads/04533363-3556-498e-8c4d-a098ec2adc6a/Results%20Book%20EICH%20Istanbul%202023.pdf) |
| Millrose Games | 2014–2026 | 44 | public | NYRR / Armory live results app | [link](https://results.millrosegames.org/) |
| European Athletics Championships | 2018–2021 | 31 | archived | European Athletics (externalmodules) | [link](http://www.european-athletics.org/externalmodules/AT/pdf/ATM008101_C77A.pdf) |
| Commonwealth Games (athletics) | 2018–2018 | 20 | public | Gold Coast 2018 OC (results book, Pulselive-hosted) | [link](https://resources.cwg-qbr.pulselive.com/qbr-commonwealth-games/document/2022/11/24/d64c5087-f083-46f8-a3d3-f395c2928973/GC2018_ATH_ResultsBook.pdf) |
| European Athletics Championships | 2002–2006 | 20 | unofficial-splits | FGS Halle (Graubner), Behm, Weber | [link](http://www.fgs.uni-halle.de) |
| Wanda Diamond League | 2016–2020 | 17 | archived | SportResult (static.sportresult.com); Flash Results for Prefontaine 2017-19 | [link](https://web.archive.org/cdx/search/cdx?url=static.sportresult.com/sports/at/data/2019/&matchType=prefix) |
| Olympic Games (athletics) | 1956–1996 | 16 | unofficial-splits | WA/ATFS Statistics Handbook (Rio 2016 edition, ed. Mark Butler); official report | [link](https://media.aws.iaaf.org/competitioninfo/f0e8eb10-cb01-490a-ad69-e9b16a355816.pdf) |
| Penn Relays | 2023–2026 | 13 | public | Flash Results, Inc. | [link](https://results.flashresults.com/2023_04-27_PennRelays/404-1-01.htm) |
| American Track League | 2021–2021 | 12 | public | Flash Results | [link](https://www.flashresults.com/2021_Meets/Indoor/01-24_ATL/023-1-02.htm) |
| World Athletics Indoor Championships | 2024–2026 | 12 | public | World Athletics / Seiko | [link](https://worldathletics.org/competitions/world-athletics-indoor-championships/x-7199326/results/men/400-metres/round-1/result) |
| World Athletics Championships | 2009–2011 | 10 | unofficial-splits | DLV/IAAF biomechanics project (2009); Korean Society of Sport Biomechanics/IAAF  | [link](https://www.researchgate.net/publication/263641446_Sport_Biomechanics_Research_Project_at_IAAF_World_Championships_Daegu_2011) |
| World Athletics Championships | 2013–2013 | 10 | public | World Athletics / Seiko | [link](https://media.aws.iaaf.org/competitiondocuments/pdf/4873/) |
| Olympic Games (athletics) | 2016–2016 | 8 | archived | Rio 2016 / OMEGA (ORIS results book) | [link](https://web.archive.org/web/2017/http://smsprio2016-a.akamaihd.net/_sport/R/i/Rio_2016_Athletics_Results_Book_V1.0.pdf) |
| World Athletics Championships | 2019–2019 | 8 | public | World Athletics / Seiko | [link](https://worldathletics.org/competitions/world-athletics-championships/x-7125365/results/men/1500-metres/round-1/result) |

## Where the counts come from

| Scope | Races counted from | Editions |
|---|--:|--:|
| elite-core | olympedia | 23 |
| elite-core | programme-era | 34 |
| elite-core | research-events | 303 |
| elite-core | research-rounds | 211 |
| elite-core | unknown | 351 |
| elite-core | wa | 363 |
| elite-secondary | programme-era | 1,168 |
| elite-secondary | research-events | 241 |
| elite-secondary | research-rounds | 75 |
| elite-secondary | unknown | 360 |
| elite-secondary | wa | 367 |
| sub-elite | unknown | 70 |
| sub-elite | wa | 3,808 |

Edition sources: wa 4,677, research 3,134, lineage 581, olympedia 23.

<!-- /report -->

## Known gaps

- **Unverified research.** The edition lists from research were each compiled by one
  researcher; the second, adversarial check was stopped by usage limits. `research/editions.csv`
  keeps each row's confidence and source.
- **Editions without race counts.** National championships, trials, NCAA and relay carnivals
  before 2018 mostly give the standard programme of their era, not heats per round, so they add
  events but not races. The race totals undercount these series; the event columns do not.
- **Indoor permit meetings 1997–2015, Super Grand Prix 2003–05** and a few other circuit
  seasons list meetings with their circuit events only, not full programmes.
- **Meetings outside any circuit, above all before 1985.** The classic invitationals before the
  Grand Prix, the US indoor and outdoor invitationals and the European indoor meetings are
  estimated at about 3,400 meeting-editions; the lineage research (331 meetings, a quick pass)
  attested only 587 of them, mostly with years and dates but not programmes, and marked most
  meetings low confidence. 135 minor lineages were not researched.
- **Published is a lower bound.** Availability was researched per series, so publishers that
  covered only some meetings of a series (OMEGA at several Continental Tour meetings since
  2020, PrimeTime's 10 m splits at the US indoor meetings since 2020) are missed unless Splits
  already holds those races.
- **World Athletics gaps.** 59 competitions' results could not be read from the API (mostly
  minor national championships; also the 2024 Oceania Championships).
- **Sub-elite series** before 2018 are listed as series only; their editions come from
  World Athletics' calendar (complete from 2018, sparse before).
- **The denominator is wider than the catalog's inclusion rule.** At one-day meetings,
  international "Pre-Programme" heats and second-tier races count as races; Splits leaves B
  races and invitationals out on purpose.

## Rebuilding

```bash
uv run python survey/tools/world_athletics.py calendar
uv run python survey/tools/world_athletics.py results
uv run python survey/tools/olympedia.py
uv run python survey/tools/research.py data/cache/survey/research/editions-workflow.json
uv run python survey/tools/build.py
uv run python survey/tools/report.py
```

The harvests cache under `data/cache/survey/` (not committed); `research/` is the committed
record of the research.
