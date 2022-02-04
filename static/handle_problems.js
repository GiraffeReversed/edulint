'use strict';

let editor;
let EDITOR_LIGHT_THEME = "coda";
let EDITOR_DARK_THEME = "sunburst";

function assert(condition, message = "") {
    if (!condition) {
        throw message || "Assertion failed";
    }
}

function collectSelectedProblemGroups(from, to) {
    if (!to)
        to = from;

    let result = [];
    for (let i = from; i <= to; i++) {
        let info = editor.lineInfo(i);
        if (info.gutterMarkers) {
            let problemGroup = document.getElementById("problemGroup" + info.gutterMarkers.problemMarkers.dataset.line);
            result.push(problemGroup);
        }
    }
    return result;
}

function updateActiveProblems(problemGroups) {
    for (let problemGroup of document.querySelectorAll("#problems-block .problemGroup.active")) {
        problemGroup.classList.remove("active");
    }

    for (let problemGroup of problemGroups) {
        problemGroup.scrollIntoView(
            {
                behavior: "smooth",
                block: "nearest",
            }
        );
        problemGroup.classList.add("active");
    }
}

function markLinesSolved() {
    let from = editor.getCursor("from").line;
    let to = editor.getCursor("to").line;

    let problemGroups = collectSelectedProblemGroups(from, to);
    for (let problemGroup of problemGroups) {
        for (let problem of problemGroup.getElementsByClassName("problem")) {
            markSolved(problem.getElementsByClassName("problemSolvedBtn")[0]);
        }
    }
}

function setupEditor() {
    editor = CodeMirror.fromTextArea(code, {
        lineNumbers: true,
        styleActiveLine: true,
        gutters: ["problemMarkers", "CodeMirror-linenumbers"],
        rulers: [{ color: "#ddd", column: 79, lineStyle: "dotted" }],
        theme: darkmode.inDarkMode ? EDITOR_DARK_THEME : EDITOR_LIGHT_THEME
    });

    editor.on("gutterClick", (cm, n) => {
        var info = cm.lineInfo(n);
        if (info.gutterMarkers) {
            updateActiveProblems(collectSelectedProblemGroups(n));
        }
    });

    editor.on("cursorActivity", (cm) => {
        updateActiveProblems(collectSelectedProblemGroups(cm.getCursor("from").line, cm.getCursor("to").line));
    });

    editor.addKeyMap({
        "Ctrl-D": markLinesSolved
    });
}

function makeMarker(lineIndex) {
    var marker = document.createElement("div");
    marker.classList.add("problemMarker", "text-danger");
    marker.id = "problemMarker" + lineIndex;
    marker.dataset.line = lineIndex;
    marker.innerHTML = `<h5 class="bi bi-arrow-right-short"></h5>`;
    return marker;
}

