from flask import Flask, render_template, request, redirect, jsonify, Response
import subprocess
import json
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
    project_name_id = data.get( 'name' ).split( "(" )
    project_id = project_name_id[ 1 ].replace( ")", "" ).trim()

    try:
        subprocess.run([ 'gcloud', 'config', 'set', 'project', project_id ])
        return jsonify(
        {
            'success': True, 
            'message': f"Project '{project_id}' selected"
        }), 200

    except subprocess.CalledProcessError as e:
        return jsonify(
        {
            'success': False, 
            'error': "gcloud failed to select the project"
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
        subprocess.run([ 'gcloud', 'projects', 'create', project_id, f'--name={project_name}' ], check=True )
        subprocess.run([ 'gcloud', 'config', 'set', 'project', project_id ], check=True )
        
        return jsonify(
        {
            'success': True, 
            'message': f"Project '{project_name}' created and selected"
        }), 200
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False, 
            'error': "gcloud failed to create the project"
        }), 500


def install():
    process = subprocess.Popen(
        [ './entrypoint.sh' ], 
        stdout = subprocess.PIPE, 
        stderr = subprocess.STDOUT, 
        text = True,
        bufsize=1
    )

    for line in iter( process.stdout.readline, "" ):
        yield f"data: {line}\n\n"

    process.stdout.close()
    yield "data: [INSTALLATION COMPLETED]\n\n"


@app.route('/stream-logs')
def stream_logs():
    subprocess.run([ 'clear' ])
    subprocess.run([ 'chmod', '+x', 'entrypoint.sh' ])

    # Retorna a resposta com o mimetype especial para streaming
    return Response( install(), mimetype='text/event-stream' )


if __name__ == '__main__':
    app.run( host = '0.0.0.0', port=8080 )
