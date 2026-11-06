"""Sign-ins that live queries read pages behind, such as the ASU sign-in. No Flask here.

A submodule registers a sign-in by name with two functions: usable(db, org_id) says whether the org saved a session,
and read(db, org_id, org_prefix, url) loads one page with it. A QuerySource with signin set uses read in place of a
plain fetch. read raises a ServiceError that the caller passes on.
"""

from collections.abc import Callable
from dataclasses import dataclass

from modules.submodules.types import Fetched


@dataclass(frozen=True)
class SignIn:
    usable: Callable[[object, int], bool]
    read: Callable[[object, int, str, str], Fetched]


SIGNINS: dict[str, SignIn] = {}


def register(
    name: str, usable: Callable[[object, int], bool], read: Callable[[object, int, str, str], Fetched]
) -> None:
    SIGNINS[name] = SignIn(usable, read)