function showAlert(type, message) {
    document.getElementById("messages").innerHTML +=
        `<div class="alert alert-${type} alert-dismissible fade show mb-2" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;
}

function getProblemMarker(problemLine, withFocus) {
    if (withFocus)
        jumpToLine(problemLine);
    let marker = document.getElementById("problemMarker" + problemLine);
    if (marker)
        return marker;

    for (let i = 0; i < editor.lineCount(); i++) {
        let gutterM = editor.lineInfo(i).gutterMarkers;
        if (gutterM && gutterM.problemMarkers.dataset.line == problemLine) {
            return gutterM.problemMarkers;
        }
    }

    return null;
}

function getCurrentLineIndex(problemLine) {
    let marker = getProblemMarker(problemLine, true);
    if (!marker)
        return null;

    return Number(marker.parentElement.previousElementSibling.innerText) - 1;
}

function oneLineProblemsHTML(oneLineProblems) {
    assert(oneLineProblems.length >= 1);

    let lineIndex = Number(oneLineProblems[0].line) - 1;
    let result =
        `<div id="problemGroup${lineIndex}" data-line=${lineIndex} class="problemGroup mb-2 btn-group rounded-3 w-100">`;
    result +=
        `<button class="btn btn-outline-warning problemGotoBtn p-1 px-2" type="button" data-line=${lineIndex}>
            <h5 class="bi bi-bullseye mb-0"></h5>
        </button>`;
    result += `<div class="d-flex flex-column w-100">`;

    for (let i = 0; i < oneLineProblems.length; i++) {
        let problem = oneLineProblems[i];
        result +=
            `<div class="problem border-bottom w-100 h-100 d-flex flex-column justify-content-center" id="problem${lineIndex}_${i}" data-line=${lineIndex}>
                <div class="btn-group problemBtn w-100 align-self-center" role="group">
                    <div class="problemText p-1 small w-100" id="problemText${lineIndex}_${i}">
                        ${problem.line}: ${problem.text}
                    </div>
                    <button class="btn btn-outline-secondary problemInfoBtn p-1" type="button" data-bs-toggle="collapse"
                        data-bs-target="#collapse${lineIndex}_${i}" aria-expanded="false" data-line=${lineIndex}
                        aria-controls="collapse${lineIndex}_${i}" id="heading${lineIndex}_${i}">
                        <h5 class="bi bi-chevron-down mb-0"></h5>
                    </button>
                    <button class="btn btn-outline-success problemSolvedBtn p-1" type="button" data-line=${lineIndex} data-solved=false>
                        <h5 class="bi bi-check2 mb-0"></h5>
                    </button>
                </div>
                <div id="collapse${lineIndex}_${i}" class="accordion-collapse collapse multi-collapse${lineIndex}"
                    aria-labelledby="heading${lineIndex}_${i}" data-bs-parent="#problemsAccordion">
                    <div class="accordion-body small">
                        WHY?!
                        <hr>
                        Examples
                        <hr>
                        <small>${problem.source} ${problem.code}</small>
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

function gotoCodeClick(problemInfoBtn) {
    let lineIndex = getCurrentLineIndex(Number(problemInfoBtn.dataset.line));
    if (!lineIndex) {
        showAlert("warning", "Line with this problem has been removed.");
        return;
    }

    editor.focus();
    jumpToLine(lineIndex);
    editor.setCursor({ line: lineIndex, ch: 0 });
}

function allSolved(problemGroup) {
    for (let btn of problemGroup.getElementsByClassName("problemSolvedBtn")) {
        if (btn.dataset.solved !== "true")
            return false;
    }
    return true;
}

function markSolved(btn) {
    if (btn.dataset.solved === "false") {
        btn.classList.replace("btn-outline-success", "btn-success");
        btn.dataset.solved = true;
    } else {
        btn.classList.replace("btn-success", "btn-outline-success");
        btn.dataset.solved = false;
    }

    let problemGroup = btn.closest(".problemGroup");
    let marker = getProblemMarker(problemGroup.dataset.line, false);
    if (allSolved(problemGroup)) {
        marker?.classList.add("text-success");
        marker?.classList.remove("text-danger");
        problemGroup.classList.add("solved");
    } else {
        marker?.classList.remove("text-success");
        marker?.classList.add("text-danger");
        problemGroup.classList.remove("solved");
    }
}

function problemTextClick(problemText) {
    let problem = problemText.closest(".problem");
    let problemGroup = problemText.closest(".problemGroup");
    if (window.localStorage.getItem("settingProblemClickHighlight") === "true") {
        updateActiveProblems([problemGroup]);
    }

    if (window.localStorage.getItem("settingProblemClickGoto") === "true") {
        problemGroup.getElementsByClassName("problemGotoBtn")[0].click();
    }

    if (window.localStorage.getItem("settingProblemClickInfo") === "true") {
        problem.getElementsByClassName("problemInfoBtn")[0].click();
    }

    if (window.localStorage.getItem("settingProblemClickSolve") === "true") {
        problem.getElementsByClassName("problemSolvedBtn")[0].click();
    }
}

function registerProblemCallbacks() {
    for (let problemInfoBtn of document.getElementsByClassName("problemInfoBtn")) {
        problemInfoBtn.addEventListener("click", e => gotoCodeClick(e.currentTarget));
    }

    for (let problemGotoBtn of document.getElementsByClassName("problemGotoBtn")) {
        problemGotoBtn.addEventListener("click", e => gotoCodeClick(e.currentTarget));
    }

    for (let problemSolvedBtn of document.getElementsByClassName("problemSolvedBtn")) {
        problemSolvedBtn.addEventListener("click", e => markSolved(e.currentTarget));
    }

    for (let problemText of document.getElementsByClassName("problemText")) {
        problemText.addEventListener("click", e => problemTextClick(e.currentTarget));
    }
}

function analyze(e) {
    let lintButton = e.currentTarget;
    lintButton.firstElementChild.hidden = false;
    let problemsBlock = document.getElementById("problems");
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
    document.getElementById("keybind").hidden = false;
}

function loadFile() {
    let file = this.files[0];
    if (!file || !file.name.endsWith(".py")) {
        showAlert("danger", `Select a <span class="font-monospace">.py</span> file.`);
        return;
    }

    let reader = new FileReader();
    reader.onload = function () { editor.setValue(reader.result); }
    reader.readAsText(file);
    document.getElementById("problems").innerText = "";
}

function resetFile() {
    this.value = null;
}

function initSetting(id, def) {
    let val = window.localStorage.getItem(id);
    let check = document.getElementById(id);

    if (val !== null) {
        check.checked = val === "true";
    } else {
        check.checked = def;
    }
    return check.checked;
}

function setDarkmodeToggle() {
    let darkmodeToggle = document.getElementById("settingDarkmode").firstElementChild;
    if (darkmode.inDarkMode) {
        darkmodeToggle.classList.replace("bi-moon-fill", "bi-sun-fill");
    } else {
        darkmodeToggle.classList.replace("bi-sun-fill", "bi-moon-fill");
    }
    document.getElementsByName("color-scheme")[0].content = darkmode.inDarkMode ? "dark" : "light";
}

function initSettings() {
    for (let [setting, def] of [["Highlight", true], ["Goto", true], ["Info", false], ["Solve", false]]) {
        let id = "settingProblemClick" + setting;
        let val = initSetting(id, def);
        window.localStorage.setItem(id, val);
    }
    setDarkmodeToggle();
}

function saveSettings() {
    for (let setting of ["Highlight", "Goto", "Info", "Solve"]) {
        let id = "settingProblemClick" + setting;
        let check = document.getElementById(id);
        window.localStorage.setItem(id, check.checked);
    }
}

function toggleDarkmode() {
    darkmode.toggleDarkMode();
    setDarkmodeToggle();
    editor.setOption("theme", darkmode.inDarkMode ? EDITOR_DARK_THEME : EDITOR_LIGHT_THEME);
}

function setup() {
    setupEditor();
    Split(['#code-block', '#problems-block'], {
        minSize: 250,
        snapOffset: 0,
        sizes: [60, 40],
    });
    document.getElementById("analysisSubmit").addEventListener("click", analyze);
    document.getElementById('inputFile').addEventListener('change', loadFile);
    document.getElementById('inputFile', false).addEventListener('click', resetFile);
    initSettings();
    document.getElementById("settingsSave").addEventListener("click", saveSettings);
    document.getElementById("settingDarkmode").addEventListener("click", toggleDarkmode);
}

document.addEventListener("DOMContentLoaded", setup)
