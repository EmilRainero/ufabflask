import os
from flask import Flask, render_template, request, flash, redirect, send_from_directory, session
from werkzeug.utils import secure_filename
from ufab import run_part, generate_html, materials
from shutil import copyfile

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.debug = True

UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['step', 'stp'])


@app.route('/')
def hello_world(name=None):
    return render_template('index.html', name=name)

@app.route('/file/<directory>/<name>')
def get_file(directory, name):
    full_directory_path = os.path.join('/tmp', 'ufab', 'output', directory)
    return send_from_directory(full_directory_path, name)

@app.route('/preview/<directory>/<name>')
def preview_file(directory, name):
    # return 'Preview ' + directory + ' ' + name
    url = '/file/{0}/{1}'.format(directory, name)
    return render_template('ufab.html', url=url)

@app.route('/hello/')
def hello():
    return 'Hello'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run(full_filename, material, query):
    save_directory = os.getcwd()
    os.chdir('/ufab/uFab-kernel/uFab.kernel/buildsOptimized/bin')

    output_folders, plans_output = run_part(full_filename, material, query)
    part_directory, part_filename = os.path.split(full_filename)
    part_base_name, part_extension = os.path.splitext(part_filename)
    part_excel = os.path.join(part_directory, part_base_name) + '.xlsx'

    os.chdir(save_directory)
    return part_excel, output_folders[0], plans_output

def generate_preview(output_folder, plans_output, excel_filename):
    html = generate_html(output_folder, plans_output, excel_filename)
    return html

def process_file(filename, command, material, query):
    excel_filename, output_folder, plans_output = run(filename, material, query)
    part_directory, part_filename = os.path.split(excel_filename)
    session['part_filename'] = part_filename
    if command == 'excel':
        return send_from_directory(part_directory, part_filename)
    else:
        # copy file from excel_filensame to directory output_folder
        excel_basename = os.path.basename(excel_filename)
        destination_filename = os.path.join(output_folder, excel_basename)
        copyfile(excel_filename, destination_filename)
        return generate_preview(output_folder, plans_output, excel_basename)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        command = request.form['command']
        material = request.form['material']
        query = request.form['query']
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            tmp_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(tmp_filename)
            return process_file(tmp_filename, command, material, query)
        else:
            return 'File type not supported'
    return 'No file.'

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(port=5000)
