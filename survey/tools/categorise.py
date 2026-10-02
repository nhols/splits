"""Which survey category a World Athletics calendar entry belongs to.

World Athletics files most competitions under a group ("Wanda Diamond League Meeting", "Area
Indoor Championships", "National Senior Outdoor Championships") and gives every one a ranking
category (OW, DF, GW, GL, A-F; "Pre 2018" before its ranking began). The group decides the
category where it can; area and national championships are told apart by name and host country;
the rest by name, and what is left is an ordinary meeting of its ranking category.
"""

import re
from typing import Any

GROUPS = [
    ("Youth Olympic Games", None),
    ("Olympic Games", "olympic-games"),
    ("World Athletics Indoor Championships", "world-indoor-championships"),
    ("World Athletics Championships", "world-championships"),
    ("Wanda Diamond League", "diamond-league"),
    ("World Athletics Continental Tour – Gold", "continental-tour"),
    ("World Athletics Continental Tour – Silver", "continental-tour-silver"),
    ("World Athletics Continental Tour – Bronze", "continental-tour-bronze"),
    ("World Athletics Continental Tour – Challenger", "continental-tour-challenger"),
    ("World Athletics Indoor Tour – Silver", "world-indoor-tour-silver"),
    ("World Athletics Indoor Tour – Bronze", "world-indoor-tour-bronze"),
    ("World Athletics Indoor Tour – Challenger", "world-indoor-tour-challenger"),
    ("World Athletics Indoor Tour", "world-indoor-tour"),
    ("IAAF World Challenge", "iaaf-world-challenge"),
    ("World Athletics Continental Cup", "world-cup"),
    ("IAAF World Athletics Final", "iaaf-world-athletics-final"),
    ("IAAF Grand Prix Final", "iaaf-grand-prix-final"),
    ("Traditional International Meeting", "finnkampen"),
    ("FISU Events", "universiade"),
    ("Area Permit Indoor Meetings", "european-athletics-indoor-permit-meetings"),
    ("Area Permit Outdoor Meetings", "area-permit-meetings"),
]
"""World Athletics groups, most specific first (a group string can name several)."""

