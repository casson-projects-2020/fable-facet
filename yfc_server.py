from flask import Flask, render_template, request, redirect, jsonify, Response
import subprocess
import json
import sys
import uuid
import os
import logging
import shutil


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


fatal_error = False


def billing_problems( project_id ):
    global fatal_error
 
    # verifica se o projeto ja tem uma billing account
    result = subprocess.run(
        ['gcloud', 'billing', 'projects', 'describe', project_id, '--format=json' ],
        capture_output = True, text=True
    )
    print( "billing_problems", "'gcloud', 'billing', 'projects', 'describe', project_id, '--format=json'" )
    print( "result.stdout", result.stdout )
    billing = json.loads( result.stdout.strip())
    
    if( billing[ "billingEnabled" ] != True ):
        # obtem a conta q foi criada antes de rodar este script e associa ao projeto
        result = subprocess.run(
            ["gcloud", "billing", "accounts", "list", "--format=json"],
            capture_output = True, text = True, check = True
        )
        accounts = json.loads( result.stdout )

        if not accounts:
            print( "No billing account detected", flush = True )
            err_ = "&#x274c;&#xFE0F; Fatal Error: No billing account detected. Your-Fable-Cloud "
            err_ += "requires one to function. <br/>Please follow the instructions to set up a "
            err_ += "Billing Account on Fable Facet website."
            fatal_error = True
            
            return jsonify(
            {
                'success': False, 
                'error': err_
            }), 500

        else:
            active_acc = next(( a for a in accounts if a.get( "open" )), None )
            acc_name = active_acc[ "name" ]
            acc_id = acc_name[ acc_name.find( "/" ) + 1 : ]
        
            subprocess.run(
                [   'gcloud', 'billing', 'projects', 'link', 
                    project_id, '--billing-account', acc_id ],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            
            return None


@app.route( '/set-project', methods=['POST'])
def set_project():
    data = request.json
    project_name_id = data.get( 'name_id' ).split( "(" )
    
    print( "set_project", "project_id = project_name_id[ 1 ].replace( ')', '' ).strip()" )
    print( "project_name_id", project_name_id )

    project_id = project_name_id[ 1 ].replace( ")", "" ).strip()

    try:
        subprocess.run(
            ['gcloud', 'config', 'set', 'project', project_id],
            stdout=sys.stdout,
            stderr=sys.stderr
        )

        if ( res := billing_problems( project_id )) is None:
            return jsonify(
            {
                'success': True, 
                'message': f"Project '{project_id}' selected"
            }), 200
        else:
            return res

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
        print( project_name + " " + project_id, flush = True )

        check = subprocess.run(
                [ 'gcloud', 'projects', 'describe', project_id ],
                capture_output=True, text=True
        )

        if check.returncode == 0: # error, project already exists
            print( "project already exists", flush = True )
            if attempts > 10:
                return jsonify({
                    'success': False, 
                    'error': "gcloud failed to create the project"
                }), 500
            else:
                attempts += 1
            invalid = True
        else:
            print( "project id is unique and can be used", flush = True )

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

        if ( res := billing_problems( project_id )) is None:
            return jsonify(
            {
                'success': True, 
                'message': f"Project '{project_id}' created and selected"
            }), 200
        else:
            return res

    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f"gcloud failed to create the project {e}"
        }), 500


