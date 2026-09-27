# Database schema

Generated from `src/splits/publish/tables.py` by `splits schema`; do not edit by hand.

Every value read from a document or declared in the catalog has a sibling `*_source`
column referencing `provenance.id`.

## `competitions`

Competitions, as declared in catalog/competitions/<id>/competition.yaml.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Competition ID, e.g. wch-2023-budapest. |
| `name` | VARCHAR | Official name. |
| `series` | VARCHAR | Series ID (series.id). |
| `start_date` | DATE | First day. |
| `end_date` | DATE | Last day. |
| `venue` | VARCHAR | Stadium or arena. |
| `city` | VARCHAR | City. |
| `country` | VARCHAR | Country code. |
| `setting` | VARCHAR | outdoor, indoor (200 m short track) or road. |
| `timezone` | VARCHAR | IANA time zone of the venue; document times are local to it. |
| `results_url` | VARCHAR | The organiser's official results page. |
| `declared_file` | VARCHAR | Catalog file that declares the competition. |
| `declared_line` | INTEGER | Line in that file. |

## `series`

Families of competitions (catalog/series.yaml).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Series ID, e.g. diamond-league. |
| `name` | VARCHAR | Full name. |
| `short_name` | VARCHAR | Compact name. |
| `kind` | VARCHAR | games, championships or meeting. |

## `disciplines`

What is raced (catalog/disciplines.yaml).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Discipline ID, e.g. 400mh. |
| `name` | VARCHAR | Full name, e.g. 400 metres hurdles. |
| `short_name` | VARCHAR | Compact name, e.g. 400mH. |
| `kind` | VARCHAR | flat, hurdles, steeplechase, relay, road or race-walk. |
| `distance_m` | DECIMAL(9,3) | Race distance in metres. |

## `barriers`

Barrier layouts of hurdles disciplines, per sex, from the World Athletics rules.

| Column | Type | Meaning |
| --- | --- | --- |
| `discipline` | VARCHAR | Discipline ID. |
| `sex` | VARCHAR | men or women. |
| `count` | INTEGER | Number of barriers. |
| `first_m` | DECIMAL(9,3) | Distance from the start to the first barrier. |
| `spacing_m` | DECIMAL(9,3) | Distance between barriers. |
| `height_m` | DECIMAL(9,3) | Barrier height. |

## `formats`

The kinds of document the dataset is read from, and their readers.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Format ID, e.g. wa-rs5. |
| `version` | VARCHAR | Version of the reader that read the documents. |
| `name` | VARCHAR | Name of the document type. |
| `publisher` | VARCHAR | Who publishes documents of this type. |
| `description` | VARCHAR | What the documents contain. |

## `documents`

Every document the dataset was read from: where it was published, the exact bytes that were read (SHA-256), and what the document says about itself.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Document ID: <race>/<format>. |
| `race` | VARCHAR | The race the document reports (races.id). |
| `format` | VARCHAR | Document format (formats.id). |
| `format_version` | VARCHAR | Version of the reader that read it. |
| `url` | VARCHAR | Where the publisher published it. |
| `archive_url` | VARCHAR | An immutable archived copy, if any. |
| `sha256` | VARCHAR | SHA-256 of the bytes that were read, pinned in the lock file. |
| `size_bytes` | BIGINT | Size of those bytes. |
| `retrieved_at` | TIMESTAMPTZ | When they were downloaded. |
| `retrieved_from` | VARCHAR | The URL that served them. |
| `pages` | INTEGER | Number of pages. |
| `issued` | TIMESTAMP | When the publisher issued this version (local time, as printed). |
| `issued_source` | VARCHAR | Provenance of issued. |
| `revision` | VARCHAR | The document's own version marker, e.g. v2.0. |
| `revision_source` | VARCHAR | Provenance of revision. |
| `timing_by` | VARCHAR | Timing provider credited by the document. |
| `timing_by_source` | VARCHAR | Provenance of timing_by. |

## `races`

