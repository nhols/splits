# Adding a format

A *format* is one kind of published document, such as World Athletics' RS5 race analysis. Its
reader turns a document's text layer into a `DocumentReading`: a typed transcription of what
the document says, with every value sourced to the words it came from. Identity, merging and
plausibility are not the reader's job; assembly and the checks handle them the same way for
every format.

The existing readers are good models. Race analyses, which give the splits: `wa_rs5.py`
(column markers) and `wa_rs5_2015.py` (the same documents' older layout, placed by column
alone), and `omega_race_analysis.py` and `oris_c77a.py` (tiered grids, sharing
`omega_grid.py`). Results, which give places, lanes, reaction times and the official result:
`wa_results.py` (one document for all the heats of a round), `omega_results.py` and
`oris_c73b1.py` (a race's results, or a whole round's in sections). The two ORIS readers share
`oris.py`, which finds the race a report names in either dialect (the Olympic and Commonwealth
Games', European Athletics') and serves the discovery of results books too. For races older
than the timing systems' own documents: `wa_handbook.py` (the results of past finals in World
Athletics' statistics handbooks, two columns per page, found by the competition's city and
year), and `iaaf_biomechanics.py` and `wa_biomechanics.py` (tables of video timings; the
latter names athletes by family name alone, which assembly matches to the race's results).

## 1. Declare a document

Add the competition and one document to the catalog, with a new format ID:

```yaml
# catalog/competitions/<id>/competition.yaml
documents:
  - race: 400m-men/final
    format: my-format
    url: https://example.org/results/400m-men-final.pdf
```

For a compilation that reports many races (a statistics handbook, a results book), add
`pages: [102]` to read only the pages that report this race.

Then `uv run splits fetch <competition-id>` downloads it and pins its SHA-256.

## 2. Look at it as a reader will

```bash
uv run splits inspect <document-id>          # lines, as grouped by the toolkit
uv run splits inspect <document-id> --words  # every word with position, font and size
```

The text layer is the only input a reader gets: words with their boxes, fonts and sizes,
grouped into lines by `view.lines(page)`.

## 3. Write the reader

Create `src/splits/formats/my_format.py`:

```python
import re

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
)
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView

HEADING = re.compile(r"(?P<discipline>\d+m) (?P<sex>Men|Women) (?P<round>Final|Heat \d)")
ATHLETE = re.compile(r"(?P<place>\d+) (?P<name>.+?) (?P<country>[A-Z]{3}) (?P<result>\d+\.\d{2})")


class MyFormat(Format):
    id = format_id("my-format")
    version = "1.0.0"
    name = "Example results sheet"
    publisher = "Example Timing"
    description = "What these documents contain."
    kind = DocumentKind.RESULTS  # or ANALYSIS, for documents that give splits

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = view.lines(1)
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading", 1)
        entries = []
        for line in lines:
            row = view.match(line, ATHLETE, "athlete-row", full=True)
            if row:
                entries.append(
                    EntryReading(
                        row=row.span(),
                        place=row.read_opt("place", int),
                        name=row.read("name", lambda t: parse.person_name(t, family_first=True)),
                        country=row.read("country", parse.country),
                        result=row.read("result", parse.result),
                    )
                )
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=heading.found[0], source=heading.span(), method="heading"),
            heading=HeadingReading(
                discipline=heading.read("discipline", parse.discipline),
                sex=heading.read("sex", parse.sex),
                round=heading.read("round", parse.round_name),
                heat=None,
            ),
            date=...,  # read it the same way
            entries=tuple(entries),
        )
```

The toolkit does the bookkeeping. `view.match(line, pattern, rule)` returns a `LineMatch`, and
`row.read(group, parser)` returns a `Sourced` value whose source covers exactly the words the
group matched, with method `<rule>.<group>`. `view.read(page, words, parser, method)` does the
same for words picked by position. For split tables, `Columns` assigns values to the nearest
column anchor, and `split_band` collects the split lines under an athlete row. Shared value
parsers are in `formats/parse.py`: times, ranks, results, dates, two-digit birth years, names
in either order.

Rules for readers:

- **Never guess.** If the document does not look as expected, raise `view.error(...)`. A
  document that fails to read stops the build and names itself; a silently misread one would
  not.
- **Place values by what the document says, not by counting.** A checkpoint a timing system
  missed is simply absent; use column positions or labels to decide where each value belongs.
- **Transcribe; do not interpret.** Keep values as printed, including the obviously wrong
  ones. The checks will flag them.
- **Read what is there, even if another document has it too.** A race's documents are
  combined in assembly: a results document is the authority on results, places, lanes and
  reaction times, and any disagreement between documents is flagged (`documents-agree`).

## 4. Register it

Add the reader to `FORMATS` in `src/splits/formats/__init__.py`.

## 5. Test it on real documents

```bash
uv run splits fixture <document-id>...       # save text layers to tests/fixtures/text/
UPDATE_GOLDEN=1 uv run pytest tests/formats  # record what the reader transcribes
```

Review the recorded transcripts in `tests/fixtures/readings/`: one line per value, with the
page, box, text and rule it was read from. Commit them. From then on any change to what the
reader produces shows up as a diff. Pick fixtures for every variant you found: missing
splits, disqualifications, multi-page documents, unusual headings.

## 6. Build

`make build` reads every document, and the checks will tell you if values disagree: printed
segments that do not match the splits are the usual sign of a value placed in the wrong
column. Bump the reader's `version` whenever its output changes.
