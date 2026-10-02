"""The website's data: static JSON files written from the dataset.

    data/index.json                     everything needed to browse: events, competitions,
                                        races and athletes in summary
    data/events/<event>.json            every performance of an event with its splits,
                                        for analysis across races
    data/races/<race>.json              one race in full, with the source of every value
    data/schema.json                    JSON Schema of all of the above

The file shapes are defined in :mod:`splits.publish.site_schema`.
"""

import json
import shutil
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

from splits.checks import CHECKS
from splits.formats import FORMATS
from splits.model import (
    Dataset,
    Document,
    DocumentId,
    Flag,
    Performance,
    PointKind,
    Race,
    Sourced,
    Span,
    Status,
    TimingPoint,
)
from splits.model.values import annotation_meaning
from splits.publish.site_schema import (
    AnnotationOut,
    AthleteSummary,
    Barriers,
    BuildOut,
    CheckOut,
    ColumnOut,
    CompetitionOut,
    DisciplineOut,
    DocumentOut,
    EventData,
    EventOut,
    EventPerformance,
    FlagOut,
    FormatOut,
    Index,
    Point,
    RaceData,
    RacePerformance,
    RaceSegment,
    RaceSplit,
    RaceSummary,
    SeriesOut,
    SInt,
    SiteModel,
    SNum,
    Source,
    SStr,
    TableOut,
    Winner,
)
from splits.publish.tables import build_tables


class Sources:
    """Collects the sources of one file's values."""

    def __init__(self, documents: list[DocumentId]) -> None:
        self._documents = {doc: index for index, doc in enumerate(documents)}
        self.items: list[Source] = []
        self._index: dict[str, int] = {}

    def add(self, value: Sourced[Any]) -> int:
        key = value.model_dump_json()
        index = self._index.get(key)
        if index is None:
            source = value.source
            if isinstance(source, Span):
                box = source.bbox
                item = Source(
                    doc=self._documents[source.document],
                    page=source.page,
                    box=(box.x0, box.top, box.x1, box.bottom),
                    text=source.text,
                    method=value.method,
                    file=None,
                    line=None,
                )
            else:
                item = Source(
                    doc=None,
                    page=None,
                    box=None,
                    text=None,
                    method=value.method,
                    file=source.file,
                    line=source.line,
                )
            index = self._index[key] = len(self.items)
            self.items.append(item)
        return index

    def num(self, value: Sourced[Decimal] | None) -> SNum | None:
        return None if value is None else SNum(v=float(value.value), s=self.add(value))

    def int(self, value: Sourced[int] | None) -> SInt | None:
        return None if value is None else SInt(v=value.value, s=self.add(value))

    def str(self, value: Sourced[Any] | None) -> SStr | None:
        return None if value is None else SStr(v=str(value.value), s=self.add(value))


def _point(point: TimingPoint) -> Point:
    return Point(
        key=point.slug,
        kind=point.kind,
        distance=float(point.distance),
        hurdle=point.hurdle,
        label=point.label,
    )


def _flag(flag: Flag) -> FlagOut:
    return FlagOut(
        check=flag.check,
        severity=flag.severity.value,
        subject=flag.subject,
        field=flag.field,
        message=flag.message,
        suspect=flag.suspect,
    )


# ---- Writing ---------------------------------------------------------------------------------


