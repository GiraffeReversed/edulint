from edulint.linters import Linter
from dataclasses import dataclass, field, fields
from dataclasses_json import dataclass_json, config
from marshmallow import fields as mm_fields
from typing import Optional, Dict, Union, List

ProblemJson = Dict[str, Union[str, int]]


@dataclass_json
@dataclass
class Problem:
    source: Linter = field(
        metadata=config(encoder=Linter.to_name, decoder=Linter.from_name, mm_field=mm_fields.Str())
    )
    enabled_by: Optional[str]
    path: str
    line: int
    column: int
    code: str
    text: str
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    symbol: Optional[str] = None

    def set_source(self, v: Linter) -> "Problem":
        self.source = v
        return self

    def set_enabled_by(self, v: Optional[str]) -> "Problem":
        self.enabled_by = v
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
        return (
            val is not None
            and (not isinstance(val, str) or bool(val))
            and (not isinstance(val, int) or val >= 0)
        )

    def __repr__(self) -> str:
        def get_attrvals() -> List[str]:
            result = []
            for f in fields(Problem):
                attr = f.name
                if self.has_value(attr):
                    attrval = getattr(self, attr)
                    attrval = attrval if not isinstance(attrval, str) else f'"{attrval}"'
                    result.append(f"{attr}={attrval}")
            return result

        return f"Problem({', '.join(get_attrvals())})"

    def __str__(self) -> str:
        enabler_str = f" [{self.enabled_by}]" if self.enabled_by is not None else ""
        return f"{self.path}:{self.line}:{self.column}: {self.code} {self.text}{enabler_str}"
