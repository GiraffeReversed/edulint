from edulint.config.arg import ProcessedArg, UnprocessedArg, ImmutableArg
from edulint.linters import Linter
from edulint.options import (
    UnionT,
    ImmutableT,
    Option,
    BASE_CONFIG,
)
from edulint.option_parses import (
    OptionParse,
    get_option_parses,
    get_name_to_option,
    TakesVal,
    Combine,
)
from edulint.config.file_config import load_toml_file
from edulint.config.config_translations import (
    get_config_translations,
    get_ib111_translations,
    Translation,
)
from typing import Dict, List, Optional, Tuple, Iterator, Any, cast

from dataclasses import dataclass
from argparse import Namespace
import re
import sys
import shlex


class Config:
    config: List[Optional[ProcessedArg]]

    def _convert(self, args: List[UnprocessedArg]) -> List[ProcessedArg]:
        return [
            ProcessedArg(arg.option, self.option_parses[arg.option].convert(arg.val))
            for arg in args
        ]

    def _translate(self, args: List[Optional[ProcessedArg]]) -> List[Optional[ProcessedArg]]:
        def apply_translation(
            result: List[Optional[ProcessedArg]], translated: Translation
        ) -> None:
            translated_option = translated.for_linter.to_option()
            parse = self.option_parses[translated_option]
            for val in translated.vals:
                result.append(ProcessedArg(translated_option, parse.convert(val)))

        result: List[Optional[ProcessedArg]] = []
        for arg in args:
            if arg is None:
                continue
            result.append(arg)

            translated = self.config_translations.get(arg.option)
            if translated is not None and arg.val not in (False, None):
                apply_translation(result, translated)

        for arg in args:
            if arg is not None and arg.option == Option.IB111_WEEK and arg.val is not None:
                ib111_week = arg.val
                assert isinstance(ib111_week, int)
                if 0 <= ib111_week < len(self.ib111_translations):
                    apply_translation(result, self.ib111_translations[ib111_week])
                else:
                    print(
                        f"edulint: option {Option.IB111_WEEK.to_name()} has value {ib111_week} which is invalid;"
                        f"allowed values are 0 to {len(self.ib111_translations)}",
                        file=sys.stderr,
                    )

        return result

    def _combine(
        self, args: List[Optional[ProcessedArg]], allowed_combines: Tuple[Combine, ...] = ()
    ) -> List[Optional[ProcessedArg]]:
        indices: Dict[Option, int] = {}
        results: List[Optional[ProcessedArg]] = []
        for new_arg in args:
            if new_arg is None:
                continue
            parse = self.option_parses[new_arg.option]
            if parse.combine in allowed_combines and new_arg.option in indices:
                old_index = indices[new_arg.option]
                old_arg = results[old_index]
                assert old_arg is not None

                results.append(
                    ProcessedArg(new_arg.option, parse.combine(old_arg.val, new_arg.val))
                )
                results[old_index] = None
            else:
                results.append(new_arg)
            indices[new_arg.option] = len(results) - 1

        return results

    def __init__(
        self,
        config: Optional[List[UnprocessedArg]] = None,
        option_parses: Dict[Option, OptionParse] = get_option_parses(),
        config_translations: Dict[Option, Translation] = get_config_translations(),
        ib111_translations: List[Translation] = get_ib111_translations(),
    ) -> None:
        config = config if config is not None else []
        self.option_parses = option_parses
        self.config_translations = config_translations
        self.ib111_translations = ib111_translations

        converted = self._convert(config)
        self.config = self._combine(converted, allowed_combines=(Combine.REPLACE,))  # type: ignore

    @staticmethod
    def combine(lt: "Config", rt: "Config") -> "Config":
        assert lt.option_parses == rt.option_parses
        assert lt.config_translations == rt.config_translations
        assert lt.ib111_translations == rt.ib111_translations
        new = Config(
            option_parses=lt.option_parses,
            config_translations=lt.config_translations,
            ib111_translations=lt.ib111_translations,
        )
        new.config = new._combine(lt.config + rt.config, allowed_combines=(Combine.REPLACE,))
        return new

    def __str__(self) -> str:
        return f"Config({', '.join(arg.option.name + '=' + str(arg.val) for arg in self.config if arg is not None)})"

    def get_last_value(self, option: Option, use_default: bool) -> Optional[UnionT]:
        assert self.option_parses[option].combine == Combine.REPLACE
        for arg in reversed(self.config):
            if arg is not None and arg.option == option:
                return arg.val
        return None if not use_default else self.option_parses[option].default

    @staticmethod
    def _to_immutable(val: UnionT) -> ImmutableT:
        return val if not isinstance(val, list) else tuple(val)

    def to_immutable(self) -> "ImmutableConfig":
        translated = self._translate(self.config)
        combined = self._combine(translated, allowed_combines=(Combine.REPLACE, Combine.EXTEND))

        ordered_args = [ProcessedArg(o, self.option_parses[o].default) for o in Option]
        for arg in combined:
            if arg is None:
                continue
            ordered_args[int(arg.option)] = arg

        return ImmutableConfig(
            tuple(ImmutableArg(o, self._to_immutable(ordered_args[int(o)].val)) for o in Option)
        )


