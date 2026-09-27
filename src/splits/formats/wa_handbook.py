"""World Athletics statistics handbooks: the results of past finals.

Before each Olympic Games, World Championships and Continental Cup, World Athletics publishes
a statistics handbook, compiled with the Association of Track and Field Statisticians, with
the result of every past final: place, lane, name, country and time, often the time at
halfway ("halves") or the reaction time, and for recent finals a table of splits. Pages have
two columns, read left then right. The catalog names the page (or pages) of the race; its block
is the one headed by the competition's city and year::

    Seoul, 29 Sep 1988                                          the city and date
    (1.3) Halves                                                the wind
    1, |5| Florence Griffith Joyner USA 21.34 WR 11.18/10.16    place, lane, ..., halves
    ...
    (Competitors: 59; Countries: 42; Finalists: 8)
    Splits 50m 100m 150m
    Griffith Joyner 6.29 11.18 16.10

Older editions print the city and year with the round, date and wind on the next line
(``Berlin 2009`` / ``Final (Aug 20) (-0.3)``), a reaction time after the result
(``1, Usain Bolt JAM 09.58WR 0.146``), or no lanes; then a lane given in the report
of the race (``Koch (lane 2) sped through 200m in 22.4. At 300m (34.1)``), and any splits in
the same sentence, are read from the report's words.
"""

import re
import unicodedata
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
    SegmentReading,
    SplitReading,
)
from splits.model import DisciplineId, PersonName, Round, Sex, Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch, group_lines
from splits.pdf.textlayer import Word

HEADER_BAND = 40.0
"""Points from the top of the page: the running header, in spaced capitals."""

TITLE = re.compile(
    r"(?:(?P<event>\d+ Metres(?: Hurdles)?) )?(?P<city>[^\d,()]+?),? "
    r"(?:(?P<day>\d{1,2}) (?P<month>[A-Z][a-z]{2}) )?(?P<year>(?:18|19|20)\d{2})"
)
ROUND = re.compile(r"\b(?P<round>Final)\b")
DAY = re.compile(r"\((?P<day>[A-Z][a-z]{2} \d{1,2})\)")
MINUS = "\u2212"
"""The minus sign, as some editions print negative winds."""
WIND = re.compile(rf"\((?P<wind>[-+{MINUS}]?\d+\.\d)\)")
ENTRY = re.compile(
    r"(?:(?P<place>\d{1,2}), ?)?(?:\|(?P<lane>\d{1,2})\| )?(?P<name>[^\d|]+?) "
    r"(?:[A-Z]{3}(?:/[A-Z]{3})? )*(?P<country>[A-Z]{3}) "
    r"(?P<result>\d{1,2}\.\d{1,2}|DNF|DNS|DQ)(?: ?(?P<record>=?(?:WR|OR|WJR|AR|CR|NR)))?"
    r"(?: (?P<reaction>-?0\.\d{3}))?"
    r"(?: (?P<first>\d{1,2}\.\d{1,2})/(?P<second>\d{1,2}\.\d{1,2}))?(?: \([\d.]+\))?"
)
SPLITS_HEADER = re.compile(r"Splits(?P<distances>(?: \d+m)+)")
SPLITS_ROW = re.compile(r"(?P<name>[^\d]+?)(?P<times>(?: \d{1,2}\.\d{1,2})+)")
SEX_AND_EVENTS = re.compile(
    r"(?P<sex>WOMEN|MEN)[\u02bc\u2019']S(?P<events>\d+m(?:HURDLES)?(?:,\d+m(?:HURDLES)?)*)"
)
FINALS = re.compile(r"FINALS")
REPORTED_LANE = r"\b{family} \(lane (?P<lane>\d{{1,2}})\)"
REPORTED_SPLITS = (
    re.compile(r"through (?P<distance>\d{2,3})m in (?P<time>\d{1,2}\.\d{1,2})"),
    re.compile(r"\bAt (?P<distance>\d{2,3})m \((?P<time>\d{1,2}\.\d{1,2})\)"),
)

type Timed = list[tuple[TimingPoint, Sourced[Decimal]]]


