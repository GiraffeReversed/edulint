from edulint.linters import Linter
from dataclasses import dataclass, field, fields
from dataclasses_json import dataclass_json, config
from marshmallow import fields as mm_fields
from typing import Optional, Dict, Union, List

ProblemJson = Dict[str, Union[str, int]]


@dataclass_json
@dataclass
class Problem:
    source: Linter = field(metadata=config(
        encoder=Linter.to_name,
        decoder=Linter.from_name,
        mm_field=mm_fields.Str()
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

    def has_value(self, attr: str) -> bool:
        val = getattr(self, attr)
        return val is not None \
            and (not isinstance(val, str) or val) \
            and (not isinstance(val, int) or val >= 0)

    def __repr__(self) -> str:
        def get_attrvals() -> List[str]:
            result = []
            for f in fields(Problem):
                attr = f.name
                if self.has_value(attr):
                    result.append(f"{attr}={getattr(self, attr)}")
            return result

        return f"Problem({', '.join(get_attrvals())})"

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.code} {self.text}"