@dataclass(frozen=True)
class ImmutableConfig:
    config: Tuple[ImmutableArg, ...]

    def __str__(self) -> str:
        return f"ImmutableConfig({', '.join(arg.option.name + '=' + str(arg.val) for arg in self.config)})"

    def __getitem__(self, option: Option) -> ImmutableT:
        return self.config[int(option)].val

    def __contains__(self, option: Option) -> bool:
        return self[option] is not None

    def __iter__(self) -> Iterator[ImmutableArg]:
        return filter(lambda x: x is not None, self.config.__iter__())


# %% components


def extract_args(filename: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint:\s*", re.IGNORECASE)
    ib111_re = re.compile(r"\s*from\s+ib111\s+import\s+week_(\d+)", re.IGNORECASE)

    result: List[str] = []
    with open(filename, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()

            edmatch = edulint_re.match(line)
            if edmatch:
                raw_args = line[edmatch.end() :]
                result.extend(shlex.split(raw_args))

            ibmatch = ib111_re.match(line)
            if ibmatch:
                result.append(f"{Option.IB111_WEEK.to_name()}={ibmatch.group(1)}")

    return result


def parse_option(
    option_parses: Dict[Option, OptionParse],
    name_to_option: Dict[str, Option],
    name: str,
    val: Optional[str],
) -> Optional[Option]:
    option = name_to_option.get(name)

    if option is None:
        print(f"edulint: unrecognized option {name}", file=sys.stderr)
    else:
        option_parse = option_parses[option]
        if option_parse.takes_val == TakesVal.YES and val is None:
            print(
                f"edulint: option {name} takes an argument but none was supplied",
                file=sys.stderr,
            )
        elif option_parse.takes_val == TakesVal.NO and val is not None:
            print(
                f"edulint: option {name} takes no argument but {val} was supplied",
                file=sys.stderr,
            )
        else:
            return option
    return None


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
        option = parse_option(option_parses, name_to_option, name, val)
        if option is not None:
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


# %% partial parsers


def parse_cmd_config(
    args: List[str],
    option_parses: Dict[Option, OptionParse],
    config_translations: Dict[Option, Translation],
    ib111_translations: List[Translation],
) -> Config:
    parsed = parse_args(args, option_parses)
    return Config(parsed, option_parses, config_translations, ib111_translations)


def parse_infile_config(
    filename: str,
    option_parses: Dict[Option, OptionParse],
    config_translations: Dict[Option, Translation],
    ib111_translations: List[Translation],
) -> Config:
    extracted = extract_args(filename)
    parsed = parse_args(extracted, option_parses)
    return Config(parsed, option_parses, config_translations, ib111_translations)


def parse_config_file(
    path: str,
    option_parses: Dict[Option, OptionParse],
    config_translations: Dict[Option, Translation],
    ib111_translations: List[Translation],
) -> Optional[Config]:
    def print_invalid_type_message(option: Option, val: Any) -> None:
        print(f"edulint: invalid value type {type(val)} of value {val} for option {Option.CONFIG}")

    def parse_base_config(config_dict: Dict[str, Any]) -> Optional[Config]:
        rec_config = config_dict.get(Option.CONFIG.to_name(), BASE_CONFIG)
        if not isinstance(rec_config, str):
            print_invalid_type_message(Option.CONFIG, rec_config)
            rec_config = BASE_CONFIG
        return parse_config_file(rec_config, option_parses, config_translations, ib111_translations)

    def val_to_str(option: Option, val: Any) -> Optional[str]:
        if isinstance(val, str):
            return val
        if isinstance(val, list):
            return ",".join(val)
        if isinstance(val, tuple):
            key, value = val
            value = val_to_str(option, value)
            return f"--{key}={value}" if value is not None else None
        print_invalid_type_message(option, val)
        return None

    config_dict = load_toml_file(path)
    if config_dict is None:
        return None

    base = (
        parse_base_config(config_dict)
        if path != BASE_CONFIG
        else _get_default_config(option_parses, config_translations, ib111_translations)
    )
    if base is None:
        return None

    result = []
    name_to_option = get_name_to_option(option_parses)
    for name, val in config_dict.items():
        option = parse_option(option_parses, name_to_option, name, val)
        if option is None or option == Option.CONFIG:  # config is handled as the first option
            continue

        if not isinstance(val, dict):
            to_process = [val]
        elif option.to_name() not in {linter.to_name() for linter in Linter}:
            print_invalid_type_message(option, val)
            continue
        else:
            to_process = list(val.items())

        for val in to_process:
            str_val = val_to_str(option, val)
            if str_val is not None:
                result.append(UnprocessedArg(option, str_val))

    this_file_config = Config(result, option_parses, config_translations, ib111_translations)
    return Config.combine(base, this_file_config)


# %% complete parsers


def get_config_one(
    filename: str,
    cmd_args: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
    config_translations: Dict[Option, Translation] = get_config_translations(),
    ib111_translation: List[Translation] = get_ib111_translations(),
) -> Optional[ImmutableConfig]:
    configs = get_config_many(
        [filename], cmd_args, option_parses, config_translations, ib111_translation
    )
    if len(configs) == 0:
        return None
    _filenames, config = configs[0]
    return config


def _partition(filenames: List[str], configs: List[Config]) -> List[Tuple[List[str], Config]]:
    immutable_configs = [c.to_immutable() for c in configs]

    indices: Dict[ImmutableConfig, int] = {}
    partition: List[Tuple[List[str], Config]] = []
    for i, filename in enumerate(filenames):
        iconfig = immutable_configs[i]
        config = configs[i]
        index = indices.get(iconfig)
        if index is None:
            indices[iconfig] = len(partition)
            partition.append(([filename], config))
        else:
            partition[index][0].append(filename)
    return partition


def _get_default_config(
    option_parses: Dict[Option, OptionParse],
    config_translations: Dict[Option, Translation],
    ib111_translations: List[Translation],
) -> Config:
    return Config(
        option_parses=option_parses,
        config_translations=config_translations,
        ib111_translations=ib111_translations,
    )


def _parse_infile_configs(
    filenames: List[str],
    cmd_config: Config,
    option_parses: Dict[Option, OptionParse],
    config_translations: Dict[Option, Translation],
    ib111_translations: List[Translation],
) -> List[Config]:
    infile_configs = []
    for filename in filenames:
        infile_config = parse_infile_config(
            filename, option_parses, config_translations, ib111_translations
        )
        infile_configs.append(infile_config)
    return infile_configs


def get_config_many(
    filenames: List[str],
    cmd_args_raw: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
    config_translations: Dict[Option, Translation] = get_config_translations(),
    ib111_translations: List[Translation] = get_ib111_translations(),
) -> List[Tuple[List[str], ImmutableConfig]]:
    cmd_config = parse_cmd_config(
        cmd_args_raw, option_parses, config_translations, ib111_translations
    )
    infile_configs = _parse_infile_configs(
        filenames, cmd_config, option_parses, config_translations, ib111_translations
    )

    cmd_config_path = cmd_config.get_last_value(Option.CONFIG, use_default=False)
    config_paths = (
        {cast(str, cmd_config_path)}
        if cmd_config_path is not None
        else {
            cast(str, infile_args.get_last_value(Option.CONFIG, use_default=True))
            for infile_args in infile_configs
        }
    )
    file_configs = {
        config_path: parse_config_file(
            config_path, option_parses, config_translations, ib111_translations
        )
        for config_path in config_paths
    }

    result: List[Tuple[List[str], ImmutableConfig]] = []
    for files, infile_config in _partition(filenames, infile_configs):
        combined = Config.combine(infile_config, cmd_config)
        file_config = file_configs[
            cast(str, combined.get_last_value(Option.CONFIG, use_default=True))
        ]
        if file_config is None:
            continue

        config = Config.combine(file_config, combined)
        result.append((files, config.to_immutable()))
    return result


def get_cmd_args(args: Namespace) -> List[str]:
    return [s for arg in args.options for s in shlex.split(arg)]
