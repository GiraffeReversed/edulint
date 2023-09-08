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
    TRANSLATIONS_LABEL,
    DEFAULT_ENABLER_LABEL,
)
from edulint.config.file_config import load_toml_file
from edulint.config.config_translations import Translations, Translation, parse_translations
from edulint.config.utils import print_invalid_type_message, config_file_val_to_str, add_enabled
from typing import Dict, List, Optional, Tuple, Iterator, Any, Set

from dataclasses import dataclass
from argparse import Namespace
from pathlib import Path
import re
import shlex
from loguru import logger
import os


class Config:
    config: List[Optional[ProcessedArg]]

    def _convert(self, args: List[UnprocessedArg]) -> List[ProcessedArg]:
        return [
            ProcessedArg(arg.option, self.option_parses[arg.option].convert(arg.val))
            for arg in args
        ]

    def _translate(
        self,
        args: List[Optional[ProcessedArg]],
        translations: Translations,
        log_unknown_groups: bool,
    ) -> List[Optional[ProcessedArg]]:
        def apply_translation(
            result: List[Optional[ProcessedArg]], translation: Translation
        ) -> None:
            for linter, vals in translation.to.items():
                translated_option = linter.to_option()
                parse = self.option_parses[translated_option]
                for translated in vals:
                    result.append(ProcessedArg(translated_option, parse.convert(translated)))

        result: List[Optional[ProcessedArg]] = []
        for arg in args:
            if arg is None:
                continue
            result.append(arg)

            if arg.option == Option.SET_GROUPS:
                for group in arg.val:
                    translation = translations.get(group)
                    if translation is None:
                        if log_unknown_groups:
                            logger.warning(
                                "unknown group {group}, known groups are {groups}",
                                group=group,
                                groups=", ".join(translations.keys()),
                            )
                        continue
                    apply_translation(result, translation)

            option_translation = translations.get(arg.option.to_name())
            if option_translation is not None:
                apply_translation(result, option_translation)

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
        enabler: Optional[str],
        config: Optional[List[UnprocessedArg]] = None,
        option_parses: Dict[Option, OptionParse] = get_option_parses(),
    ) -> None:
        config = config if config is not None else []
        self.option_parses = option_parses

        converted = self._convert(config)
        self.config = self._combine(converted, allowed_combines=(Combine.REPLACE,))  # type: ignore

        self.enablers = {}
        if enabler is not None:
            for arg in self.config:
                if arg is not None:
                    if isinstance(arg.val, list):
                        for val in arg.val:
                            add_enabled(enabler, self.enablers, arg.option, val)
                    elif isinstance(arg.val, str):
                        add_enabled(enabler, self.enablers, arg.option, arg.val)

    @staticmethod
    def combine(lt: "Config", rt: "Config") -> "Config":
        assert lt.option_parses == rt.option_parses
        new = Config(enabler=None, option_parses=lt.option_parses)
        new.config = new._combine(lt.config + rt.config, allowed_combines=(Combine.REPLACE,))
        new.enablers = {**lt.enablers, **rt.enablers}
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

    def to_immutable(
        self, translations: Translations = {}, log_unknown_groups: bool = True
    ) -> "ImmutableConfig":
        translated = self._translate(self.config, translations, log_unknown_groups)
        combined = self._combine(translated, allowed_combines=(Combine.REPLACE, Combine.EXTEND))

        ordered_args = [ProcessedArg(o, self.option_parses[o].default) for o in Option]
        for arg in combined:
            if arg is None:
                continue
            ordered_args[int(arg.option)] = arg

        enablers_from_translations = {}
        for name, translation in translations.items():
            for linter, vals in translation.to.items():
                for val in vals:
                    add_enabled(
                        name, enablers_from_translations, Option.from_name(linter.to_name()), val
                    )

        return ImmutableConfig(
            tuple(ImmutableArg(o, self._to_immutable(ordered_args[int(o)].val)) for o in Option),
            hashabledict({**enablers_from_translations, **self.enablers}),
        )