AREA = [
    (r"European.*Indoor|Indoor.*European", "european-indoor-championships"),
    (r"Asian.*Indoor", "asian-indoor-championships"),
    (r"South American.*Indoor", "south-american-indoor-championships"),
    (r"European", "european-championships"),
    (r"Asian Athletics|Asian Championships", "asian-championships"),
    (r"African", "african-championships"),
    (r"NACAC", "nacac-championships"),
    (r"South American", "south-american-championships"),
    (r"Oceania", "oceania-championships"),
    (r"Pan American", "pan-american-championships"),
]
GAMES = [
    (r"Asian Games", "asian-games"),
    (r"African Games|All-Africa", "african-games"),
    (r"Pan American Games", "pan-american-games"),
    (r"South American Games", "south-american-games"),
    (r"European Games", "european-games"),
    (r"Commonwealth Games", "commonwealth-games"),
    (r"Goodwill Games", "goodwill-games"),
    (r"Universiade|University Games", "universiade"),
    (r"Mediterran", "mediterranean-games"),
    (r"South ?East Asian Games|SEA Games", "southeast-asian-games"),
    (r"CAC Games|Central American and Caribbean Games", "cac-games"),
    (r"Centroamericanos|Central American Games", "central-american-games"),
    (r"Bolivarian", "bolivarian-games"),
    (r"Islamic Solidarity", "islamic-solidarity-games"),
    (r"Francophonie", "jeux-de-la-francophonie"),
    (r"Military World Games|CISM", "military-world-games"),
    (r"Pacific Mini Games", "pacific-mini-games"),
    (r"Pacific Games", "pacific-games"),
    (r"South Asian Games", "south-asian-games"),
    (r"Arab Games", "pan-arab-games"),
    (r"Games of the Small States", "games-of-the-small-states-of-europe"),
    (r"Micronesian Games", "micronesian-games"),
    (r"Island Games", "island-games"),
    (r"Lusophony|Lusofonia", "lusophony-games"),
    (r"Maccabiah", "maccabiah-games"),
]
REGIONAL = [
    (r"Balkan.*Indoor", "balkan-indoor-championships"),
    (r"Balkan", "balkan-championships"),
    (r"Nordic", "nordic-championships"),
    (r"West Asian", "west-asian-championships"),
    (r"Arab", "arab-championships"),
    (r"GCC", "gcc-championships"),
    (r"Small States", "championships-of-the-small-states-of-europe"),
    (r"Central Asian", "central-asian-championships"),
    (r"Oceania Cup", "oceania-cup"),
    (r"Ibero", "ibero-american-championships"),
    (r"CAC|Central American and Caribbean", "cac-championships"),
    (r"Central American", "central-american-championships"),
]
NAMES = [
    (r"Grand Slam Track", "grand-slam-track"),
    (r"\bAthlos\b", "athlos"),
    (r"Millrose", "millrose-games"),
    (r"Penn Relays", "penn-relays"),
    (r"Drake Relays", "drake-relays"),
    (r"Mt\.? SAC", "mt-sac-relays"),
    (r"Texas Relays", "texas-relays"),
    (r"Kansas Relays", "kansas-relays"),
    (r"Florida Relays", "florida-relays"),
    (r"NCAA Div(?:ision|\.)? I\b.*Indoor|NCAA Indoor", "ncaa-division-i-indoor"),
    (r"NCAA Div(?:ision|\.)? I\b|NCAA Outdoor", "ncaa-division-i-outdoor"),
    (
        r"Big Ten|Big 12|\bSEC\b|\bACC\b|Pac-1\d|NJCAA|NAIA|Conference|Division I[I]+|Div\. I[I]+|"
        r"Ivy League|Heptagonal|IC4A|Mountain West",
        "us-collegiate-conference-championships",
    ),
    (r"Olympic Trials|US Trials", "us-olympic-trials"),
    (r"Finnkampen|Sweden.?Finland|Finland.?Sweden", "finnkampen"),
    (
        r"European.*Team.*(First|Second|Third) League|European.*Team.*(Second|Third) Division",
        "european-team-competition-lower-divisions",
    ),
    (r"European (Team Championships|Athletics Team)", "european-team-championships"),
    (r"European Cup(?! Combined| Race Walk|.*Throw|.*10,?000)", "european-cup"),
    (r"European 10,?000", "european-10000m-cup"),
    (r"Ultimate Championship", "ultimate-championship"),
    (r"Athletics World Cup", "athletics-world-cup-london-2018"),
    (r"IAAF World Cup", "world-cup"),
]
NATIONAL = {
    "USA": ("usatf-outdoor-championships", "usatf-indoor-championships"),
    "JAM": ("jamaican-championships", None),
    "KEN": ("kenyan-championships", None),
    "ETH": ("ethiopian-championships", None),
    "RUS": ("russian-championships", "russian-indoor-championships"),
    "GBR": ("british-championships", "british-indoor-championships"),
    "CHN": ("chinese-championships", None),
    "JPN": ("japan-championships", None),
    "GER": ("german-championships", "german-indoor-championships"),
    "FRA": ("french-championships", "french-indoor-championships"),
    "ITA": ("italian-championships", "italian-indoor-championships"),
    "ESP": ("spanish-championships", "spanish-indoor-championships"),
    "AUS": ("australian-championships", None),
    "CAN": ("canadian-championships", None),
    "NZL": ("new-zealand-championships", None),
    "SWE": ("swedish-championships", None),
    "NOR": ("norwegian-championships", None),
    "FIN": ("finnish-championships", None),
    "NED": ("dutch-championships", None),
    "POL": ("polish-championships", None),
    "CZE": ("czech-championships", None),
    "CUB": ("cuban-championships", None),
    "NGR": ("nigerian-championships", None),
    "BAH": ("bahamas-championships", None),
    "TTO": ("trinidad-championships", None),
    "RSA": ("south-african-championships", None),
    "BEL": ("belgian-championships", None),
    "DEN": ("danish-championships", None),
    "GRE": ("greek-championships", None),
    "HUN": ("hungarian-championships", None),
    "SUI": ("swiss-championships", None),
    "AUT": ("austrian-championships", None),
    "POR": ("portuguese-championships", None),
    "ROU": ("romanian-championships", None),
    "EST": ("estonian-championships", None),
    "LAT": ("latvian-championships", None),
    "LTU": ("lithuanian-championships", None),
    "BUL": ("bulgarian-championships", None),
    "MEX": ("mexican-championships", None),
    "BRA": ("brazilian-championships", None),
    "ARG": ("argentine-championships", None),
    "TUR": ("turkish-championships", None),
    "IND": ("indian-championships", None),
    "UGA": ("ugandan-championships", None),
    "ALG": ("algerian-championships", None),
    "MAR": ("moroccan-championships", None),
    "BOT": ("botswana-championships", None),
    "QAT": ("qatari-championships", None),
    "BRN": ("bahraini-championships", None),
    "BLR": ("belarusian-championships", None),
    "CRO": ("croatian-championships", None),
    "UKR": ("ukrainian-championships", None),
    "TUN": ("tunisian-championships", None),
    "IRL": ("irish-championships", None),
}
"""National championships by host country: (outdoor, indoor) category ids."""

