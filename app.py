import os
import re
from flask import Flask, render_template, request, flash, redirect, send_from_directory, session
from werkzeug.utils import secure_filename
from ufab import run_part, generate_html, make_medium_machine_json
from shutil import copyfile
from threading import Lock
from tempfile import mkstemp
import json

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.debug = True

UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['step', 'stp'])

job_id = 0
lock = Lock()

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

def run(full_filename, material, query, machine_filename):
    global job_id
    print('JOBID:', job_id)
    job_id = job_id + 1

    # print('acquiring lock')
    # lock.acquire()
    # print('got lock')
    save_directory = os.getcwd()
    os.chdir('/ufab/uFab-kernel/uFab.kernel/buildsOptimized/bin')

    output_folders, plans_output = run_part(full_filename, material, query, machine_filename, job_id)
    part_directory, part_filename = os.path.split(full_filename)
    part_base_name, part_extension = os.path.splitext(part_filename)
    part_excel = os.path.join(part_directory, part_base_name) + '.xlsx'

    os.chdir(save_directory)
    # print('releasing lock')
    # lock.release()

    output_folder = output_folders[0][0]
    output_data = output_folders[0][1]
    output_text = output_data['Output']

    # remove color coding
    output_text = re.sub('\033\[1;\d+m', '', output_text)
    output_filename = os.path.join(output_folder, 'output.txt')
    with open(output_filename, 'w') as file:
        file.write(output_text)

    return part_excel, output_folder, plans_output

def generate_preview(output_folder, plans_output, excel_filename):
    html = generate_html(output_folder, plans_output, excel_filename)
    return html

def process_file(filename, command, material, query, machine_filename):
    excel_filename, output_folder, plans_output = run(filename, material, query, machine_filename)
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
        billing_rate = request.form['billing_rate']
        stage_time = request.form['stage_time']
        load_unload_time = request.form['load_unload_time']
        tool_change_time = request.form['tool_change_time']

        dimensions_x = request.form['dimensions_x']
        dimensions_y = request.form['dimensions_y']
        dimensions_z = request.form['dimensions_z']

        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            tmp_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(tmp_filename)

            machine = make_medium_machine_json(billing_rate, stage_time, load_unload_time, tool_change_time, dimensions_x, dimensions_y, dimensions_z)
            print(machine)

            fd, machine_filename = mkstemp(prefix="machine-", suffix='.json', dir='/tmp', text=True)
            print(machine_filename)
            file = open(machine_filename, 'w')
            machine_json = json.dumps(machine, sort_keys=True, indent=4)
            print(machine_json)
            file.write(machine_json)
            file.close()
            os.close(fd)

            return process_file(tmp_filename, command, material, query, machine_filename)
        else:
            return 'File type not supported'
    return 'No file.'

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(port=5000)