class WaHandbook(Format):
    kind = DocumentKind.RESULTS
    id = format_id("wa-handbook")
    version = "1.1.0"
    name = "World Athletics statistics handbook"
    publisher = "World Athletics, with the ATFS"
    description = (
        "The results of past finals in the statistics handbooks World Athletics publishes for "
        "its championships: place, lane, name, country and time, often the time at halfway "
        "or the reaction time, and for recent finals a table of splits."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines, headers = _reading_order(view)
        city, year = context.competition.venue.city, context.competition.start_date.year
        titles = [
            (index, found)
            for index, line in enumerate(lines)
            if _is_title(line) and (found := view.match(line, TITLE, "title", full=True))
        ]
        ours = [
            (index, found)
            for index, found in titles
            if _fold(found["city"] or "") == _fold(city) and found["year"] == str(year)
        ]
        if len(ours) != 1:
            raise view.error(f"expected one result headed {city} {year}, found {len(ours)}")
        start, title = ours[0]
        following = [index for index, _ in titles if index > start]
        block = lines[start + 1 : following[0] if following else len(lines)]

        first = next((i for i, line in enumerate(block) if ENTRY.fullmatch(line.text)), None)
        if first is None:
            raise view.error(f"no results under {title.line.text!r}", title.line.page)
        intro, rows = block[:first], []
        for line in block[first:]:
            row = view.match(line, ENTRY, "result-row", full=True)
            if row is None:
                break
            rows.append(row)
        after = block[first + len(rows) :]
        table = _splits_table(view, after)
        report = [line for line in after if not line.words[0].font.startswith("Helvetica")]
        families = [name for name, _ in table]

        finish = context.discipline.finish()
        half = TimingPoint.at(finish.distance / 2)
        entries = []
        for row in rows:
            name = row.read("name", lambda text: _split_name(text, families))
            timed = next((times for printed, times in table if _is(printed, name.value)), [])
            points = {point.distance: SplitReading(point=point, time=time) for point, time in timed}
            lane = row.read_opt("lane", int)
            if lane is None:
                lane, told = _from_report(view, report, name.value.family)
                for point, time in told:
                    points.setdefault(point.distance, SplitReading(point=point, time=time))
            segments: tuple[SegmentReading, ...] = ()
            if row["first"] is not None:
                if half.distance not in points:
                    points[half.distance] = SplitReading(
                        point=half, time=row.read("first", parse.seconds)
                    )
                segments = (
                    SegmentReading(start=half, end=finish, time=row.read("second", parse.seconds)),
                )
            record = row.read_opt("record", str)
            entries.append(
                EntryReading(
                    row=row.span(),
                    place=row.read_opt("place", int),
                    lane=lane,
                    name=name,
                    country=row.read("country", parse.country),
                    result=row.read("result", parse.result),
                    reaction_time=row.read_opt("reaction", parse.signed_decimal),
                    records=(record,) if record else (),
                    splits=tuple(points[distance] for distance in sorted(points)),
                    segments=segments,
                )
            )

        page = title.line.page
        sex, finals = _header(view, page, headers[page])
        round_line = view.find(intro, ROUND, "round")
        wind_line = view.find(intro, WIND, "wind")
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=title.line.text, source=title.span(), method="title"),
            heading=HeadingReading(
                discipline=_event(view, lines[:start], title, headers[page]),
                sex=sex,
                round=round_line.read("round", parse.round_name) if round_line else finals,
                heat=None,
            ),
            date=_date(view, title, view.find(intro, DAY, "date")),
            wind=wind_line.read("wind", _wind) if wind_line else None,
            entries=tuple(entries),
        )


def _reading_order(view: DocumentView) -> tuple[list[Line], dict[int, list[Word]]]:
    """The pages' lines, left column then right, and each page's running header."""
    lines: list[Line] = []
    headers: dict[int, list[Word]] = {}
    for page in view.pages:
        middle = page.width / 2
        headers[page.number] = sorted(
            (word for word in page.words if word.top < HEADER_BAND), key=lambda word: word.x0
        )
        body = [word for word in page.words if word.top >= HEADER_BAND]
        lines.extend(group_lines([w for w in body if w.xc < middle], page.number))
        lines.extend(group_lines([w for w in body if w.xc >= middle], page.number))
    return lines, headers


def _is_title(line: Line) -> bool:
    """Results are headed by their city and year, in 12-point bold."""
    return line.words[0].bold and line.words[0].size >= 11


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _wind(text: str) -> Decimal:
    return parse.signed_decimal(text.replace(MINUS, "-"))


def _despaced(
    view: DocumentView, words: list[Word], pattern: re.Pattern[str]
) -> tuple[re.Match[str] | None, list[Word]]:
    """``pattern`` in words set as spaced capitals (``M E N ’ S``), run together."""
    text, owners = "", []
    for index, word in enumerate(words):
        text += word.text
        owners.extend([index] * len(word.text))
    return (pattern.search(text), [words[i] for i in owners]) if text else (None, [])


def _read_spaced[T](
    view: DocumentView,
    page: int,
    found: re.Match[str],
    owners: list[Word],
    group: str | int,
    parse_value: Callable[[str], T],
    method: str,
) -> Sourced[T]:
    """Read a group of a match in spaced capitals: the letters it matched, from the words
    they are printed in."""
    words: list[Word] = []
    for word in owners[found.start(group) : found.end(group)]:
        if not words or words[-1] is not word:
            words.append(word)
    return view.read(page, words, parse_value, method, found[group])


