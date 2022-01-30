'use strict';

let editor;

function setupEditor() {
    editor = CodeMirror.fromTextArea(code, {
        lineNumbers: true,
        gutters: ["CodeMirror-linenumbers", "breakpoints"]
    });
    editor.setOption("theme", "base16-light");
    editor.on("gutterClick", function (cm, n) {
        let info = cm.lineInfo(n);
        cm.setGutterMarker(n, "breakpoints", info.gutterMarkers ? null : makeMarker());
        // editor.doc.setGutterMarker(11, "breakpoints", makeMarker());
    });
}

function analyze() {
    let problems = document.getElementById("problems-block");
    problems.innerHTML = ""
    fetch("/upload_code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            code: editor.getValue()
        })
    })
        .then(response => response.json()) // .json() for Objects vs text() for raw
        .then(data => {
            problems.innerHTML = "<ul>";
            for (let problem of data) {
                problems.innerHTML += "<li>" +
                    problem.source + " " + problem.line + ": " + problem.code + " " + problem.text +
                    "</li>"
            }
            problems.innerHTML += "</ul>"
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