class hashabledict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))


@dataclass(frozen=True)
class ImmutableConfig:
    config: Tuple[ImmutableArg, ...]
    enablers: Dict[str, str]

    def __str__(self) -> str:
        return (
            "ImmutableConfig(\n"
            + "".join(f"  {arg.option.name}={str(arg.val)}\n" for arg in self.config)
            + ")"
        )

    def __getitem__(self, option: Option) -> ImmutableT:
        return self.config[int(option)].val

    def __contains__(self, option: Option) -> bool:
        return self[option] is not None

    def __iter__(self) -> Iterator[ImmutableArg]:
        return filter(lambda x: x is not None, self.config.__iter__())


# %% components


def extract_args(filename: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint:\s*", re.IGNORECASE)
    ib111_re = re.compile(r".*from\s+ib111\s+import.+week_(\d+)", re.IGNORECASE)

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
                result.append(f"{Option.CONFIG.to_name()}=ib111.toml")

    return result


def parse_option(
    option_parses: Dict[Option, OptionParse],
    name_to_option: Dict[str, Option],
    name: str,
    val: Optional[str],
) -> Optional[Option]:
    option = name_to_option.get(name)

    if option is None:
        logger.warning("unrecognized option {name}", name=name)
    else:
        option_parse = option_parses[option]
        if option_parse.takes_val == TakesVal.YES and val is None:
            logger.warning("option {name} takes an argument but none was supplied", name=name)
        elif option_parse.takes_val == TakesVal.NO and val is not None:
            logger.warning(
                "option {name} takes no argument but {val} was supplied", name=name, val=val
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


def parse_cmd_config(args: List[str], option_parses: Dict[Option, OptionParse]) -> Config:
    parsed = parse_args(args, option_parses)
    return Config("cmd", parsed, option_parses)


def parse_infile_config(filename: str, option_parses: Dict[Option, OptionParse]) -> Config:
    extracted = extract_args(filename)
    parsed = parse_args(extracted, option_parses)
    return Config("in-file", parsed, option_parses)


def parse_config_file(
    path: str, option_parses: Dict[Option, OptionParse]
) -> Optional[Tuple[Config, Translations]]:
    def parse_base_config(config_dict: Dict[str, Any]) -> Optional[Config]:
        rec_config = config_dict.get(Option.CONFIG.to_name(), BASE_CONFIG)
        if not isinstance(rec_config, str):
            print_invalid_type_message(Option.CONFIG, rec_config)
            rec_config = BASE_CONFIG
        return parse_config_file(rec_config, option_parses)

    config_dict = load_toml_file(path)
    if config_dict is None:
        return None

    base = (
        parse_base_config(config_dict)
        if path != BASE_CONFIG
        else _get_default_config(option_parses)
    )
    if base is None:
        return None
    base_config, base_translations = base

    result = []
    name_to_option = get_name_to_option(option_parses)
    this_file_translations = {}
    for name, val in config_dict.items():
        if name == TRANSLATIONS_LABEL:
            this_file_translations = parse_translations(val)
        elif name == DEFAULT_ENABLER_LABEL:
            continue
        else:
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
                str_val = config_file_val_to_str(option, val)
                if str_val is not None:
                    result.append(UnprocessedArg(option, str_val))

    enabler_name = config_dict.get(DEFAULT_ENABLER_LABEL, Path(path).stem)
    this_file_config = Config(enabler_name, result, option_parses)
    return (
        Config.combine(base_config, this_file_config),
        {**base_translations, **this_file_translations},
    )


# %% complete parsers


def get_config_one(
    filename: str,
    cmd_args: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
) -> Optional[ImmutableConfig]:
    configs = get_config_many([filename], cmd_args, option_parses)
    if len(configs) == 0:
        return None
    _filenames, config = configs[0]
    return config


def _partition(
    filenames: List[str], configs: List[Config], filenames_mapping: Dict[str, str]
) -> List[Tuple[List[str], Config]]:
    immutable_configs = [
        (c.to_immutable(log_unknown_groups=False), filenames_mapping[filenames[i]])
        for i, c in enumerate(configs)
    ]

    indices: Dict[ImmutableConfig, int] = {}
    partition: List[Tuple[List[str], Config]] = []
    for i, filename in enumerate(filenames):
        id_ = immutable_configs[i]
        config = configs[i]
        index = indices.get(id_)
        if index is None:
            indices[id_] = len(partition)
            partition.append(([filename], config))
        else:
            partition[index][0].append(filename)
    return partition


def _get_default_config(option_parses: Dict[Option, OptionParse]) -> Tuple[Config, Translations]:
    return Config(enabler=None, option_parses=option_parses), {}


def _ignore_infile(config: Config) -> bool:
    ignored_infile = config.get_last_value(Option.IGNORE_INFILE_CONFIG_FOR, use_default=True)
    return Linter.EDULINT.to_name() in ignored_infile or "all" in ignored_infile


def _parse_infile_configs(
    filenames: List[str], cmd_config: Config, option_parses: Dict[Option, OptionParse]
) -> List[Config]:
    if _ignore_infile(cmd_config):
        return [_get_default_config(option_parses)[0] for filename in filenames]

    infile_configs = []
    for filename in filenames:
        infile_config = parse_infile_config(filename, option_parses)
        if _ignore_infile(infile_config):
            ignore_infile_val = infile_config.get_last_value(
                Option.IGNORE_INFILE_CONFIG_FOR, use_default=False
            )
            assert ignore_infile_val is not None
            ignore_infile_str = ",".join(ignore_infile_val)
            infile_config = Config(
                "in-file",
                [UnprocessedArg(Option.IGNORE_INFILE_CONFIG_FOR, ignore_infile_str)],
                option_parses,
            )

        infile_configs.append(infile_config)
    return infile_configs


def get_config_paths(
    filenames: List[str], infile_configs: List[Config]
) -> Tuple[Set[str], Dict[str, str]]:
    assert len(filenames) == len(infile_configs)
    config_paths = set()
    filename_mapping = {}
    for filename, config in zip(filenames, infile_configs):
        config_file = config.get_last_value(Option.CONFIG, use_default=True)
        if (
            config_file.startswith("http")
            or not config_file.endswith(".toml")
            or os.path.isabs(config_file)
        ):
            config_path = config_file
        else:
            config_path = str(Path(filename).parent / config_file)
        config_paths.add(config_path)
        filename_mapping[filename] = config_path
    return config_paths, filename_mapping


def get_config_many(
    filenames: List[str],
    cmd_args_raw: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
) -> List[Tuple[List[str], ImmutableConfig]]:
    cmd_config = parse_cmd_config(cmd_args_raw, option_parses)
    infile_configs = _parse_infile_configs(filenames, cmd_config, option_parses)

    cmd_config_path = cmd_config.get_last_value(Option.CONFIG, use_default=False)

    if cmd_config_path is not None:
        config_paths = {cmd_config_path}
        filenames_mapping = {filename: cmd_config_path for filename in filenames}
    else:
        config_paths, filenames_mapping = get_config_paths(filenames, infile_configs)

    file_configs_translations = {
        config_path: parse_config_file(config_path, option_parses) for config_path in config_paths
    }

    result: List[Tuple[List[str], ImmutableConfig]] = []
    for files, infile_config in _partition(filenames, infile_configs, filenames_mapping):
        combined = Config.combine(infile_config, cmd_config)
        file_config_translations = file_configs_translations[filenames_mapping[files[0]]]
        if file_config_translations is None:
            continue
        file_config, translations = file_config_translations

        if _ignore_infile(file_config):
            if cmd_config_path is not None:
                config = Config.combine(file_config, cmd_config)
            else:
                config = cmd_config
        else:
            config = Config.combine(file_config, combined)
        result.append((files, config.to_immutable(translations)))
    return result


def get_cmd_args(args: Namespace) -> List[str]:
    return [s for arg in args.options for s in shlex.split(arg)]