Races: one start, one finish. Declared in the catalog, confirmed by the document.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Race ID: <competition>/<discipline>-<sex>/<round>[-<heat>]. |
| `competition` | VARCHAR | competitions.id. |
| `discipline` | VARCHAR | disciplines.id. |
| `sex` | VARCHAR | men, women or mixed. |
| `round` | VARCHAR | heat, repechage, quarter-final, semi-final or final. |
| `heat` | INTEGER | Heat number within the round; null for a single race. |
| `setting` | VARCHAR | outdoor, indoor or road. |
| `title` | VARCHAR | The race heading as printed. |
| `title_source` | VARCHAR | Provenance of title. |
| `date` | DATE | Date of the race. |
| `date_source` | VARCHAR | Provenance of date. |
| `start_time` | TIME | Local start time. |
| `start_time_source` | VARCHAR | Provenance of start_time. |
| `wind_mps` | DECIMAL(5,2) | Wind in m/s, positive is a tailwind. |
| `wind_mps_source` | VARCHAR | Provenance of wind_mps. |
| `temperature_c` | DECIMAL(5,1) | Temperature in °C. |
| `temperature_c_source` | VARCHAR | Provenance of temperature_c. |
| `humidity_pct` | DECIMAL(5,1) | Relative humidity in percent. |
| `humidity_pct_source` | VARCHAR | Provenance of humidity_pct. |
| `weather` | VARCHAR | Conditions as described. |
| `weather_source` | VARCHAR | Provenance of weather. |
| `declared_file` | VARCHAR | Catalog file that declares the race's document. |
| `declared_line` | INTEGER | Line in that file. |

## `athletes`

Athletes, identified across documents. Names and birth dates summarise the printed values stored, with provenance, on each performance.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Athlete ID, e.g. karsten-warholm. |
| `given_name` | VARCHAR | Given name. |
| `family_name` | VARCHAR | Family name, in display case. |
| `name` | VARCHAR | Given and family name. |
| `sex` | VARCHAR | men or women. |
| `country` | VARCHAR | Country of the most recent performance. |
| `birth_date` | VARCHAR | YYYY-MM-DD, or YYYY when only the year is printed. |
| `rule_file` | VARCHAR | The identity rule applied (catalog/athletes.yaml), if any. |
| `rule_line` | INTEGER | Line of that rule. |

## `performances`

One athlete's run in one race.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Performance ID: <race>/<athlete>. |
| `race` | VARCHAR | races.id. |
| `athlete` | VARCHAR | athletes.id. |
| `given_name` | VARCHAR | Given name as printed. |
| `family_name` | VARCHAR | Family name as printed. |
| `name_source` | VARCHAR | Provenance of the printed name. |
| `country` | VARCHAR | Country code as printed. |
| `country_source` | VARCHAR | Provenance of country. |
| `birth_date` | VARCHAR | Birth date as printed: YYYY-MM-DD, or YYYY. |
| `birth_date_source` | VARCHAR | Provenance of birth_date. |
| `bib` | VARCHAR | Bib number. |
| `bib_source` | VARCHAR | Provenance of bib. |
| `lane` | INTEGER | Lane. |
| `lane_source` | VARCHAR | Provenance of lane. |
| `place` | INTEGER | Finishing place. |
| `place_source` | VARCHAR | Provenance of place. |
| `status` | VARCHAR | finished, dnf, dns or dq. |
| `time_s` | DECIMAL(9,3) | Official finishing time in seconds; null unless finished. |
| `result_source` | VARCHAR | Provenance of status and time_s (the printed result). |
| `reaction_time_s` | DECIMAL(6,3) | Reaction time in seconds; negative for a false start. |
| `reaction_time_s_source` | VARCHAR | Provenance of reaction_time_s. |
| `precise_time_s` | DECIMAL(9,3) | The finishing time to the thousandth, where printed. |
| `precise_time_s_source` | VARCHAR | Provenance of precise_time_s. |
| `qualification` | VARCHAR | Q (by place) or q (by time). |
| `qualification_source` | VARCHAR | Provenance of qualification. |

## `annotations`

Annotations printed next to results: record tags (PB, SB, NR...) and remarks such as disqualification rules (TR17.3.1) or cards (YC).

| Column | Type | Meaning |
| --- | --- | --- |
| `performance` | VARCHAR | performances.id. |
| `kind` | VARCHAR | record or remark. |
| `value` | VARCHAR | The annotation as printed. |
| `source` | VARCHAR | Provenance of value. |

