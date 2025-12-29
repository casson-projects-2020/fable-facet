import functions_framework


from google.auth.transport.requests import Request as GoogleRequestTransport
from google.oauth2 import id_token
import hashlib
import json
import os
import requests
import secrets
import time


_ = """

Installation        Fable Facet
    |                    |
    |------------------->|
    |  register (OIDC)   | * JWT identity token assures the CF is registered for the correct user
    |   data( email )    |    - email recorded independently on API after oauth's JWT validation
    |   data( CF name)   |    - FF will not replace the registration after it is done (one-time-only)
    |<-------------------|    - CF name registered will have email hash on the name 
    |   ok               |     

"""

@functions_framework.http
def main( request ):
    central_url = "https://api.fablefacet.com"

    tstamp = int( time.time())

    response_headers = {
        'Content-Type': 'text/html'
    }

    if request.method == 'GET':
        return land_page(), 200


    # may be null - register don't use it
    prism = request.form.get( 'prism' )

    try:
        task = request.form.get( 'task' )
        if task is None:
            raise Exception( "task is null" )

    except Exception as e:
        cloud_log( "user_ff.no_task", "API called without informing task" )
        return ( f'<output>no task - {tstamp}</output>', 200, response_headers )


    if task == "register":
        try:
            self_url = request.form.get( 'self' )
            user = request.form.get( 'user' )
            auth_header = request.form.get( 'token' )

            if self_url is None:
                raise Exception( "self is null" )

            if user is None:
                raise Exception( "user is null" )

            if auth_header is None:
                raise Exception( "token is null" )

        except Exception as e:
            cloud_log( "user_ff.no_data", f"API called without informing data: {e}" )
            return ( f'<output>no data - {tstamp}</output>', 200, response_headers )

        # call will fail if it is not valid (signed by Google)
        try:
            id_info = id_token.verify_oauth2_token( auth_header, GoogleRequestTransport())

        except Exception as e:
            cloud_log( "user_ff.invalid_reg_jwt", f"Register attempt with invalid authorization {e}" )
            return ( f'<output>Not authorized</output>', 401, response_headers )

        # ... fails if the token email is not in the one provided
        user_id = id_info[ "sub" ]
        token_email = id_info[ "email" ]

        if user != token_email:
            cloud_log( "user_ff.invalid_user", f"Register attempt with invalid user" )
            return ( f'<output>Not authorized</output>', 401, response_headers )

        # ... fails if the token sub is not in the function name provided
        sub_str = str( user_id ).strip()
        sha256_hash = hashlib.sha256( sub_str.encode( 'utf-8' )).hexdigest()
        sha256_hash = sha256_hash[ :10 ]

        if self_url.startswith( f"https://ffacet-user-{sha256_hash}" ) == False:
            # Google has two different naming schemes for CFs, detect...
            if self_url.rstrip( "/" ).endswith( f"ffacet-user-{sha256_hash}" ) == False :
                cloud_log( "user_ff.invalid_sub", f"Register attempt with invalid user (sub)" )
                return ( f'<output>Not authorized</output>', 401, response_headers )

        # ... fails if this function name is not the one provided
        service_name = os.environ.get( 'K_SERVICE', 'localhost' )
        clean_url = self_url.replace( "https://", "" ).rstrip( "/" )

        if clean_url.startswith( service_name ) == False:
            # Google has two different naming schemes for CFs, detect...
            if clean_url.split( '/' )[-1] != service_name:
                cloud_log( "user_ff.invalid_url", f"Register attempt with invalid function url" )
                return ( f'<output>Unprocessable Entity</output>', 422, response_headers )

        # if we get to this point, call central API and try to register this CF
            # forwarding the JWT
        payload = {
            "task": "register",
            "addr": self_url,
            "user": user,
            "prism": auth_header
        }

        try:
            # call the API to register this user Your-Fable-Cloud instance
            r = requests.post( central_url, data = payload )

            r.raise_for_status() 
            return ( f'<output>Registered - {tstamp}</output>', 200, response_headers )

        except Exception as e:
            cloud_log( "user_ff.register_error", f"Error while sending post request to FF: {e}" )
            return ( f'<output>Error trying to register - {tstamp}</output>', 200, response_headers )


    # all other tasks needs the prism
    if prism is None:
        cloud_log( "user_ff.no_prims", "API called without informing prism" )
        return ( f'<output>no prism - {tstamp}</output>', 200, response_headers )


    return ( f'<output>Invalid call - {tstamp}</output>', 200, response_headers )