def write_site_data(dataset: Dataset, root: Path) -> None:
    """Write every site file under ``root`` (replacing what was there)."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    flags_by_subject: dict[str, list[Flag]] = defaultdict(list)
    for flag in dataset.flags:
        flags_by_subject[flag.subject].append(flag)

    _write(root / "index.json", _index(dataset))
    for event, data in _events(dataset, flags_by_subject):
        _write(root / "events" / f"{event}.json", data)
    for race in dataset.races:
        _write(root / "races" / f"{race.id}.json", _race(dataset, race, flags_by_subject))
    schema = {
        name: model.model_json_schema(by_alias=True, mode="serialization")
        for name, model in (
            ("Index", Index),
            ("EventData", EventData),
            ("RaceData", RaceData),
        )
    }
    (root / "schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def _write(path: Path, model: SiteModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(by_alias=True), encoding="utf-8")


def annotation_meanings(dataset: Dataset) -> dict[str, str | None]:
    """Every mark printed beside a result in the dataset, and what it means (``None`` when
    neither the model nor ``catalog/annotations.yaml`` explains it)."""
    declared = {annotation.code: annotation.meaning for annotation in dataset.annotation_meanings}
    printed = sorted(
        {tag.value for perf in dataset.performances for tag in (*perf.records, *perf.remarks)}
    )
    return {value: annotation_meaning(value, declared) for value in printed}


def _event_of(race: Race) -> str:
    return race.key.event


def _module_path(cls: type) -> str:
    """``src/splits/formats/wa_rs5.py``: where a class is defined, from the repository root."""
    return "src/" + cls.__module__.replace(".", "/") + ".py"


def _race_of_subject(subject: str) -> str:
    """The race a flag is about: race, performance, split and segment IDs all start with it."""
    return "/".join(subject.split("/")[:3])


def _index(dataset: Dataset) -> Index:
    races = {race.id: race for race in dataset.races}
    perfs_by_race: dict[str, list[Performance]] = defaultdict(list)
    for perf in dataset.performances:
        perfs_by_race[perf.race].append(perf)
    split_points: dict[str, set[TimingPoint]] = defaultdict(set)
    split_formats: dict[str, set[str]] = defaultdict(set)
    perfs_with_splits: set[str] = set()
    for split in dataset.splits:
        race_id = split.performance.rsplit("/", 1)[0]
        split_points[race_id].add(split.point)
        split_formats[race_id].add(split.document.rsplit("/", 1)[1])
        perfs_with_splits.add(split.performance)
    flag_count: dict[str, int] = defaultdict(int)
    for flag in dataset.flags:
        flag_count[_race_of_subject(flag.subject)] += 1

    def winner(race_id: str) -> Winner | None:
        finishers = [p for p in perfs_by_race[race_id] if p.status is Status.FINISHED and p.time]
        if not finishers:
            return None
        # The place decides a tie in hundredths (a photo finish); without places, the time.
        best = min(
            finishers,
            key=lambda p: (
                p.place.value if p.place is not None else 999,
                p.precise_time.value if p.precise_time is not None else p.time,
            ),
        )
        assert best.time is not None
        return Winner(
            athlete=best.athlete,
            time=float(best.time),
            records=[record.value for record in best.records],
        )

    events: dict[str, list[Race]] = defaultdict(list)
    for race in dataset.races:
        events[_event_of(race)].append(race)
    event_out = []
    for event, event_races in sorted(events.items()):
        perfs = [p for race in event_races for p in perfs_by_race[race.id]]
        times = [p.time for p in perfs if p.time is not None]
        event_out.append(
            EventOut(
                id=event,
                discipline=event_races[0].key.discipline,
                sex=event_races[0].key.sex.value,
                races=len(event_races),
                performances=len(perfs),
                athletes=len({p.athlete for p in perfs}),
                with_splits=sum(p.id in perfs_with_splits for p in perfs),
                settings=sorted({race.setting.value for race in event_races}),
                fastest=float(min(times)) if times else None,
            )
        )

    bests: dict[str, dict[str, float]] = defaultdict(dict)
    race_count: dict[str, int] = defaultdict(int)
    athlete_events: dict[str, set[str]] = defaultdict(set)
    for perf in dataset.performances:
        race_count[perf.athlete] += 1
        athlete_events[perf.athlete].add(_event_of(races[perf.race]))
        if perf.time is not None:
            event = _event_of(races[perf.race])
            current = bests[perf.athlete].get(event)
            if current is None or float(perf.time) < current:
                bests[perf.athlete][event] = float(perf.time)

    documents_by_competition: dict[str, int] = defaultdict(int)
    for document in dataset.documents:
        documents_by_competition[races[document.race].competition] += 1
    documents_by_format: dict[str, int] = defaultdict(int)
    for document in dataset.documents:
        documents_by_format[document.format] += 1
    flags_by_check: dict[str, int] = defaultdict(int)
    for flag in dataset.flags:
        flags_by_check[flag.check] += 1

    return Index(
        build=BuildOut(
            built_at=dataset.build.built_at.isoformat(),
            code_version=dataset.build.code_version,
            races=len(dataset.races),
            performances=len(dataset.performances),
            athletes=len(dataset.athletes),
            splits=len(dataset.splits),
            documents=len(dataset.documents),
            flags=len(dataset.flags),
        ),
        disciplines=[
            DisciplineOut(
                id=d.id,
                name=d.name,
                short_name=d.short_name,
                kind=d.kind.value,
                distance=float(d.distance),
                barriers={
                    sex.value: Barriers(
                        count=b.count,
                        first=float(b.first),
                        spacing=float(b.spacing),
                        height=float(b.height),
                    )
                    for sex, b in d.barriers.items()
                },
            )
            for d in dataset.disciplines
        ],
        series=[
            SeriesOut(id=s.id, name=s.name, short_name=s.short_name, kind=s.kind.value)
            for s in dataset.series
        ],
        competitions=[
            CompetitionOut(
                id=c.id,
                name=c.name,
                series=c.series,
                start_date=c.start_date.isoformat(),
                end_date=c.end_date.isoformat(),
                venue=c.venue.name,
                city=c.venue.city,
                country=c.venue.country,
                setting=c.setting.value,
                results_url=c.results_url,
                races=sum(race.competition == c.id for race in dataset.races),
                documents=documents_by_competition[c.id],
                declared_file=c.declared.file,
                declared_line=c.declared.line,
            )
            for c in sorted(dataset.competitions, key=lambda c: c.start_date, reverse=True)
        ],
        annotations=[
            AnnotationOut(value=printed, meaning=meaning)
            for printed, meaning in annotation_meanings(dataset).items()
            if meaning is not None
        ],
        formats=[
            FormatOut(
                id=f.id,
                version=f.version,
                name=f.name,
                publisher=f.publisher,
                description=f.description,
                kind=f.kind.value,
                module=_module_path(type(f)),
                documents=documents_by_format[f.id],
            )
            for f in FORMATS.values()
        ],
        checks=[
            CheckOut(
                id=c.id,
                severity=c.severity.value,
                suspect=c.suspect,
                title=c.title,
                explanation=c.explanation,
                flags=flags_by_check[c.id],
            )
            for c in CHECKS
        ],
        events=event_out,
        races=[
            RaceSummary(
                id=race.id,
                competition=race.competition,
                discipline=race.key.discipline,
                sex=race.key.sex.value,
                event=_event_of(race),
                round=race.key.round.value,
                heat=race.key.heat,
                setting=race.setting.value,
                date=race.date.value.isoformat(),
                title=race.title.value,
                athletes=len(perfs_by_race[race.id]),
                winner=winner(race.id),
                points=[
                    point.slug
                    for point in sorted(split_points[race.id], key=lambda p: p.order)
                    if point.kind is not PointKind.FINISH
                ],
                formats=sorted(split_formats[race.id]),
                flags=flag_count[race.id],
            )
            for race in sorted(dataset.races, key=lambda r: (r.date.value, r.id), reverse=True)
        ],
        athletes=[
            AthleteSummary(
                id=a.id,
                name=a.name,
                given_name=a.given_name,
                family_name=a.family_name,
                country=a.country,
                sex=a.sex.value,
                birth_date=str(a.birth_date) if a.birth_date else None,
                races=race_count[a.id],
                events=sorted(athlete_events[a.id]),
                bests=bests[a.id],
            )
            for a in dataset.athletes
        ],
        tables=[
            TableOut(
                name=table.name,
                description=table.description,
                rows=len(table.rows),
                columns=[
                    ColumnOut(name=c.name, type=c.type, description=c.description)
                    for c in table.columns
                ],
            )
            for table in build_tables(dataset)
        ],
    )


def _events(
    dataset: Dataset, flags_by_subject: dict[str, list[Flag]]
) -> Iterable[tuple[str, EventData]]:
    races = {race.id: race for race in dataset.races}
    documents = {document.id: document for document in dataset.documents}
    by_event: dict[str, list[Performance]] = defaultdict(list)
    for perf in dataset.performances:
        by_event[_event_of(races[perf.race])].append(perf)
    splits_by_perf: dict[str, list[Any]] = defaultdict(list)
    for split in dataset.splits:
        if split.point.kind is not PointKind.FINISH:
            splits_by_perf[split.performance].append(split)

    for event, perfs in sorted(by_event.items()):
        points = sorted(
            {split.point for perf in perfs for split in splits_by_perf[perf.id]},
            key=lambda point: point.order,
        )
        position = {point: index for index, point in enumerate(points)}
        rows = []
        for perf in perfs:
            splits = splits_by_perf[perf.id]
            # One series per performance: the document with the most splits.
            by_doc: dict[str, list[Any]] = defaultdict(list)
            for split in splits:
                by_doc[split.document].append(split)
            chosen = max(by_doc.values(), key=len) if by_doc else []
            values: list[float | None] = [None] * len(points)
            suspect: list[int] = []
            # A run whose result is out of line with its splits (a fall late in the race) is
            # left out of analyses whole: every split's share of that finish is untypical.
            whole = any(
                flag.suspect and flag.field == "result"
                for flag in flags_by_subject.get(perf.id, [])
            )
            for split in chosen:
                values[position[split.point]] = float(split.time.value)
                if whole or any(flag.suspect for flag in flags_by_subject.get(split.id, [])):
                    suspect.append(position[split.point])
            rows.append(
                EventPerformance(
                    id=perf.id,
                    race=perf.race,
                    athlete=perf.athlete,
                    place=perf.place.value if perf.place else None,
                    status=perf.status.value,
                    time=float(perf.time) if perf.time is not None else None,
                    format=documents[chosen[0].document].format if chosen else None,
                    splits=values,
                    suspect=sorted(suspect),
                )
            )
        first = races[perfs[0].race]
        yield (
            event,
            EventData(
                event=event,
                discipline=first.key.discipline,
                sex=first.key.sex.value,
                points=[_point(point) for point in points],
                performances=rows,
            ),
        )


def _race(dataset: Dataset, race: Race, flags_by_subject: dict[str, list[Flag]]) -> RaceData:
    documents = [d for d in dataset.documents if d.race == race.id]
    doc_index = {document.id: index for index, document in enumerate(documents)}
    sources = Sources([document.id for document in documents])
    performances = [p for p in dataset.performances if p.race == race.id]
    perf_ids = {p.id for p in performances}
    splits = [s for s in dataset.splits if s.performance in perf_ids]
    segments = [s for s in dataset.segments if s.performance in perf_ids]
    discipline = next(d for d in dataset.disciplines if d.id == race.key.discipline)
    points = sorted(
        {s.point for s in splits} | {s.end for s in segments} | {discipline.finish()},
        key=lambda point: point.order,
    )
    position = {point: index for index, point in enumerate(points)}

    subjects = {race.id, *perf_ids, *(s.id for s in splits), *(s.id for s in segments)}
    subjects |= {document.id for document in documents}
    flags = [
        _flag(flag) for subject in sorted(subjects) for flag in flags_by_subject.get(subject, [])
    ]

    def document_out(document: Document) -> DocumentOut:
        return DocumentOut(
            id=document.id,
            format=document.format,
            format_version=document.format_version,
            url=document.url,
            archive_url=document.archive_url,
            sha256=document.retrieval.sha256,
            size=document.retrieval.size,
            retrieved_at=document.retrieval.retrieved_at.isoformat(),
            retrieved_from=document.retrieval.retrieved_from,
            pages=document.pages,
            issued=sources.str(document.issued),
            revision=sources.str(document.revision),
            timing_by=sources.str(document.timing_by),
            declared_file=document.declared.file,
            declared_line=document.declared.line,
        )

    def performance_out(perf: Performance) -> RacePerformance:
        name = perf.name
        printed = SStr(v=name.span.text, s=sources.add(name))
        return RacePerformance(
            id=perf.id,
            athlete=perf.athlete,
            name=printed,
            given_name=name.value.given,
            family_name=name.value.family,
            country=sources.str(perf.country),
            birth_date=sources.str(perf.birth_date),
            bib=sources.str(perf.bib),
            lane=sources.int(perf.lane),
            place=sources.int(perf.place),
            status=perf.status.value,
            time=(
                SNum(v=float(perf.time), s=sources.add(perf.result))
                if perf.time is not None
                else None
            ),
            result_source=sources.add(perf.result),
            reaction_time=sources.num(perf.reaction_time),
            precise_time=sources.num(perf.precise_time),
            qualification=sources.str(perf.qualification),
            records=[SStr(v=tag.value, s=sources.add(tag)) for tag in perf.records],
            remarks=[SStr(v=remark.value, s=sources.add(remark)) for remark in perf.remarks],
            splits=[
                RaceSplit(
                    doc=doc_index[split.document],
                    point=position[split.point],
                    time=SNum(v=float(split.time.value), s=sources.add(split.time)),
                    rank=sources.int(split.rank),
                )
                for split in sorted(
                    (s for s in splits if s.performance == perf.id), key=lambda s: s.point.order
                )
            ],
            segments=[
                RaceSegment(
                    doc=doc_index[segment.document],
                    start=None
                    if segment.start.kind is PointKind.START
                    else position[segment.start],
                    end=position[segment.end],
                    time=SNum(v=float(segment.time.value), s=sources.add(segment.time)),
                )
                for segment in segments
                if segment.performance == perf.id
                # A stretch from a point no one was timed at (the last 400m of a 1500m) has
                # no place among the race's points; the tables keep it.
                and (segment.start.kind is PointKind.START or segment.start in position)
            ],
        )

    def sort_key(perf: Performance) -> tuple[int, int, float, str]:
        # Finishing order: by place where given (a photo finish can separate equal times),
        # then by time, to the thousandth where printed.
        order = {Status.FINISHED: 0, Status.DID_NOT_FINISH: 1, Status.DISQUALIFIED: 2}
        timed = perf.precise_time.value if perf.precise_time is not None else perf.time
        return (
            order.get(perf.status, 3),
            perf.place.value if perf.place is not None else 999,
            float(timed) if timed is not None else 0.0,
            perf.athlete,
        )

    documents_out = [document_out(document) for document in documents]
    performances_out = [performance_out(perf) for perf in sorted(performances, key=sort_key)]
    return RaceData(
        id=race.id,
        competition=race.competition,
        discipline=race.key.discipline,
        sex=race.key.sex.value,
        round=race.key.round.value,
        heat=race.key.heat,
        setting=race.setting.value,
        title=SStr(v=race.title.value, s=sources.add(race.title)),
        date=SStr(v=race.date.value.isoformat(), s=sources.add(race.date)),
        start_time=(
            SStr(v=race.start_time.value.strftime("%H:%M"), s=sources.add(race.start_time))
            if race.start_time
            else None
        ),
        wind=sources.num(race.wind),
        temperature=sources.num(race.temperature),
        humidity=sources.num(race.humidity),
        weather=sources.str(race.weather),
        documents=documents_out,
        points=[_point(point) for point in points],
        performances=performances_out,
        flags=flags,
        sources=sources.items,
    )
