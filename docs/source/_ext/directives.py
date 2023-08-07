from edulint.options import Option
from edulint.option_parses import get_option_parses
from edulint.linters import Linter
from edulint.config.config_translations import get_config_translations
import edulint.linting.checkers as custom_checkers
from pylint.checkers import BaseChecker
from docutils.parsers.rst import Directive
from docutils import nodes
from configparser import ConfigParser
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from pkgutil import iter_modules
import os
import sys
import importlib
import inspect


def html_to_nodes(siblings):
    para = nodes.paragraph()
    for sibling in siblings:
        if sibling.name is None:
            para.append(nodes.inline(text=sibling.string))
        elif sibling.name == "a":
            para.append(
                nodes.reference(internal=False, refuri=sibling["href"], text=sibling.string)
            )
        elif sibling.name == "cite":
            para.append(nodes.literal(text=sibling.string))
        elif sibling.name == "code":
            para.append(nodes.literal(text=" ".join(x.string for x in sibling.find_all("span"))))
        else:
            assert False, sibling.name
    return para


def get_description_from(url, heading):
    descriptions_html = requests.get(url)
    if descriptions_html.status_code != 200:
        raise RuntimeError("descriptions not available")
    soup = BeautifulSoup(descriptions_html.text, "html.parser")

    result = {}
    for h4 in soup.find_all(heading):
        for dt in h4.parent.find_all("dt"):
            if " " not in dt.string:
                continue

            name, pcode = dt.string.split(" ", 1)
            code = pcode.strip(" ()")

            dd = dt.next_sibling.next_sibling
            if dd.em is None:
                message = None
                desc = dd.text
            else:
                message = dd.em.string
                desc = html_to_nodes(dd.em.next_siblings)
            result[name] = (name, code, message, desc)
    return result


def get_descriptions():
    features = get_description_from(
        "https://pylint.readthedocs.io/en/v2.14.5/user_guide/checkers/features.html", "h4"
    )
    extensions = get_description_from(
        "https://pylint.readthedocs.io/en/v2.14.5/user_guide/checkers/extensions.html", "h3"
    )

    extensions.update(features)
    return extensions


def get_links():
    links_html = requests.get(
        "https://pylint.pycqa.org/en/latest/user_guide/messages/messages_overview.html"
    )
    if links_html.status_code != 200:
        raise RuntimeError("links not available")
    soup = BeautifulSoup(links_html.text, "html.parser")

    result = {}
    for a in soup.select("li a"):
        if "/" not in a.string:
            continue
        name, code = a.string.split("/")
        name, code = name.strip(), code.strip()
        link = "https://pylint.pycqa.org/en/latest/user_guide/messages/" + a["href"]
        result[name] = (name, code, link)

    return result


DESCRIPTIONS = get_descriptions()
LINKS = get_links()


def text_to_entry(text):
    entry = nodes.entry()
    if isinstance(text, str):
        entry.append(nodes.paragraph(text=text))
    else:
        para = nodes.paragraph()
        para.append(text)
        entry.append(para)
    return entry


def prepare_table(header, colwidths=None):
    colwidths = colwidths if colwidths is not None else []

    colspecs = [
        nodes.colspec(colwidth=colwidths[i] if i < len(colwidths) else 1)
        for i in range(len(header))
    ]

    entries = [text_to_entry(h) for h in header]
    row = nodes.row()
    row.extend(entries)

    thead = nodes.thead()
    thead.append(row)

    tbody = nodes.tbody()

    tgroup = nodes.tgroup(cols=len(header))
    tgroup.extend(colspecs + [thead, tbody])

    table = nodes.table()
    table.append(tgroup)

    return table, tbody


def prepare_row(*contents):
    row = nodes.row()
    row.extend(map(text_to_entry, contents))
    return row


class OptionsTable(Directive):
    def run(self):
        table, tbody = prepare_table(
            [
                "Option name",
                "Takes argument",
                "Default",
                "Converts to",
                "When used multiple types",
                "Description",
            ],
            [2, 1, 1, 1, 1, 10],
        )

        for option, parse in get_option_parses().items():
            id_ = f"option-{option.to_name()}"
            row = prepare_row(
                option.to_name(),
                parse.takes_val.name.lower(),
                nodes.literal(text=str(parse.default)),
                parse.convert.name.lower(),
                parse.combine.name.lower(),
                parse.help_,
            )
            self.options["name"] = id_
            self.add_name(row)
            tbody.append(row)

        return [table]


