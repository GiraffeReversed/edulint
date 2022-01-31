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
        gutters: ["CodeMirror-linenumbers", "breakpoints"],
        rulers: [{ color: "#ddd", column: 79, lineStyle: "dotted" }]
    });

    editor.setOption("theme", "base16-light");

    editor.on("gutterClick", (cm, n) => {
        var info = cm.lineInfo(n);
        if (info.gutterMarkers) {
            info.gutterMarkers.breakpoints.click();
            document.getElementById("problem" + n).scrollIntoView(
                {
                    behavior: "smooth",
                    block: "nearest",
                }
            );
        }
    });
}

function makeMarker(lineIndex) {
    var marker = document.createElement("div");
    marker.innerHTML =
        `<a data-bs-toggle="collapse" href="#collapse${lineIndex}" role="button" aria-expanded="false"
      aria-controls="collapse${lineIndex}" class="problemMarker">
    ●
    </a>`;
    return marker.firstElementChild;
}

function oneLineProblemsHTML(oneLineProblems) {
    assert(oneLineProblems.length >= 1);

    let lineIndex = Number(oneLineProblems[0].line) - 1;
    let result = "";

    for (let problem of oneLineProblems) {
        result +=
            `<div id="problem${lineIndex}" data-line=${lineIndex} class="accordion-item problem">
                <h5 class="accordion-header" id="heading${lineIndex}">
                    <button class="accordion-button collapsed btn-outline-primary" type="button" data-bs-toggle="collapse"
                    data-bs-target="#collapse${lineIndex}" aria-expanded="false"
                    aria-controls="collapse${lineIndex}">
                    ${problem.source} ${problem.line}: ${problem.code} ${problem.text}
                    </button>
                </h5>
                <div id="collapse${lineIndex}" class="accordion-collapse collapse"
                    aria-labelledby="heading${lineIndex}" data-bs-parent="#problemsAccordion">
                    <div class="accordion-body">
                        WHY?!
                        <hr>
                        Examples
                    </div>
                </div>
            </div>`;
    }

    editor.doc.setGutterMarker(lineIndex, "breakpoints", makeMarker(lineIndex));
    return result;
}

function problemsHTML(problems) {
    let result = `<div class="accordion" id="problemsAccordion">`;

    let firstUnprocessed = 0;
    for (let i = 1; i <= problems.length; i++) {
        if (i === problems.length || problems[i].line !== problems[firstUnprocessed].line) {
            result += oneLineProblemsHTML(problems.slice(firstUnprocessed, i));
            firstUnprocessed = i;
        }
    }
    result += `</div>`;
    return result;
}

function jumpToLine(n) {
    var t = editor.charCoords({ line: n, ch: 0 }, "local").top;
    var middleHeight = editor.getScrollerElement().offsetHeight / 3;
    editor.scrollTo(null, t - middleHeight - 5);
}

function problemClick(e) {
    let problem = e.currentTarget;
    if (problem.getElementsByClassName("accordion-button")[0].ariaExpanded === "true") {
        let lineIndex = Number(problem.dataset.line);
        editor.addLineClass(lineIndex, "background", "highlighted-line");
        setTimeout(() => {
            editor.removeLineClass(lineIndex, "background", "highlighted-line")
        }, 1700);
        jumpToLine(lineIndex);
    }
}

function registerProblemCallbacks() {
    for (let problem of document.getElementsByClassName("problem")) {
        problem.addEventListener("click", problemClick);
    }
}

function analyze() {
    let problemsBlock = document.getElementById("problems-block");
    problemsBlock.innerHTML = ""
    fetch("/analyze", {
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
        );
}

function loadFile() {
    let file = this.files[0];
    console.log(file);
    if (!file || file.type !== "text/x-python") {
        alert("Upload Python file");
        return;
    }

    let reader = new FileReader();
    reader.onload = function () { editor.setValue(reader.result); }
    reader.readAsText(file);
    document.getElementById("inputFileLabel").innerText = file.name;
}

function setup() {
    setupEditor();
    document.getElementById("analysisSubmit").addEventListener("click", analyze);
    document.getElementById('inputFile').addEventListener('change', loadFile);
}

document.addEventListener("DOMContentLoaded", setup)
