from edulint.linters import Linter
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from marshmallow import fields
from typing import Optional, Dict, Union

ProblemJson = Dict[str, Union[str, int]]


@dataclass_json
@dataclass
class Problem:
    source: Linter = field(metadata=config(
        encoder=Linter.to_name,
        decoder=Linter.from_name,
        mm_field=fields.Str()
    ))
    path: str
    line: int
    column: int
    code: str
    text: str
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def set_source(self, v: Linter) -> "Problem":
        self.source = v
        return self

    def set_path(self, v: str) -> "Problem":
        self.path = v
        return self

    def set_line(self, v: int) -> "Problem":
        self.line = v
        return self

    def set_column(self, v: int) -> "Problem":
        self.column = v
        return self

    def set_code(self, v: str) -> "Problem":
        self.code = v
        return self

    def set_text(self, v: str) -> "Problem":
        self.text = v
        return self

    def set_end_line(self, v: Optional[int]) -> "Problem":
        self.end_line = v
        return self

    def set_end_column(self, v: Optional[int]) -> "Problem":
        self.end_column = v
        return self

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: " \
               f"{self.code} {self.text}"