def cloud_log( tipo_erro, mensagem, user_id = None, warning = None ):
    # objeto de log (JSON Payload)
    log_entry = {
        "severity": "ERROR" if warning is None else "WARNING", 
        "event_type": tipo_erro,
        "message": mensagem,
        "timestamp_ms": int( time.time() * 1000 ),
        "user_id": user_id
    }

    print( json.dumps( log_entry ))


def land_page():
    return """
<!DOCTYPE html>
<html>
<head>
<link rel="preconnect" href="https://fonts.googleapis.com" /> 
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="true" />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Blinker:wght@100;200;300;400;600;700;800;900&amp;display=block" 
crossorigin="true" />
<style>
*
{   box-sizing: border-box;   }
:root
{
    /* cores do tema */
    --theme-darkest: rgb( 0, 16, 0 );
    --theme-dark: rgb( 0, 22, 0 );
    --theme-dark-op0: rgba( 0, 22, 0, 0 );
    --theme-medium: rgb( 0, 32, 0 );
    --theme-light: rgb( 0, 42, 0 );
    --theme-lighter: rgb( 0, 47, 0 );
    --theme-lightest: rgb( 0, 122, 0 );
    --theme-megalight: rgb( 120, 200, 120 );
    --theme-ultralight: #B0FFB0;
}
html
{
    scrollbar-color: rgb( 0, 42, 0 );
    scrollbar-width: thin;
}
body
{   
    padding: 0px;
    line-height: 1.5;
}
form
{
    padding: 12px;
    background-color: var( --theme-ultralight );
    border-radius: 8px;
}
input[type='text']
{
    padding: 8px;
    width: 95%;
    margin: 10px;
}
label
{
    color: var( --theme-darkest );
    margin-right: 10px;
    font-family: Blinker, sans-serif;
}
button[type='button']
{
    padding: 12px;
    background-color: var( --theme-light );
    border-radius: 6px;
    color: white;
    border: none;
    cursor: pointer;
}
form span
{
    font-family: Blinker, sans-serif;
}
p
{
    font-family: Blinker, sans-serif;
    font-size: 1rem;
    color: white;
    font-weight: 300;
}
</style>
<script>
window.addEventListener( "message", (event) => 
{
    if( event.origin != 'https://cliente.fablefacet.com' ) return;

    if( event.data.type == 'content' ) 
    {   var parser = new DOMParser();
        var doc = parser.parseFromString( event.data.payload, "text/html" );

        // well-formed markdown (ffacet flavor)
        var elems = doc.body.children;
        if( doc.body.children[ 0 ].tagName == "MAIN" )
            elems = doc.body.children[ 0 ].children;

        Array.from( elems ).forEach( elem_ => document.body.appendChild( elem_ ));
        document.body.appendChild( document.createElement( "br" ));
        document.body.appendChild( document.createElement( "br" ));

        // check if there are data to send to the controller
        var button = document.querySelector( "button[type='button']" );
        if( button != undefined )
        {
            button.addEventListener( "click", (event) =>
            {   
                var data = "";
                document.querySelectorAll( "input" ).forEach( el_ =>
                {   data += el_.outerHTML.replace( ">", "" ) +
                        ' value="' + el_.value + '">';
                });
                var msg = { type: 'IFRAME_DATA', payload: data };
                window.parent.postMessage( msg, 'https://cliente.fablefacet.com' );
            });
        }
    }
    if( event.data.type == 'data_ack' ) 
    {   var form = document.querySelector( "form" );
        if( form != undefined ) form.remove();
    }
    if( event.data.type == 'font_size' ) 
    {   const font_size = parseInt( event.data.payload );
        if( font_size <= 150 && font_size >= 80 )
        {   if( document.body?.font_style == undefined )
            {
                document.body.font_style = document.createElement( "style" );
                document.body.font_style.textContent = "body p{ font-size: 100%; }";
                document.head.appendChild( document.body.font_style );
            }
            document.body.font_style.textContent = "body p{ font-size: " + font_size + "%; }";
        }
    }
});
window.parent.postMessage({ type: 'IFRAME_READY' }, 'https://cliente.fablefacet.com' );
console.log( "enviado o ready" );
</script>
</head>
<body>
</body>
</html>
"""

