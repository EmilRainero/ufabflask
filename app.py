import os
import subprocess
from flask import Flask, render_template, request, flash, redirect, send_from_directory
from werkzeug.utils import secure_filename
from ufab import run_part

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['step', 'stp'])


@app.route('/')
def hello_world(name=None):
    return render_template('index.html', name=name)

@app.route('/hello/')
@app.route('/hello/<name>')
def hello(name=None):
    return render_template('index.html', name=name)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run(full_filename):
    save_directory = os.getcwd()
    os.chdir('/ufab/uFab-kernel/uFab.kernel/builds/bin')

    run_part(full_filename)
    part_directory, part_filename = os.path.split(full_filename)
    part_base_name, part_extension = os.path.splitext(part_filename)
    part_excel = os.path.join(part_directory, part_base_name) + '.xlsx'
    print(part_directory, part_base_name, part_extension, part_excel)

    os.chdir(save_directory)
    return part_excel

def process_file(filename):
    print('Process file', filename)
    excel_filename = run(filename)
    part_directory, part_filename = os.path.split(excel_filename)
    return send_from_directory(part_directory, part_filename)
    # return render_template('generateplans.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            tmp_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print('Saving file', tmp_filename)
            file.save(tmp_filename)
            return process_file(tmp_filename)
        else:
            return 'File type not supported'
    return 'No file.'

if __name__ == '__main__':
    app.run()
