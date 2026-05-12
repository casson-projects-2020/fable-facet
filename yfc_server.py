from flask import Flask, render_template, request, redirect, jsonify, Response
import subprocess
import json
import sys
import uuid
import os
import logging

from google import genai
from google.api_core import exceptions

os.environ[ 'WERKEZUG_RUN_MAIN' ] = 'true' 
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

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


@app.route( '/get_email', methods=[ 'GET' ])
def get_email():
    # check if the account is not tied to an organization

    project = ""

    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project" ],
            capture_output = True,
            text = True,
            check = True
        )
        project = result.stdout.strip()

    except subprocess.CalledProcessError as e:
        # Caso o gcloud retorne erro (ex: sem conta configurada)
        print( f"Cannot run gcloud config get-value project: {e.stderr}")
        return "## error, please click restart"

    try:
        result = subprocess.run(
            ["gcloud", "projects", "get-ancestors", project ],
            capture_output = True,
            text = True,
            check = True
        )
        ancestors = result.stdout

    except subprocess.CalledProcessError as e:
        print( f"Cannot run gcloud projects get-ancestors {project}: {e.stderr}")
        return "## error, please click restart"

    # This license restriction is a security measure to ensure that secrets 
    # (such as your Gemini API keys) remain private. Privacy cannot be guaranteed 
    # if the account is managed by a third-party organization. 
    # Additionally, managing the Free Tier is complex; the presence of other 
    # organization-level resources could lead to unexpected Google Cloud charges. 
    # Bypassing this restriction makes the user solely responsible for any 
    # consequences, as per the Fable Facet Terms of Service on our website.
    if "organization" in ancestors:
        print( f"account is not personal {ancestors}")
        err_ = "## This GCP account is part of an organization. Fable Facet's"
        err_ += "license only allows personal accounts"

        return err_
    
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output = True,
            text = True,
            check = True
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        # Caso o gcloud retorne erro (ex: sem conta configurada)
        print(f"Cannot run gcloud config get-value account: {e.stderr}")
        return "## error, please click restart"


env = os.environ.copy()

@app.route('/validate_key', methods=['POST'])
def validate_key():
    data = request.json
    key = data.get( 'key' )

    if not key:
        return "no key", 400

    try:
        client = genai.Client( api_key = key )
        models = client.models.list()

        env[ "GEMINI_KEY" ] = key

        return "ok", 200

    except Exception as e:
        return "Invalid key", 401


@app.route( '/run_installer', methods=['POST'])
def yfc_installer_run():
    print( "running installer..." )


    subprocess.Popen(
        ['bash', 'yfc_install.sh'],
        env = env,
        stdout = None, 
        stderr = None,
        bufsize = 1
    )

    return jsonify(
    {
        'success': True, 
        'message': f"Installer running"
    }), 200


if __name__ == '__main__':
    app.run( host = '0.0.0.0', port=8080 )
