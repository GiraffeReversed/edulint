'use strict';

let editor;

function assert(condition, message = "") {
    if (!condition) {
        throw message || "Assertion failed";
    }
}

function setupEditor() {
    editor = CodeMirror.fromTextArea(code, {
        lineNumbers: true,
        gutters: ["CodeMirror-linenumbers", "breakpoints"]
    });
    editor.setOption("theme", "base16-light");
}

function oneLineProblemsHTML(oneLineProblems) {
    assert(oneLineProblems.length >= 1);

    let lineIndex = Number(oneLineProblems[0].line) - 1;
    let result = "<li id='problem" + lineIndex + "' line=" + lineIndex + " class=\"list-group-item\">";

    for (let problem of oneLineProblems) {
        result += problem.source + " " + problem.line + ": " + problem.code + " " + problem.text + "<br>";
    }

    result += "</li>";

    editor.doc.setGutterMarker(lineIndex, "breakpoints", makeMarker());
    return result;
}

function problemsHTML(problems) {
    let result = "<ul class=\"list-group\">";

    let firstUnprocessed = 0;
    for (let i = 1; i <= problems.length; i++) {
        if (i === problems.length || problems[i].line !== problems[firstUnprocessed].line) {
            result += oneLineProblemsHTML(problems.slice(firstUnprocessed, i));
            firstUnprocessed = i;
        }
    }
    result += "</ul>";
    return result;
    editor.on("gutterClick", function (cm, n) {
        let info = cm.lineInfo(n);
        cm.setGutterMarker(n, "breakpoints", info.gutterMarkers ? null : makeMarker());
        // editor.doc.setGutterMarker(11, "breakpoints", makeMarker());
    });
}

function analyze() {
    let problemsBlock = document.getElementById("problems-block");
    problemsBlock.innerHTML = ""
    fetch("/upload_code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            code: editor.getValue()
        })
    })
        .then(response => response.json()) // .json() for Objects vs text() for raw
        .then(problems => {
            problemsBlock.innerHTML = problemsHTML(problems);
        }
        )
}

function setup() {
    setupEditor();
    document.getElementById("analysisSubmit").addEventListener("click", analyze);
}

function makeMarker() {
    var marker = document.createElement("div");
    marker.style.color = "#822";
    marker.innerHTML = "●";
    return marker;
}

document.addEventListener("DOMContentLoaded", setup)
