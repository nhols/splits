"""The base class every record in the data model derives from."""

from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    """An immutable, strictly typed value.

    * ``frozen``: records never change after construction; pipeline stages build new ones.
    * ``extra="forbid"``: unknown fields are an error, so a typo in a data file cannot hide.
    * ``strict``: no silent coercion (``"1.5"`` is not a number). Code that reads text formats
      (YAML, JSON) opts into lax parsing explicitly, at that boundary only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
