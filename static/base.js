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
    if (typeof editor !== "undefined")
        editor.setOption("theme", darkmode.inDarkMode ? EDITOR_DARK_THEME : EDITOR_LIGHT_THEME);
}

function baseSetup() {
    initSettings();
    document.getElementById("settingsSave").addEventListener("click", saveSettings);
    document.getElementById("settingDarkmode").addEventListener("click", toggleDarkmode);
}

document.addEventListener("DOMContentLoaded", baseSetup);