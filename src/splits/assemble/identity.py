"""Athlete identity: deciding which printed names are the same person.

The default rule is deliberately conservative. Two appearances are the same athlete when
their given name, family name and country are equal, ignoring case, accents and punctuation,
whatever order the document printed them in. So "WARHOLM Karsten NOR" and
"Karsten WARHOLM NOR" match, and "MAGI Rasmus EST" matches "Rasmus MÄGI EST". The athlete ID
is the slug of the name: ``karsten-warholm``.

A given name printed as initials, as results sometimes shorten it to fit a column
(``JEFFERSON-WOODEN M``, ``MUDIYANSELAGE YA``), is the athlete of that family name and country
whose given names start with those initials, when there is exactly one such athlete among
everyone the documents name; otherwise the initials stand as printed.

Anything the default cannot decide is surfaced as an error rather than guessed: if two
different people would get the same ID, or one person appears under two names or countries,
the build asks for a rule in ``catalog/athletes.yaml``.
"""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from splits.formats.parse import PARTICLES
from splits.model import AthleteId, AthleteRule, CatalogRef, PersonName
from splits.model.ids import ascii_fold, athlete_id, slugify

INITIALS = re.compile(r"(?:[A-Z]\.? ?){1,3}")
"""A given name printed as one to three initials: ``M``, ``YA``, ``J.``."""


class IdentityError(ValueError):
    """Printed names cannot be resolved to athletes without a curated rule."""


def fold(text: str) -> str:
    """Case-, accent- and punctuation-insensitive form: ``"HUDSON-SMITH"`` -> ``"hudson smith"``."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", ascii_fold(text).lower()).split())


def name_key(given: str, family: str, country: str) -> str:
    return f"{fold(family)}|{fold(given)}|{country}"


@dataclass(frozen=True)
class Identity:
    athlete: AthleteId
    rule: CatalogRef | None
    """The rule that decided the identity, if the default did not."""


class IdentityResolver:
    def __init__(self, rules: tuple[AthleteRule, ...]) -> None:
        self._rules: dict[str, AthleteRule] = {}
        for rule in rules:
            names = [(rule.given, rule.family, rule.country)] + [
                (variant.given, variant.family, variant.country or rule.country)
                for variant in rule.also_known_as
            ]
            for given, family, country in names:
                key = name_key(given, family, country)
                if key in self._rules and self._rules[key].id != rule.id:
                    raise IdentityError(
                        f"{given} {family} ({country}) is claimed by rules "
                        f"{self._rules[key].id} and {rule.id}"
                    )
                self._rules[key] = rule
        self._claimed: dict[AthleteId, set[str]] = defaultdict(set)
        self._full: dict[tuple[str, str], set[str]] = defaultdict(set)

    def learn(self, names: Iterable[tuple[PersonName, str | None]]) -> None:
        """Every name the documents print, so that initials can be matched to full names."""
        for name, country in names:
            if country is not None and not INITIALS.fullmatch(name.given):
                self._full[(fold(name.family), country)].add(name.given)

    def _expand(self, name: PersonName, country: str) -> PersonName:
        """The full name that initials stand for, if exactly one athlete fits them."""
        if not INITIALS.fullmatch(name.given):
            return name
        letters = name.given.replace(".", "").replace(" ", "").upper()
        fits = [
            given
            for given in self._full.get((fold(name.family), country), ())
            if "".join(word[0] for word in given.split()).upper().startswith(letters)
        ]
        return (
            PersonName(given=fits[0], family=name.family, local=name.local)
            if len(fits) == 1
            else name
        )

    def resolve(self, name: PersonName, country: str | None) -> Identity:
        if country is None:
            raise IdentityError(f"cannot identify {name.given} {name.family}: no country")
        if name_key(name.given, name.family, country) not in self._rules:
            name = self._expand(name, country)
        key = name_key(name.given, name.family, country)
        rule = self._rules.get(key)
        if rule is not None:
            identity = Identity(rule.id, rule.declared)
        else:
            identity = Identity(athlete_id(slugify(f"{name.given} {name.family}")), None)
        self._claimed[identity.athlete].add(key if rule is None else f"rule:{rule.id}")
        return identity

    def check(self) -> None:
        """Fail if one ID was claimed by different people (distinct names or countries)."""
        clashes = {athlete: keys for athlete, keys in self._claimed.items() if len(keys) > 1}
        if clashes:
            lines = [
                f"  {athlete}: {' / '.join(sorted(keys))}" for athlete, keys in clashes.items()
            ]
            raise IdentityError(
                "these athlete IDs would be shared by appearances that differ in name or "
                "country; add rules to catalog/athletes.yaml saying which are the same "
                "person:\n" + "\n".join(sorted(lines))
            )


def display_family(printed: list[str]) -> str:
    """A readable family name from its printed spellings. Documents print family names in
    capitals; a spelling with some lower case (``McMASTER``, ``dos SANTOS``) keeps that
    information, so it is preferred."""
    mixed = [text for text in printed if any(char.islower() for char in text)]
    return " ".join(_display_token(token) for token in (mixed or printed)[0].split())


def _display_token(token: str) -> str:
    if token.lower() in PARTICLES and not token.isupper():
        return token  # "dos", "van", "De" as printed
    parts = re.split(r"([-'’])", token)
    return "".join(_display_part(part) for part in parts)


def _display_part(part: str) -> str:
    if not part.isalpha():
        return part
    last_lower = max((i for i, char in enumerate(part) if char.islower()), default=-1)
    if last_lower >= 0:  # "McMASTER": keep "Mc", case the rest
        return part[: last_lower + 1] + part[last_lower + 1 :].capitalize()
    if re.fullmatch(r"MC[A-Z]{2,}", part):
        return "Mc" + part[2:].capitalize()
    return part.capitalize()
