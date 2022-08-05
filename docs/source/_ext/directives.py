from edulint.options import Option, get_option_parses
from edulint.linters import Linters
from edulint.config.config_translates import get_config_translations
from docutils.parsers.rst import Directive
from docutils import nodes
from configparser import ConfigParser
import requests
from bs4 import BeautifulSoup


def html_to_nodes(siblings):
    para = nodes.paragraph()
    for sibling in siblings:
        if sibling.name is None:
            para.append(nodes.inline(text=sibling.string))
        elif sibling.name == "a":
            para.append(nodes.reference(internal=False, refuri=sibling["href"], text=sibling.string))
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
    features = get_description_from("https://pylint.pycqa.org/en/latest/user_guide/checkers/features.html", "h4")
    extensions = get_description_from("https://pylint.pycqa.org/en/latest/user_guide/checkers/extensions.html", "h3")

    extensions.update(features)
    return extensions


def get_links():
    links_html = requests.get("https://pylint.pycqa.org/en/latest/user_guide/messages/messages_overview.html")
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

    colspecs = [nodes.colspec(colwidth=colwidths[i] if i < len(colwidths) else 1) for i in range(len(header))]

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


class Options(Directive):

    def run(self):
        table, tbody = prepare_table(["Option name", "Takes argument", "Description"], [2, 1, 4])

        for option, parse in get_option_parses().items():
            tbody.append(prepare_row(
                option.to_name(), parse.takes_val.name.lower(), parse.help_
            ))

        return [table]


class MessageTable(Directive):

    required_arguments = 1

    def run(self):
        table, tbody = prepare_table(["Message name", "Description"], [1, 3])

        arg = self.arguments[0]
        if arg == "default":
            config = ConfigParser()
            config.read("../edulint/linting/.pylintrc")
            message_names = [c.strip() for c in config["MESSAGES CONTROL"]["enable"].split(",")]
        else:
            translations = get_config_translations()
            opt_arg = Option.from_str(arg)
            translation = translations[opt_arg]
            assert translation.to == Linters.PYLINT
            message_names = [c.strip() for v in translation.val for c in v[len("--enable="):].split(",")]

        tbody.extend([prepare_row(
            nodes.reference(internal=False, refuri=LINKS[n][2], text=n),
            DESCRIPTIONS[n][3]
        ) for n in message_names])

        return [table]


def link_pylint(name, rawtext, text, lineno, inliner, options={}, content=[]):
    return [nodes.reference(internal=False, refuri=LINKS[text][2], text=text)], []


def setup(app):
    app.add_directive("options", Options)
    app.add_directive("message-table", MessageTable)
    app.add_role("link_pylint", link_pylint)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