def _header(
    view: DocumentView, page: int, header: list[Word]
) -> tuple[Sourced[Sex], Sourced[Round] | None]:
    """The sex, and the round when the page is in a section of finals, from the running
    header."""
    found, owners = _despaced(view, header, SEX_AND_EVENTS)
    if found is None:
        raise view.error("no running header naming men's or women's events", page)
    sex = _read_spaced(view, page, found, owners, "sex", parse.sex, "header.sex")
    finals, finals_owners = _despaced(view, header, FINALS)
    rounds = (
        _read_spaced(view, page, finals, finals_owners, 0, parse.round_name, "header.round")
        if finals
        else None
    )
    return sex, rounds


def _event(
    view: DocumentView, before: list[Line], title: LineMatch, header: list[Word]
) -> Sourced[DisciplineId]:
    """The event: in the title, else in the last title before it on the page that names one,
    else in the running header when the page carries a single event."""
    if title["event"]:
        return title.read("event", parse.discipline)
    for line in reversed(before):
        if line.page != title.line.page:
            break
        earlier = view.match(line, TITLE, "title", full=True) if _is_title(line) else None
        if earlier is not None and earlier["event"]:
            return earlier.read("event", parse.discipline)
    found, owners = _despaced(view, header, SEX_AND_EVENTS)
    if found is None or "," in found["events"]:
        raise view.error("cannot tell which event this page reports", title.line.page)
    page = title.line.page
    return _read_spaced(view, page, found, owners, "events", parse.discipline, "header.event")


def _date(view: DocumentView, title: LineMatch, day: LineMatch | None) -> Sourced[date]:
    """The day of the race: in the title (``Seoul, 29 Sep 1988``), or on the line below it
    (``Final (Aug 20)``) with the year from the title."""
    if title["day"]:
        words = [*title.words("day"), *title.words("month"), *title.words("year")]
        return view.read(title.line.page, words, parse.day_month_year, "title.date")
    if day is None:
        raise view.error(f"no date for {title.line.text!r}", title.line.page)
    month, number = (day["day"] or "").split()
    text = f"{number} {month} {title['year']}"
    return day.read("day", lambda _: parse.day_month_year(text))


def _splits_table(view: DocumentView, lines: list[Line]) -> list[tuple[str, Timed]]:
    """The table of splits after the results, by the names it prints."""
    for index, line in enumerate(lines):
        header = view.match(line, SPLITS_HEADER, "splits-table", full=True)
        if header is None:
            continue
        distances = [Decimal(d.rstrip("m")) for d in (header["distances"] or "").split()]
        table = []
        for row_line in lines[index + 1 :]:
            row = view.match(row_line, SPLITS_ROW, "splits-table", full=True)
            if row is None or len((row["times"] or "").split()) != len(distances):
                break
            table.append(
                (
                    (row["name"] or "").strip(),
                    [
                        (
                            TimingPoint.at(distance),
                            view.read(
                                row_line.page, [word], parse.seconds, f"splits-table.{distance}m"
                            ),
                        )
                        for distance, word in zip(distances, row.words("times"), strict=True)
                    ],
                )
            )
        return table
    return []


def _split_name(text: str, families: list[str]) -> PersonName:
    """Given and family names from a name printed in full: the family name as the table of
    splits prints it, else everything after the first name and any initials (``P. T. Usha``)."""
    for printed in families:
        family = _without_initial(printed)
        if _fold(text).endswith(" " + _fold(family)):
            return PersonName(given=text[: -len(family) - 1], family=text[-len(family) :])
    tokens = text.split()
    if len(tokens) < 2:
        raise ValueError(f"expected a given and a family name in {text!r}")
    given = 1
    while given < len(tokens) - 1 and re.fullmatch(r"[A-Z]\.", tokens[given]):
        given += 1
    return PersonName(given=" ".join(tokens[:given]), family=" ".join(tokens[given:]))


def _without_initial(printed: str) -> str:
    """A family name as a table prints it, less an initial telling namesakes apart
    (``K Borlée``)."""
    return printed.split(" ", 1)[1] if re.match(r"[A-Z] ", printed) else printed


def _is(printed: str, name: PersonName) -> bool:
    """Whether a table's name for an athlete (``Van Niekerk``, ``K Borlée``) is ``name``."""
    if _fold(_without_initial(printed)) != _fold(name.family):
        return False
    return not re.match(r"[A-Z] ", printed) or name.given.startswith(printed[0])


def _from_report(
    view: DocumentView, report: list[Line], family: str
) -> tuple[Sourced[int] | None, Timed]:
    """The lane the report of the race gives an athlete (``Koch (lane 2)``), and the splits it
    gives in the rest of that line."""
    pattern = re.compile(REPORTED_LANE.format(family=re.escape(family)))
    for line in report:
        found = view.match(line, pattern, "report")
        if found is None:
            continue
        told: Timed = []
        rest = found.found.end()
        for sentence in REPORTED_SPLITS:
            for said in sentence.finditer(line.text, rest):
                words = line.words_in(said.start("time"), said.end("time"))
                told.append(
                    (
                        TimingPoint.at(Decimal(said["distance"])),
                        view.read(line.page, words, parse.seconds, "report.split", said["time"]),
                    )
                )
        return found.read("lane", int), told
    return None, []
