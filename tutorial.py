from flask import Flask, render_template, request, redirect, jsonify, Response
import subprocess
import json
import sys
import uuid


app = Flask(__name__)


def get_projects():
    result = subprocess.run(
        ['gcloud', 'projects', 'list', '--format=json'],
        capture_output=True, text=True
    )
    return json.loads( result.stdout )


@app.route('/')
def index():
    projects = get_projects()
    return render_template( 'index.html', projects = projects )


@app.route( '/set-project', methods=['POST'])
def set_project():

    data = request.json
    project_name_id = data.get( 'name_id' ).split( "(" )
    project_id = project_name_id[ 1 ].replace( ")", "" ).strip()

    try:
        subprocess.run(
            ['gcloud', 'config', 'set', 'project', project_id],
            stdout=sys.stdout,
            stderr=sys.stderr
        )

        return jsonify(
        {
            'success': True, 
            'message': f"Project '{project_id}' selected"
        }), 200

    except Exception as e:
        return jsonify(
        {
            'success': False, 
            'error': f"gcloud failed to select the project {e}"
        }), 500


@app.route('/create-project', methods=['POST'])
def create_project():
    data = request.json
    project_name = data.get( 'name' )

    invalid = True
    attempts = 0
    while invalid:
        invalid = False

        project_id = project_name[ : 20 ] + "-" + uuid.uuid4().hex[ :9 ]
        print( project_name + " " + project_id )

        check = subprocess.run(
                [ 'gcloud', 'projects', 'describe', project_id ],
                capture_output=True, text=True
        )

        if check.returncode == 0: # error, project already exists
            print( "project already exists" )
            if attempts > 10:
                return jsonify({
                    'success': False, 
                    'error': "gcloud failed to create the project"
                }), 500
            else:
                attempts += 1
            invalid = True
        else:
            print( "project id is unique and can be used" )

    try:
        subprocess.run(
            [ 'gcloud', 'projects', 'create', project_id, f'--name={project_name}'],
            stdout=sys.stdout, 
            stderr=sys.stderr,
            check=True
        )

        subprocess.run(
            [ 'gcloud', 'config', 'set', 'project', project_id ],
            stdout=sys.stdout, 
            stderr=sys.stderr 
        )

        return jsonify(
        {
            'success': True, 
            'message': f"Project '{project_name}' created and selected"
        }), 200

    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f"gcloud failed to create the project {e}"
        }), 500


@app.route('/installer_run', methods=['POST'])
def yfc_installer_run():
    print( "running installer..." )

    subprocess.run([ 'chmod', '+x', 'entrypoint.sh' ])
    subprocess.Popen(
        ['./entrypoint.sh'],
        stdout=None, 
        stderr=None,
        bufsize=1
    )

    return jsonify(
    {
        'success': True, 
        'message': f"Installer running"
    }), 200


if __name__ == '__main__':
    app.run( host = '0.0.0.0', port=8080 )
