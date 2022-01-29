from flask import Flask, render_template, redirect, request, flash, url_for, jsonify
from uuid import uuid4
from edulint import lint
from typing import Optional
import os
import json
from datetime import datetime


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploaded_files"


def full_path(filename: str) -> str:
    return os.path.join(app.config["UPLOAD_FOLDER"], filename)


def new_filename() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S_") + str(uuid4())[:8]


@app.route("/")
def hello_world():
    return redirect("analyze", code=302)


@app.route("/upload_code", methods=["POST"])
def upload_code():
    filename = new_filename()
    with open(full_path(filename), "w", encoding="utf8") as f:
        f.write(request.form["code"])
    return redirect(url_for("analyze", file_id=filename))


@app.route("/upload_file", methods=["GET"])
def upload_get():
    return render_template("upload.html")


@app.route("/upload_file", methods=["POST"])
def upload_file():
    assert request.method == "POST"
    # check if the post request has the file part
    if "file" not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        filename = new_filename()
        file.save(full_path(filename))
        return redirect(url_for("analyze", file_id=filename))


@app.route("/analyze", methods=["GET"])
@app.route("/analyze/<string:file_id>", methods=["GET"])
def analyze(file_id: Optional[str] = None):
    if file_id is None:
        return render_template("analysis.html")
    result = lint(full_path(file_id))
    with open(full_path(file_id)) as f:
        contents = f.read()
    return render_template("analysis.html", problems=result, textarea_text=contents)


if __name__ == "__main__":
    app.run(debug=True)
