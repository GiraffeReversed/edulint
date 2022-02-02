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
            document.getElementById("problemGroup" + n).scrollIntoView(
                {
                    behavior: "smooth",
                    block: "center",
                }
            );
        }
    });
}

function makeMarker() {
    var marker = document.createElement("div");
    marker.classList.add("problemMarker");
    marker.innerHTML = "●";
    return marker;
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
    result += `<div class="button-group-vertical w-100">`;

    for (let i = 0; i < oneLineProblems.length; i++) {
        let problem = oneLineProblems[i];
        result +=
        `<div class="problem border-bottom w-100" id="problem${lineIndex}_${i}" data-line=${lineIndex}>
                <div class="btn-group problemBtn w-100" role="group">
                    <div class="p-1 small w-100 d-flex align-items-center">
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

    editor.doc.setGutterMarker(lineIndex, "breakpoints", makeMarker());
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
    let lineIndex = Number(problemInfoBtn.dataset.line);
    editor.addLineClass(lineIndex, "background", "highlighted-line");
    setTimeout(() => {
        editor.removeLineClass(lineIndex, "background", "highlighted-line")
    }, 1700);
    jumpToLine(lineIndex);
}

function problemClick(e) {
    let problemInfoBtn = e.currentTarget;
    if (problemInfoBtn.ariaExpanded === "true") {
        gotoCodeClick(e);
    }
}

function registerProblemCallbacks() {
    for (let problemInfoBtn of document.getElementsByClassName("problemInfoBtn")) {
        problemInfoBtn.addEventListener("click", problemClick);
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
        minSize: 240,
        columnGutters: [{
            track: 1,
            element: document.querySelector('#gutter'),
        }],
    });
    document.getElementById("analysisSubmit").addEventListener("click", analyze);
    document.getElementById('inputFile').addEventListener('change', loadFile);
}

document.addEventListener("DOMContentLoaded", setup)
