"""World Athletics' results of a competition, as its public API answers, pinned like a document.

World Athletics lists every result with the athlete it belongs to: their profile ID, their name
as it is now (results are renamed when an athlete's name changes) and their birth date. The
answer for every day of the competition is stored as one JSON document, its keys sorted, so the
same results always give the same bytes and a change (a renamed athlete, a corrected result) is
detected as a change.
"""

import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from splits.acquire.store import sha256_of
from splits.model import Retrieval

ENDPOINT = "https://graphql-prod-4896.edge.aws.worldathletics.org/graphql"
API_KEY = "da2-kw72k7ccfrcl7m2bzvkejgd44a"
"""The public key the worldathletics.org site itself sends (found in its JavaScript)."""
PAUSE_SECONDS = 0.5

QUERY = """query($competition: Int, $day: Int) {
  getCalendarCompetitionResults(competitionId: $competition, day: $day) {
    competition { name startDate endDate venue }
    options { days { date day } }
    eventTitles { eventTitle events { event eventId gender races { date race raceNumber
      results { place mark nationality
        competitor { name urlSlug birthDate } } } } }
  }
}"""


def fetch_results(client: httpx.Client, competition: int) -> tuple[Retrieval, bytes]:
    """Every day's results of a World Athletics competition, as one JSON document."""
    first = _query(client, competition, None)
    days = [option["day"] for option in first["options"]["days"]]
    answers = [first] + [_query(client, competition, day) for day in days[1:]]
    document = {"competition": competition, "endpoint": ENDPOINT, "query": QUERY, "days": answers}
    content = (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()
    retrieval = Retrieval(
        sha256=sha256_of(content),
        size=len(content),
        media_type="application/json",
        retrieved_at=datetime.now(UTC).replace(microsecond=0),
        retrieved_from=ENDPOINT,
    )
    return retrieval, content


def _query(client: httpx.Client, competition: int, day: int | None) -> dict[str, Any]:
    """One day's results (the first day's when ``day`` is ``None``). The API answers a
    transient failure with ``null`` data, so that is retried."""
    for attempt in range(4):
        time.sleep(PAUSE_SECONDS * (1 + 4 * attempt))
        response = client.post(
            ENDPOINT,
            json={"query": QUERY, "variables": {"competition": competition, "day": day}},
            headers={"x-api-key": API_KEY},
        )
        response.raise_for_status()
        data = (response.json().get("data") or {}).get("getCalendarCompetitionResults")
        if data:
            return dict(data)
    raise ValueError(f"World Athletics did not answer for competition {competition}, day {day}")
