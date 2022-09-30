from edulint.config.arg import ProcessedArg, UnprocessedArg, ImmutableArg
from edulint.options import UnionT, ImmutableT, Option, TakesVal, OptionParse, get_option_parses, get_name_to_option
from edulint.config.config_translations import get_config_translations, get_ib111_translations, Translation
from typing import Dict, List, Optional, Tuple, Iterator
from dataclasses import dataclass
from argparse import Namespace
import re
import sys
import shlex


@dataclass(frozen=True)
class Config:

    config: Tuple[ImmutableArg]

    @staticmethod
    def to_immutable(v: UnionT) -> ImmutableT:
        return v if not isinstance(v, list) else tuple(v)

    def __init__(self, config: Optional[List[ProcessedArg]] = None,
                 option_parses: Dict[Option, OptionParse] = get_option_parses()) -> None:
        config = config if config is not None else []
        wip_config: List[Optional[ImmutableArg]] = [None for _ in Option]

        for arg in config:
            assert wip_config[int(arg.option)] is None
            wip_config[int(arg.option)] = ImmutableArg(arg.option, self.to_immutable(arg.val))

        object.__setattr__(self, "config", tuple([arg if arg is not None else ImmutableArg(
            o, self.to_immutable(option_parses[o].default)) for o, arg in zip(Option, wip_config)]))

    def __str__(self) -> str:
        return f"Config({', '.join(arg.option.name + '=' + str(arg.val) for arg in self.config)})"

    def __getitem__(self, option: Option) -> ImmutableArg:
        return self.config[int(option)]

    def __contains__(self, option: Option) -> bool:
        return self[option] is not None

    def __iter__(self) -> Iterator[ImmutableArg]:
        return filter(lambda x: x is not None, self.config.__iter__())


def extract_args(filename: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint:\s*", re.IGNORECASE)
    ib111_re = re.compile(r"\s*from\s+ib111\s+import\s+week_(\d+)", re.IGNORECASE)

    result: List[str] = []
    with open(filename) as f:
        for i, line in enumerate(f):
            line = line.strip()

            edmatch = edulint_re.match(line)
            if edmatch:
                raw_args = line[edmatch.end():]
                result.extend(shlex.split(raw_args))

            ibmatch = ib111_re.match(line)
            if ibmatch:
                result.append(f"{Option.IB111_WEEK.to_name()}={ibmatch.group(1)}")

    return result


def parse_args(args: List[str], option_parses: Dict[Option, OptionParse]) -> List[UnprocessedArg]:
    name_to_option = get_name_to_option(option_parses)

    def get_name_val(arg: str) -> Tuple[str, Optional[str]]:
        if "=" in arg:
            name, val = arg.split("=", 1)
            return name, val
        return arg, None

    result: List[UnprocessedArg] = []
    for arg in args:
        name, val = get_name_val(arg)
        option = name_to_option.get(name)

        if option is None:
            print(f"edulint: unrecognized option {name}", file=sys.stderr)
        else:
            option_parse = option_parses[option]
            if option_parse.takes_val == TakesVal.YES and val is None:
                print(f"edulint: option {name} takes an argument but none was supplied", file=sys.stderr)
            elif option_parse.takes_val == TakesVal.NO and val is not None:
                print(f"edulint: option {name} takes no argument but {val} was supplied", file=sys.stderr)
            else:
                result.append(UnprocessedArg(option, val))

    return result


def fill_in_val(arg: UnprocessedArg, translation: List[str]) -> List[str]:
    result = []
    for t in translation:
        if "<val>" in t:
            assert isinstance(arg.val, str)
            result.append(t.replace("<val>", arg.val))
        else:
            result.append(t)
    return result


def combine_and_translate(
        args: List[UnprocessedArg],
        option_parses: Dict[Option, OptionParse],
        config_translations: Dict[Option, Translation],
        ib111_translations: List[Translation]) -> Config:

    def combine(option_vals: List[UnionT], option: Option, val: Optional[str]) -> None:
        parse = option_parses[option]
        old_val = option_vals[int(option)]
        option_vals[int(option)] = parse.combine(old_val, parse.convert(val))

    def apply_translation(option_vals: List[UnionT], translated: Translation) -> None:
        translated_option = translated.for_linter.to_option()
        for val in translated.vals:
            combine(option_vals, translated_option, val)

    option_vals = [option_parses[o].default for o in Option]

    for arg in args:
        combine(option_vals, arg.option, arg.val)

        translated = config_translations.get(arg.option)
        if translated is not None:
            apply_translation(option_vals, translated)

    ib111_week = option_vals[int(Option.IB111_WEEK)]
    if ib111_week is not None:
        assert isinstance(ib111_week, int)
        if 0 <= ib111_week < len(ib111_translations):
            apply_translation(option_vals, ib111_translations[ib111_week])
        else:
            print(f"edulint: option {Option.IB111_WEEK.to_name()} has value {ib111_week} which is invalid;"
                  f"allowed values are 0 to {len(ib111_translations)}", file=sys.stderr)

    return Config([ProcessedArg(o, v) for o, v in zip(Option, option_vals) if v is not None])


def get_config(
        filename: str, cmd_args: List[str],
        option_parses: Dict[Option, OptionParse] = get_option_parses(),
        config_translations: Dict[Option, Translation] = get_config_translations(),
        ib111_translation: List[Translation] = get_ib111_translations()) -> Config:
    extracted = extract_args(filename) + cmd_args
    parsed = parse_args(extracted, option_parses)
    return combine_and_translate(parsed, option_parses, config_translations, ib111_translation)


def get_cmd_args(args: Namespace) -> List[str]:
    return [s for arg in args.options for s in shlex.split(arg)]
