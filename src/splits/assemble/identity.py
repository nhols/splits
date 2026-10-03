"""Athlete identity: deciding which printed names are the same person.

Where World Athletics' results say which of its athletes a row names (see
:mod:`splits.assemble.world_athletics`), that decides: rows naming the same World Athletics
athlete are one athlete, whatever names and countries they print, and the athlete ID is the
slug of the name World Athletics gives the athlete now (``georgia-hunter-bell``), or the ID of
the rule that names them. A row World Athletics does not identify is the athlete its printed
name and country are elsewhere linked to, when there is exactly one.

Otherwise the default rule applies. It is deliberately conservative. Two appearances are the
same athlete when their given name, family name and country are equal, ignoring case, accents
and punctuation, whatever order the document printed them in. So "WARHOLM Karsten NOR" and
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
        self._by_profile: dict[int, AthleteRule] = {}
        for rule in rules:
            if rule.world_athletics is not None:
                if rule.world_athletics in self._by_profile:
                    raise IdentityError(
                        f"World Athletics athlete {rule.world_athletics} is claimed by rules "
                        f"{self._by_profile[rule.world_athletics].id} and {rule.id}"
                    )
                self._by_profile[rule.world_athletics] = rule
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
        self._profiles_of: dict[str, set[int]] = defaultdict(set)
        self._names: dict[int, PersonName] = {}

    def learn(self, names: Iterable[tuple[PersonName, str | None]]) -> None:
        """Every name the documents print, so that initials can be matched to full names."""
        for name, country in names:
            if country is not None and not INITIALS.fullmatch(name.given):
                self._full[(fold(name.family), country)].add(name.given)

    def learn_profiles(
        self, links: Iterable[tuple[PersonName, str | None, int, PersonName]]
    ) -> None:
        """Every row World Athletics identifies: its printed name and country, the World
        Athletics athlete, and the name World Athletics gives them now (the last given for an
        athlete stands). Call after :meth:`learn`."""
        for name, country, profile, current in links:
            self._names[profile] = current
            if country is not None:
                self._profiles_of[self._key(name, country)].add(profile)
        for profile in {p for profiles in self._profiles_of.values() for p in profiles}:
            self._rule_of_profile(profile)  # fail early on contradicting rules

    def _key(self, name: PersonName, country: str) -> str:
        name = self._full_name(name, country)
        return name_key(name.given, name.family, country)

    def _full_name(self, name: PersonName, country: str) -> PersonName:
        if name_key(name.given, name.family, country) not in self._rules:
            return self._expand(name, country)
        return name

    def _rule_of_profile(self, profile: int) -> AthleteRule | None:
        """The rule that names a World Athletics athlete: by its ID, or by the printed names
        of the rows World Athletics identifies as theirs."""
        named = {
            self._rules[key].id: self._rules[key]
            for key, profiles in self._profiles_of.items()
            if profile in profiles and key in self._rules
        }
        declared = self._by_profile.get(profile)
        if declared is not None:
            named.pop(declared.id, None)
            if named:
                raise IdentityError(
                    f"World Athletics athlete {profile} is declared by rule {declared.id} but "
                    f"also printed under names of rule(s) {sorted(named)}"
                )
            return declared
        if len(named) > 1:
            raise IdentityError(
                f"World Athletics athlete {profile} is printed under names of several rules: "
                f"{sorted(named)}; merge them into one"
            )
        rule = next(iter(named.values()), None)
        if rule is not None and rule.world_athletics not in (None, profile):
            raise IdentityError(
                f"rule {rule.id} declares World Athletics athlete {rule.world_athletics}, but "
                f"World Athletics' results identify its names as athlete {profile}"
            )
        return rule

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

    def resolve(
        self, name: PersonName, country: str | None, profile: int | None = None
    ) -> Identity:
        """The athlete a row names: the World Athletics athlete it was linked to, if any."""
        if country is None:
            raise IdentityError(f"cannot identify {name.given} {name.family}: no country")
        name = self._full_name(name, country)
        key = name_key(name.given, name.family, country)
        if profile is None:
            linked = self._profiles_of.get(key, set())
            if len(linked) > 1:
                raise IdentityError(
                    f"{name.given} {name.family} ({country}) is printed for World Athletics "
                    f"athletes {sorted(linked)}; a row World Athletics does not identify cannot "
                    "be told apart: add a rule to catalog/athletes.yaml"
                )
            profile = next(iter(linked), None)
            if profile is None and key in self._rules:
                profile = self._rules[key].world_athletics
        if profile is not None:
            return self._profile_identity(profile)
        rule = self._rules.get(key)
        if rule is not None:
            identity = Identity(rule.id, rule.declared)
        else:
            identity = Identity(athlete_id(slugify(f"{name.given} {name.family}")), None)
        self._claimed[identity.athlete].add(key if rule is None else f"rule:{rule.id}")
        return identity

    def _profile_identity(self, profile: int) -> Identity:
        rule = self._rule_of_profile(profile)
        if rule is not None:
            identity = Identity(rule.id, rule.declared)
            self._claimed[rule.id].add(f"rule:{rule.id}")
            return identity
        current = self._names.get(profile)
        if current is None:
            raise IdentityError(f"World Athletics athlete {profile} has no name")
        athlete = athlete_id(slugify(f"{current.given} {current.family}"))
        self._claimed[athlete].add(f"world-athletics:{profile}")
        return Identity(athlete, None)

    def profile_of(self, athlete: AthleteId) -> int | None:
        """The World Athletics athlete a rule declares for ``athlete``, if any."""
        for profile, rule in self._by_profile.items():
            if rule.id == athlete:
                return profile
        return None

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
    if part.endswith(".") and part[:-1].isalpha():  # "ST." in "ST. PIERRE"
        return _display_part(part[:-1]) + "."
    if not part.isalpha():
        return part
    last_lower = max((i for i, char in enumerate(part) if char.islower()), default=-1)
    if last_lower >= 0:  # "McMASTER": keep "Mc", case the rest
        return part[: last_lower + 1] + part[last_lower + 1 :].capitalize()
    if re.fullmatch(r"MC[A-Z]{2,}", part):
        return "Mc" + part[2:].capitalize()
    return part.capitalize()
