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
    TakesVal,
    Combine,
    OPTION_SETS_LABEL,
    LANG_TRANSLATIONS_LABEL,
    DEFAULT_ENABLER_LABEL,
)
from edulint.config.file_config import load_toml_file, get_path_relative_to
from edulint.config.option_sets import OptionSets, OptionSet, parse_option_sets
from edulint.config.language_translations import (
    LangTranslations,
    parse_lang_translations,
    parse_lang_file,
)
from edulint.config.utils import print_invalid_type_message, config_file_val_to_str, add_enabled
from typing import Dict, List, Optional, Tuple, Iterator, Any

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
        option_sets: OptionSets,
        log_unknown_groups: bool,
    ) -> List[Optional[ProcessedArg]]:
        def apply_option_set(result: List[Optional[ProcessedArg]], option_set: OptionSet) -> None:
            for linter, vals in option_set.to.items():
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
                    option_set = option_sets.get(group)
                    if option_set is None:
                        if log_unknown_groups:
                            logger.warning(
                                "unknown group {group}, known groups are {groups}",
                                group=group,
                                groups=", ".join(option_sets.keys()),
                            )
                        continue
                    apply_option_set(result, option_set)

            option_option_set = option_sets.get(arg.option.to_name())
            if option_option_set is not None:
                apply_option_set(result, option_option_set)

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

    @staticmethod
    def _resolve_enable_disable_all(pylint_args: List[str]) -> List[str]:
        result = []
        all_set, enable = False, False
        for arg in reversed(pylint_args):
            arg = arg.lower()
            if arg == "--enable=noop":
                pass
            elif arg in ("--disable=all", "--enable=all"):
                if all_set:
                    continue
                all_set = True
                enable = arg == "--enable=all"
            elif all_set and (
                (arg.startswith("--disable") and enable)
                or (arg.startswith("--enable") and not enable)
            ):
                continue
            result.append(arg)

        result.reverse()
        return result

    def to_immutable(
        self, option_sets: OptionSets = {}, log_unknown_groups: bool = True
    ) -> "ImmutableConfig":
        translated = self._translate(self.config, option_sets, log_unknown_groups)
        combined = self._combine(translated, allowed_combines=(Combine.REPLACE, Combine.EXTEND))

        ordered_args = [ProcessedArg(o, self.option_parses[o].default) for o in Option]
        for arg in combined:
            if arg is None:
                continue
            if arg.option == Option.PYLINT:
                arg = ProcessedArg(Option.PYLINT, self._resolve_enable_disable_all(arg.val))
            ordered_args[int(arg.option)] = arg

        enablers_from_option_sets = {}
        for name, option_set in option_sets.items():
            for linter, vals in option_set.to.items():
                for val in vals:
                    add_enabled(name, enablers_from_option_sets, linter.to_option(), val)

        return ImmutableConfig(
            tuple(ImmutableArg(o, self._to_immutable(ordered_args[int(o)].val)) for o in Option),
            hashabledict({**enablers_from_option_sets, **self.enablers}),
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


def extract_args(path: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint:\s*", re.IGNORECASE)
    ib111_re = re.compile(r".*from\s+ib111\s+import.+week_(\d+)", re.IGNORECASE)

    result: List[str] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()

            edmatch = edulint_re.match(line)
            if edmatch:
                raw_args = line[edmatch.end() :]
                result.extend(shlex.split(raw_args))

            ibmatch = ib111_re.match(line)
            if ibmatch:
                result.append(f"{Option.CONFIG_FILE.to_name()}=ib111.toml")

    return result


def parse_option(
    option_parses: Dict[Option, OptionParse],
    name: str,
    val: Optional[str],
) -> Optional[Option]:
    option = Option.safe_from_name(name)

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
    def get_name_val(arg: str) -> Tuple[str, Optional[str]]:
        if "=" in arg:
            name, val = arg.split("=", 1)
            return name, val
        return arg, None

    result: List[UnprocessedArg] = []
    for arg in args:
        name, val = get_name_val(arg)
        option = parse_option(option_parses, name, val)
        if option is not None:
            result.append(UnprocessedArg(option, val))
    return result


def fill_in_val(arg: UnprocessedArg, option_set: List[str]) -> List[str]:
    result = []
    for t in option_set:
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


def resolve_relative_option_path(path: str, config: Config, option: Option) -> None:
    config_path = config.get_last_value(option, use_default=False)
    if config_path is None:
        return

    assert config.option_parses[option].combine == Combine.REPLACE
    config_abspath = get_path_relative_to(config_path, path)
    config.config.append(ProcessedArg(option, config_abspath))


def resolve_ignore_infile_config(parsed: List[UnprocessedArg], config: Config) -> Config:
    if not _ignore_infile(config):
        return config

    ignore_infile_val = config.get_last_value(Option.IGNORE_INFILE_CONFIG_FOR, use_default=False)
    assert ignore_infile_val is not None
    ignore_infile_str = ",".join(ignore_infile_val)

    if "edulint" in ignore_infile_val or "all" in ignore_infile_val:
        parsed = [UnprocessedArg(Option.IGNORE_INFILE_CONFIG_FOR, ignore_infile_str)]
    else:
        parsed.append(UnprocessedArg(Option.IGNORE_INFILE_CONFIG_FOR, ignore_infile_str))

    return Config("in-file", parsed, config.option_parses)


def parse_infile_config(path: str, option_parses: Dict[Option, OptionParse]) -> Config:
    extracted = extract_args(path)
    parsed = parse_args(extracted, option_parses)
    infile_config = Config("in-file", parsed, option_parses)

    resolve_relative_option_path(path, infile_config, Option.CONFIG_FILE)
    resolve_relative_option_path(path, infile_config, Option.LANGUAGE_FILE)

    return resolve_ignore_infile_config(parsed, infile_config)


def parse_config_file(
    path: str, option_parses: Dict[Option, OptionParse]
) -> Optional[Tuple[Config, OptionSets, LangTranslations]]:
    def parse_base_config(config_dict: Dict[str, Any]) -> Optional[Config]:
        rec_config = config_dict.get(Option.CONFIG_FILE.to_name(), BASE_CONFIG)
        if not isinstance(rec_config, str):
            print_invalid_type_message(Option.CONFIG_FILE, rec_config)
            rec_config = BASE_CONFIG
        rec_config_abspath = get_path_relative_to(rec_config, path)
        return parse_config_file(rec_config_abspath, option_parses)

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
    base_config, base_option_sets, base_lang_tranlations = base

    result = []
    this_file_option_sets = {}
    this_file_lang_translations = {}
    for name, val in config_dict.items():
        if name == OPTION_SETS_LABEL:
            this_file_option_sets = parse_option_sets(val)
        elif name == LANG_TRANSLATIONS_LABEL:
            this_file_lang_translations = parse_lang_translations(val)
        elif name == DEFAULT_ENABLER_LABEL:
            continue
        else:
            option = parse_option(option_parses, name, val)
            if (
                option is None or option == Option.CONFIG_FILE
            ):  # config is handled as the first option
                continue

            if option == Option.LANGUAGE_FILE:
                val = get_path_relative_to(val, path)

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
        {**base_option_sets, **this_file_option_sets},
        {**base_lang_tranlations, **this_file_lang_translations},
    )


# %% complete parsers


def get_config_one(
    filename: str,
    cmd_args: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
) -> Optional[Tuple[ImmutableConfig, LangTranslations]]:
    configs = get_config_many([filename], cmd_args, option_parses)
    if len(configs) == 0:
        return None
    _filenames, config, lang_translations = configs[0]
    return config, lang_translations


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


def _get_default_config(option_parses: Dict[Option, OptionParse]) -> Tuple[Config, OptionSets]:
    return Config(enabler=None, option_parses=option_parses), {}, {}


def _ignore_infile(config: Config) -> bool:
    ignored_infile = config.get_last_value(Option.IGNORE_INFILE_CONFIG_FOR, use_default=True)
    return Linter.EDULINT.to_name() in ignored_infile or "all" in ignored_infile


# def get_config_paths(
#     filenames: List[str], infile_configs: List[Config]
# ) -> Tuple[Set[str], Dict[str, str]]:
#     assert len(filenames) == len(infile_configs)
#     config_paths = set()
#     filename_mapping = {}
#     for filename, config in zip(filenames, infile_configs):
#         config_file = config.get_last_value(Option.CONFIG_FILE, use_default=True)
#         if (
#             config_file.startswith("http")
#             or not config_file.endswith(".toml")
#             or os.path.isabs(config_file)
#         ):
#             config_path = config_file
#         else:
#             config_path = str(Path(filename).parent / config_file)
#         config_paths.add(config_path)
#         filename_mapping[filename] = config_path
#     return config_paths, filename_mapping


def _parse_infile_configs(
    files_or_dirs: List[str], cmd_config: Config, option_parses: Dict[Option, OptionParse]
) -> Dict[ImmutableConfig, Tuple[Config, List[str]]]:

    def add_to_result(result, config, path, iconfig=None):
        iconfig = config.to_immutable() if iconfig is None else iconfig
        if iconfig not in result:
            result[iconfig] = (config, [path])
        else:
            result[iconfig][1].append(path)

    def aggregate_subresults(paths):
        result = {}
        for path in paths:
            subresult = _parse_infile_configs_rec(path)
            for iconfig, (config, subpaths) in subresult.items():
                if iconfig not in result:
                    result[iconfig] = (config, subpaths)
                else:
                    result[iconfig][1].extend(subpaths)
        return result

    def _parse_infile_configs_rec(path: str):
        if not os.path.isdir(path):
            if not os.path.splitext(path)[1].lower() == ".py":
                return {}

            infile_config = parse_infile_config(path, option_parses)
            return {infile_config.to_immutable(log_unknown_groups=False): (infile_config, [path])}

        result = aggregate_subresults([os.path.join(path, name) for name in os.listdir(path)])

        if len(result) != 1:
            return result

        iconfig, (config, _paths) = list(result.items())[0]
        return {iconfig: (config, [path])}

    if _ignore_infile(cmd_config):
        default_config = _get_default_config(option_parses)[0]
        return {default_config.to_immutable(): (default_config, files_or_dirs)}

    return aggregate_subresults(files_or_dirs)


def get_config_many(
    files_or_dirs: List[str],
    cmd_args_raw: List[str],
    option_parses: Dict[Option, OptionParse] = get_option_parses(),
) -> List[Tuple[List[str], ImmutableConfig, LangTranslations]]:
    cmd_config = parse_cmd_config(cmd_args_raw, option_parses)
    infile_configs = _parse_infile_configs(files_or_dirs, cmd_config, option_parses)

    cmd_config_path = cmd_config.get_last_value(Option.CONFIG_FILE, use_default=False)

    if cmd_config_path is not None:
        config_paths = {cmd_config_path}
    else:
        config_paths = {iconfig[Option.CONFIG_FILE] for iconfig in infile_configs.keys()}

    config_file_results = {
        config_path: parse_config_file(config_path, option_parses) for config_path in config_paths
    }
    lang_file_results = {}

    result: List[Tuple[List[str], ImmutableConfig, LangTranslations]] = []
    for infile_config, paths in infile_configs.values():
        combined = Config.combine(infile_config, cmd_config)
        config_file_result = (
            config_file_results[cmd_config_path]
            if cmd_config_path is not None
            else config_file_results[
                infile_config.get_last_value(Option.CONFIG_FILE, use_default=True)
            ]
        )
        if config_file_result is None:
            continue
        file_config, option_sets, lang_translations = config_file_result

        if _ignore_infile(file_config):
            if cmd_config_path is not None:
                config = Config.combine(file_config, cmd_config)
            else:
                config = cmd_config
        else:
            config = Config.combine(file_config, combined)

        iconfig = config.to_immutable(option_sets)
        language_file = iconfig[Option.LANGUAGE_FILE]
        if language_file is not None:
            lang_file_translations = lang_file_results.get(
                language_file, parse_lang_file(iconfig[Option.LANGUAGE_FILE])
            )
            if lang_file_translations is not None:
                lang_translations = {**lang_translations, **lang_file_translations}
                lang_file_results[language_file] = lang_translations

        result.append((paths, iconfig, lang_translations))
    return result


def get_cmd_args(args: Namespace) -> List[str]:
    return [s for arg in args.options for s in shlex.split(arg)]
