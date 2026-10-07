"""One coding fixture and the reference result the scorer compares."""

from dataclasses import dataclass


@dataclass
class Case:
    data: dict
    expected: object
