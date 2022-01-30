from flask import Flask, render_template, redirect, request, flash, url_for, jsonify
from edulint import lint, ProblemEncoder
import os
import json
from hashlib import sha256
from os import path


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
    code = request.get_json()["code"]
    code_hash = sha256(code.encode("utf8")).hexdigest()

    if not path.exists(code_path(code_hash)):
        with open(code_path(code_hash), "w", encoding="utf8") as f:
            f.write(code)

    return redirect(url_for("analyze", code_hash=code_hash))


@app.route("/upload_file", methods=["GET"])
def upload_get():
    return render_template("upload.html")


@app.route("/upload_file", methods=["POST"])
def upload_file():
    # check if the post request has the file part
    if "file" not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if not file or file.filename == "":
        flash('No selected file')
        return redirect(request.url)

    code_hash = sha256(file.read()).hexdigest()

    if not path.exists(code_path(code_hash)):
        file.save(code_path(code_hash))

    return redirect(url_for("analyze", code_hash=code_hash))


@app.route("/editor", methods=["GET"])
def editor():
    return render_template("editor.html")


@app.route("/analyze/<string:code_hash>", methods=["GET"])
def analyze(code_hash: str):
    if not code_hash.isalnum():
        return {"message": "Don't even try"}, 400

    if not path.exists(code_path(code_hash)):
        flash('No such file uploaded')
        return redirect("editor", code=302)

    if path.exists(problems_path(code_hash)):
        with open(problems_path(code_hash), encoding="utf8") as f:
            return f.read()

    result = lint(code_path(code_hash))
    with open(problems_path(code_hash), "w", encoding="utf8") as f:
        f.write(json.dumps(result, cls=ProblemEncoder))

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