class MessageTable(Directive):
    required_arguments = 1

    def run(self):
        table, tbody = prepare_table(["Message name", "Description"], [1, 3])

        arg = self.arguments[0]
        if arg == "default":
            config = ConfigParser()
            config.read(Path(__file__).parent.parent.parent.parent / "edulint/linting/.pylintrc")
            message_names = [c.strip() for c in config["MESSAGES CONTROL"]["enable"].split(",")]
        else:
            translations = get_config_translations()
            opt_arg = Option.from_name(arg)
            translation = translations[opt_arg]
            assert translation.for_linter == Linter.PYLINT
            message_names = [
                c.strip() for v in translation.vals for c in v[len("--enable=") :].split(",")
            ]

        message_names = [n for n in message_names if n]

        for name in message_names:
            if name in LINKS:
                tbody.append(
                    prepare_row(
                        nodes.reference(internal=False, refuri=LINKS[name][2], text=name),
                        DESCRIPTIONS[name][3],
                    )
                )
            else:
                message = nodes.reference(internal=True, refuri="#custom-checkers", text=name)
                para = nodes.paragraph()
                para.append(nodes.inline(text="Custom message or checker, see "))
                para.append(
                    nodes.reference(
                        internal=True, refuri="#custom-checkers", text="the corresponding section."
                    )
                )
                tbody.append(prepare_row(message, para))

        return [table]


def link_pylint(name, rawtext, text, lineno, inliner, options={}, content=[]):
    return [nodes.reference(internal=False, refuri=LINKS[text][2], text=text)], []


def link_option(name, rawtext, text, lineno, inliner, options={}, context=[]):
    return [
        nodes.reference(
            internal=True, refuri=f"#option-{Option.from_name(text).to_name()}", text=text
        )
    ], []


def prepare_section(name, title):
    section = nodes.section(ids=[f"checker-{name}"])
    titlenode = nodes.title(text=title)
    section += titlenode
    para = nodes.paragraph()
    para.extend(
        [
            nodes.inline(text="This section details messages emmited by the "),
            nodes.literal(text=name),
            nodes.inline(text=" checker."),
        ]
    )
    section += para
    return section


class CheckersBlock(Directive):
    @staticmethod
    def _iterate_checkers():
        custom_checkers_dir = os.path.dirname(custom_checkers.__file__)
        for _, name, _ in iter_modules([custom_checkers_dir]):
            module_path = os.path.join(custom_checkers_dir, name) + ".py"
            spec = importlib.util.spec_from_file_location(
                f"edulint.linting.checkers.{name}", module_path
            )

            module = importlib.util.module_from_spec(spec)
            sys.modules["module.name"] = module
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseChecker) and obj != BaseChecker:
                    yield obj

    def _prepare_option_defaults_table(self, options):
        noun_plural = "s" if len(options) > 1 else ""
        verb_plural = "" if len(options) > 1 else "s"
        para = nodes.paragraph(
            text=f"The checker has {'some' if len(options) > 1 else 'an'} option{noun_plural} associated "
            f"with it. If the checker or its messages are enabled directly, the option{noun_plural} "
            f"receive{verb_plural} the following default{noun_plural}:"
        )

        table, tbody = prepare_table(["Option", "Default"])
        for name, details in options:
            default = details["default"]
            tbody.append(
                prepare_row(
                    name,
                    nodes.literal(text=default if not isinstance(default, str) else f'"{default}"'),
                )
            )

        return [para, table]

    def run(self):
        result = []
        for checker_class in self._iterate_checkers():
            name = checker_class.name
            section = prepare_section(name, name.replace("-", " ").title())

            table, tbody = prepare_table(["Message name", "Format", "Description"], [1, 3, 3])
            for message_code, (message_format, message_name, desc) in checker_class.msgs.items():
                tbody.append(prepare_row(message_name, nodes.literal(text=message_format), desc))
            section.append(table)

            options = checker_class.options
            if options:
                section.extend(self._prepare_option_defaults_table(options))

            result.append(section)
        return result


def setup(app):
    app.add_directive("options-table", OptionsTable)
    app.add_directive("message-table", MessageTable)
    app.add_role("link_pylint", link_pylint)
    app.add_role("link_option", link_option)
    app.add_directive("checkers-block", CheckersBlock)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
