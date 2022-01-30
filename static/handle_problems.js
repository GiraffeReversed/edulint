'use strict';

let editor;

function assert(condition, message = "") {
    if (!condition) {
        throw message || "Assertion failed";
    }
}

function toggleActiveProblem(lineIndex) {
    let problem = document.getElementById("problem" + lineIndex);
    let shouldActivate = true;
    for (let stale of document.getElementsByClassName("active")) {
        if (problem.id === stale.id)
            shouldActivate = false;
        stale.classList.remove("active");
    }

    if (problem !== null && shouldActivate) {
        problem.classList.add("active");
        return true;
    }
    return false;
}

function setupEditor() {
    editor = CodeMirror.fromTextArea(code, {
        lineNumbers: true,
        gutters: ["CodeMirror-linenumbers", "breakpoints"]
    });

    editor.setOption("theme", "base16-light");
    editor.setSize("90ch", "80vh");

    editor.on("gutterClick", (_, n) => { toggleActiveProblem(n); });
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
}

function jumpToLine(n) {
    var t = editor.charCoords({ line: n, ch: 0 }, "local").top;
    var middleHeight = editor.getScrollerElement().offsetHeight / 3;
    editor.scrollTo(null, t - middleHeight - 5);
}

function problemClick(e) {
    let lineIndex = Number(e.target.getAttribute("line"));
    let activated = toggleActiveProblem(lineIndex);

    if (activated) {
        editor.addLineClass(lineIndex, "background", "highlighted-line");
        setTimeout(() => {
            editor.removeLineClass(lineIndex, "background", "highlighted-line")
        }, 1000);
        jumpToLine(lineIndex);
    }
}

function registerProblemCallbacks() {
    for (let problemLi of document.getElementsByClassName("list-group-item")) {
        problemLi.addEventListener("click", problemClick);
    }
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
            registerProblemCallbacks();
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