AGE_GROUP = re.compile(r"\bU1\d\b|\bU2\d\b|Junior|Youth|Masters|Veteran|School|Kids", re.I)
"""Age-group competitions, out of scope whatever their group."""

MEETING_TIERS = {
    "ow": "elite-core",
    "df": "elite-core",
    "gw": "elite-core",
    "gl": "elite-secondary",
    "a": "elite-secondary",
    "b": "sub-elite",
    "c": "sub-elite",
    "d": "sub-elite",
    "e": "sub-elite",
    "f": "sub-elite",
    "pre-2018": "sub-elite",
}
"""The scope of an ordinary meeting by its World Athletics ranking category."""


def country(venue: str | None) -> str | None:
    found = re.search(r"\(([A-Z]{3})\)\s*$", venue or "")
    return found[1] if found else None


def _first(rules: list[tuple[str, str]], text: str) -> str | None:
    return next((category for pattern, category in rules if re.search(pattern, text, re.I)), None)


def category(entry: dict[str, Any]) -> str:
    """The category id of a World Athletics calendar entry. Entries that fit no named category
    are ordinary meetings: ``wa-meeting-<ranking category>``, indoor or outdoor."""
    group = entry.get("competitionGroup") or ""
    name = entry["name"]
    if AGE_GROUP.search(name):
        return "national-age-group-championships"
    for marker, found in GROUPS:
        if marker in group:
            if found is None:
                return "youth-olympic-games"
            return found
    if "Area Indoor Championships" in group or "Area Senior Outdoor Championships" in group:
        return _first(AREA, name) or "area-championships-other"
    if "Area Senior Games" in group:
        return _first(GAMES, name) or "area-games-other"
    if "Area Regional Senior Championships" in group:
        return _first(GAMES, name) or _first(REGIONAL, name) or "regional-championships-other"
    host = country(entry.get("venue"))
    if "National Senior Indoor Championships" in group:
        indoor = NATIONAL.get(host or "", (None, None))[1]
        return indoor or "other-national-indoor-championships"
    if "National Senior" in group and "Championships" in group:
        return NATIONAL.get(host or "", (None, None))[0] or "other-national-championships"
    named = _first(NAMES, name) or _first(GAMES, name)
    if named:
        return named
    if re.search(r"Championships", name) and not re.search(
        r"U1\d|U2\d|Junior|Youth|Masters|School|Universit|Student|College|Combined|\bCE\b|Walk|"
        r"Cross Country|Throw",
        name,
        re.I,
    ):
        if re.search(r"Regional|Melanesian|Polynesian|Micronesian|Area", name):
            return "regional-championships-other"
        outdoor, indoor = NATIONAL.get(host or "", (None, None))
        if "Indoor" in name:
            return indoor or "other-national-indoor-championships"
        return outdoor or "other-national-championships"
    tier = entry["rankingCategory"].replace("Pre 2018", "pre-2018").lower()
    return f"wa-meeting-{tier}"
