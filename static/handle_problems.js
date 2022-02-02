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
        gutters: ["problemMarkers", "CodeMirror-linenumbers"],
        rulers: [{ color: "#ddd", column: 79, lineStyle: "dotted" }]
    });

    // editor.setOption("theme", "base16-light");

    editor.on("gutterClick", (cm, n) => {
        var info = cm.lineInfo(n);
        if (info.gutterMarkers) {
            let problemGroup = document.getElementById("problemGroup" + n);
            problemGroup.scrollIntoView(
                {
                    behavior: "smooth",
                    block: "nearest",
                }
            );
            problemGroup.classList.add("highlighted-problem-group");
            setTimeout(() => {
                problemGroup.classList.remove("highlighted-problem-group");
            }, 1700);
        }
    });
}

function makeMarker(lineIndex) {
    var marker = document.createElement("div");
    marker.classList.add("problemMarker");
    marker.id = "problemMarker" + lineIndex;
    marker.innerHTML = `<h5 class="bi bi-arrow-right-short"></h5>`;
    return marker;
}

// TODO warn on shift
function approximateCurrentLineIndex(problemLine) {
    let marker = document.getElementById("problemMarker" + problemLine);
    if (!marker)
        return problemLine;
    return Number(marker.parentElement.previousElementSibling.innerText) - 1;
}

function oneLineProblemsHTML(oneLineProblems) {
    assert(oneLineProblems.length >= 1);

    let lineIndex = Number(oneLineProblems[0].line) - 1;
    let result =
        `<div id="problemGroup${lineIndex}" data-line=${lineIndex} class="problemGroup mb-2 btn-group border rounded w-100">`;
    result +=
        `<button class="btn btn-outline-warning problemGotoBtn p-2" type="button" data-line=${lineIndex}>
            <h5 class="bi bi-bullseye mb-0"></h5>
        </button>`;
    result += `<div class="d-flex flex-column w-100">`;

    for (let i = 0; i < oneLineProblems.length; i++) {
        let problem = oneLineProblems[i];
        result +=
        `<div class="problem border-bottom w-100 h-100 d-flex flex-column justify-content-center" id="problem${lineIndex}_${i}" data-line=${lineIndex}>
                <div class="btn-group problemBtn w-100 align-self-center" role="group">
                    <div class="p-1 small w-100">
                        ${problem.source} ${problem.line}: ${problem.code} ${problem.text}
                    </div>
                    <button class="btn btn-outline-secondary problemInfoBtn p-2" type="button" data-bs-toggle="collapse"
                        data-bs-target="#collapse${lineIndex}_${i}" aria-expanded="false" data-line=${lineIndex}
                        aria-controls="collapse${lineIndex}_${i}" id="heading${lineIndex}_${i}">
                        <h5 class="bi bi-chevron-down mb-0"></h5>
                    </button>
                    <button class="btn btn-outline-success problemSolvedBtn p-2" type="button" data-line=${lineIndex}>
                        <h5 class="bi bi-check2 mb-0"></h5>
                    </button>
                </div>
                <div id="collapse${lineIndex}_${i}" class="accordion-collapse collapse multi-collapse${lineIndex}"
                    aria-labelledby="heading${lineIndex}_${i}" data-bs-parent="#problemsAccordion">
                    <div class="accordion-body">
                        WHY?!
                        <hr>
                        Examples
                    </div>
                </div>
            </div>`;
    }

    result += `</div>`;
    result += `</div>`;

    editor.doc.setGutterMarker(lineIndex, "problemMarkers", makeMarker(lineIndex));
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

function gotoCodeClick(e) {
    let problemInfoBtn = e.currentTarget;
    let lineIndex = approximateCurrentLineIndex(Number(problemInfoBtn.dataset.line));
    editor.addLineClass(lineIndex, "background", "highlighted-line");
    setTimeout(() => {
        editor.removeLineClass(lineIndex, "background", "highlighted-line")
    }, 1700);
    jumpToLine(lineIndex);
}

function registerProblemCallbacks() {
    for (let problemInfoBtn of document.getElementsByClassName("problemInfoBtn")) {
        problemInfoBtn.addEventListener("click", gotoCodeClick);
    }

    for (let problemGotoBtn of document.getElementsByClassName("problemGotoBtn")) {
        problemGotoBtn.addEventListener("click", gotoCodeClick);
    }
}

function analyze(e) {
    let lintButton = e.currentTarget;
    lintButton.firstElementChild.hidden = false;
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
            lintButton.firstElementChild.hidden = true;
        }
        );
}

function loadFile() {
    let file = this.files[0];
    if (!file || file.type !== "text/x-python") {
        alert("Upload Python file");
        return;
    }

    let reader = new FileReader();
    reader.onload = function () { editor.setValue(reader.result); }
    reader.readAsText(file);
    document.getElementById("problems-block").innerText = "";
}

function setup() {
    setupEditor();
    Split({
        minSize: 255,
        snapOffset: 0,
        columnGutters: [{
            track: 1,
            element: document.querySelector('#gutter'),
        }],
    });
    document.getElementById("analysisSubmit").addEventListener("click", analyze);
    document.getElementById('inputFile').addEventListener('change', loadFile);
}

document.addEventListener("DOMContentLoaded", setup)
