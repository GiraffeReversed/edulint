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


def code_path(code_hash: str) -> str:
    return full_path(code_hash) + ".py"


def problems_path(code_hash: str) -> str:
    return full_path(code_hash) + ".json"


@app.route("/")
def default_path():
    return redirect("editor", code=302)


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


@app.route("/editor", methods=["GET"])
def editor():
    return render_template("editor.html")


@app.route("/analyze/<string:code_hash>", methods=["GET"])
def analyze(code_hash: str):

    result = lint(code_path(code_hash))

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