@app.route( '/get_email', methods=[ 'GET' ])
def get_email():
    # check if the account is not tied to an organization
    global fatal_error

    project = ""

    try:
        result = subprocess.run(
            ["gcloud", "billing", "accounts", "list", "--format=json"],
            capture_output = True, text = True, check = True
        )
        accounts = json.loads( result.stdout )

        # Do not remove this restriction. If no billing account is detected, 
        # it means you haven't linked one or your account is not personal. 
        # Several APIs used in YFC require an active Billing Account even 
        # when using the $300 free credits or the Always Free tier. 
        # Without it, Google will block requests, but Fable Facet might not 
        # be able to display the specific error message. Furthermore, if 
        # your account is not personal and you lack permissions to run this 
        # command, Fable Facet cannot guarantee the privacy of your secrets 
        # (such as Gemini API Keys). This could lead to unauthorized quota 
        # usage, for which Fable Facet is not responsible. 
        # Please use a personal account as instructed on the website.
        if not accounts:
            print( "No billing account detected", flush = True )
            err_ = "&#x274c;&#xFE0F; Fatal Error: No billing account detected. Your-Fable-Cloud "
            err_ += "requires one to function. <br/>Please follow the instructions to set up a "
            err_ += "Billing Account on Fable Facet website."
            fatal_error = True
            return err_

    except Exception as e:
        err_ = f"Cannot run gcloud billing accounts list: {e.stderr}"
        print( err_, flush = True )
        return f"? error, please click restart [{err_}]"
                    
        # Currencies that indicate that Gemini Free Tier is not provided
        restricted_currencies = [
            "EUR", # Europe
            "GBP", # United Kingdom
            "CHF", # Switzerland and Liechtenstein
            "PLN", # Poland
            "SEK", # Sweden
            "NOK", # Norway
            "DKK", # Denmark
            "CZK", # Czech Republic
            "HUF", # Hungary
            "BGN", # Bulgaria
            "RON", # Romania
            "ISK"  # Iceland
        ]    
    
        # Do not remove this restriction. If you live in an area where 
        # Gemini Free Tier is unavailable, using this system will result in 
        # charges to your GCP billing account, for which Fable Facet 
        # is not responsible.
        active_acc = next(( a for a in accounts if a.get( "open" )), None )
        if active_acc and active_acc.get( "currencyCode" ) in restricted_currencies:
            err_ = f"&#x274c;&#xFE0F; Fatal Error: currency [{active_acc.get('currencyCode')}] "
            err_ += "indicates a region (EEA/UK/CH) where Gemini Free Tier is "
            err_ += "unavailable. Your-Fable-Cloud will not work."
            fatal_error = True
            return 
    
    try:
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'account'],
            capture_output = True, text = True, check = True
        )
        
        print( "get_email", "'gcloud', 'config', 'get-value', 'account'" )
        print( "result.stdout", result.stdout )

        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        err_ = f"Cannot run gcloud config get-value account: {e.stderr}"
        print( err_, flush = True )
        return f"? error, please click restart [{err_}]"


env = os.environ.copy()


@app.route( '/run_installer', methods=['GET'])
def yfc_installer_run():
    global fatal_error

    def generate( fatal_error_loc ):
        outp = ""

        if not fatal_error_loc:
            yield "data: running installer...\n\n";

            process = subprocess.Popen(
                ['bash', 'yfc_install.sh'],
                env = env,
                stdout = subprocess.PIPE,
                stderr = subprocess.STDOUT, 
                text = True,
                bufsize = 1,
                universal_newlines = True
            )

            try:
                while True:
                  line = process.stdout.readline()
                  if not line and process.poll() is not None:
                      break
                  if line:
                      yield f"data: {line}\n\n"
                        
                process.wait()

            finally:
                # check for errors
                if process.returncode != 0:
                    outp = "installer failed, starting rollback...";
                else:
                    outp = ""
                process.terminate() 
                process.wait()

        else:
            outp = "installer failed, starting rollback...";
        
        # Envia uma mensagem de finalização para o JS saber que acabou antes do crash
        yield f"data: internal_status:finished_{'ok' if not outp else 'error'}\n\n"
        
        # erase the folder fable-facet inside cloudshell_open to avoid
        # conflicts if the user ever try to install again
        cwd = os.getcwd()
        home_dir = os.path.expanduser( "~" )
        safe_ = os.path.join( home_dir, "cloudshell_open" )
        is_target = "fable-facet" in os.path.basename( cwd ) 
    
        cmd = f"""
(
sleep 2
"""
        if os.path.commonpath([ cwd, safe_ ]) == safe_ and cwd != safe_ and is_target:
            cmd += f"rm -rf '{cwd}'\n"

            if outp != "":
                cmd += "Fatal Error: "
            
            cmd += f"Removing repo folder: {cwd}\nclear\n"

        if outp != "":
            cmd += """) | dialog --cr-wrap --msgbox "Success: 
Your-Fable-Cloud is installed. Get back to Fable Facet site to use it\n\n
this script created one bucket on Cloud Storage, and one Cloud Run Function.\n
If you want to uninstall it, see instructions on Fable Facet site site:\n
in Tech section, 'How to delete my account'\n\n
You can now close the browser tab and Cloud Shell and return to Fable Facet site
" 20 60 > /dev/tty && clear
""" 
        else:
            cmd += """) | dialog --cr-wrap --msgbox "Fatal Error: 
cannot install Your-Fable-Cloud.\n\n
If the error appears to be temporaty you may try to install again.\n
Close the browser tab and Cloud Shell and return to Fable Facet site\n\n
Please contact us." 20 60 > /dev/tty && clear
""" 
        subprocess.Popen( cmd, shell = True )

        # send os._exit(0) after a small delay to allow Flask to send 
        # the last package in the connection
        import _thread
        def kill_later():
            import time
            time.sleep( 2 )
            os._exit( 0 )

        _thread.start_new_thread( kill_later, ())


    return Response( generate( fatal_error ), mimetype='text/event-stream' )


if __name__ == '__main__':
    app.run( host = '0.0.0.0', port=8080 )