## `splits`

Cumulative times from the gun at timing points, each from the document that measured it. Derive segment times and speeds from these, not from segments.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Split ID: <performance>/<point>@<format>. |
| `performance` | VARCHAR | performances.id. |
| `document` | VARCHAR | documents.id of the document that measured it. |
| `point` | VARCHAR | Timing point label: 100m, H3 (hurdle 3), Finish. |
| `point_kind` | VARCHAR | distance, hurdle or finish. |
| `distance_m` | DECIMAL(9,3) | Distance of the point from the start. |
| `hurdle` | INTEGER | Barrier number, for hurdle points. |
| `time_s` | DECIMAL(9,3) | Time from the gun, in seconds. |
| `time_source` | VARCHAR | Provenance of time_s. |
| `rank` | INTEGER | Position at the point, as printed. |
| `rank_source` | VARCHAR | Provenance of rank. |

## `segments`

Segment times as printed by documents. Kept to verify the splits: each must equal the difference of the cumulative times at its ends (check segment-matches-splits).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Segment ID. |
| `performance` | VARCHAR | performances.id. |
| `document` | VARCHAR | documents.id. |
| `start_point` | VARCHAR | Label of the point the segment starts at (Start for the gun). |
| `start_m` | DECIMAL(9,3) | Its distance. |
| `end_point` | VARCHAR | Label of the point it ends at. |
| `end_m` | DECIMAL(9,3) | Its distance. |
| `time_s` | DECIMAL(9,3) | Segment time in seconds. |
| `time_source` | VARCHAR | Provenance of time_s. |

## `checks`

The data-quality checks run on every build.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Check ID. |
| `severity` | VARCHAR | error (values contradict each other) or warning (implausible). |
| `suspect` | BOOLEAN | Whether flagged values are left out of analyses. |
| `title` | VARCHAR | What the check verifies, briefly. |
| `explanation` | VARCHAR | What the check verifies and why. |

## `flags`

Findings of the checks, attached to the value they are about. Flagged values are kept as published; suspect ones are left out of analyses.

| Column | Type | Meaning |
| --- | --- | --- |
| `check_id` | VARCHAR | checks.id. |
| `severity` | VARCHAR | error or warning. |
| `subject` | VARCHAR | ID of the record the finding is about. |
| `field` | VARCHAR | The field of that record, e.g. time. |
| `message` | VARCHAR | What was found. |
| `suspect` | BOOLEAN | Whether analyses leave the value out. |

## `provenance`

Where each value came from. A document source gives the page, the box (in PDF points from the top-left corner) and the exact text read; a catalog source gives the file and line. method names the extraction rule.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | VARCHAR | Provenance ID, referenced by the *_source columns. |
| `kind` | VARCHAR | document or catalog. |
| `document` | VARCHAR | documents.id, for document sources. |
| `page` | INTEGER | Page number, from 1. |
| `x0` | DOUBLE | Left edge of the box. |
| `top` | DOUBLE | Top edge of the box. |
| `x1` | DOUBLE | Right edge of the box. |
| `bottom` | DOUBLE | Bottom edge of the box. |
| `text` | VARCHAR | The exact text read from the box. |
| `method` | VARCHAR | The rule that interpreted the text, e.g. cumulative.time. |
| `file` | VARCHAR | Catalog file, for catalog sources. |
| `line` | INTEGER | Line in that file. |
| `pointer` | VARCHAR | JSON pointer to the value in that file. |

## `build`

When and from which code this dataset was built.

| Column | Type | Meaning |
| --- | --- | --- |
| `built_at` | TIMESTAMPTZ | When the build ran. |
| `code_version` | VARCHAR | Git commit of the code, suffixed -dirty if uncommitted. |

## Views

- `results`: Results with names, races and competitions joined in: a convenient starting point.
- `split_analysis`: Each split series with the finish added from the official result, and the derived segment time, speed and share of the race. Derived columns are computed here, from the stored splits, never stored. suspect marks values analyses leave out: those a check flagged, and the whole run when a check flagged its result.
