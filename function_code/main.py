import functions_framework

import google.auth.transport.requests
from google.auth.transport.requests import Request as GoogleRequestTransport
import google.oauth2.id_token
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
            forw_auth = request.form.get( 'forw_auth' )

            if self_url is None:
                raise Exception( "task is null" )

            if user is None:
                raise Exception( "user is null" )
            
            if forw_auth is None:
                raise Exception( "user auth is null" )

        except Exception as e:
            cloud_log( "user_ff.no_data", f"API called without informing data {e}" )
            return ( f'<output>no data - {tstamp}</output>', 200, response_headers )

        # call will fail if it is register but no Authorizaton header is sent
        auth_header = request.headers.get( "Authorization" )

        if auth_header is None:
            cloud_log( "user_ff.no_auth", f"Register attempt without authorization header" )
            return ( f'<output>Not authorized</output>', 401, response_headers )

        # ...fails if it is not valid (signed by Google)
        token = auth_header.split(' ')[ 1 ]

        try:
            id_info = token.verify_oauth2_token( token, GoogleRequestTransport(), audience = self_url )

        except Exception as e:
            cloud_log( "user_ff.invalid_reg_jwt", f"Register attempt with invalid authorization" )
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

        if self_url[ : 22 ] != f"ffacet-user-{sha256_hash}":
            cloud_log( "user_ff.invalid_sub", f"Register attempt with invalid user (sub)" )
            return ( f'<output>Not authorized</output>', 401, response_headers )

        # ... fails if this function name is not the one provided
        service_name = os.environ.get( 'K_SERVICE', 'localhost' )
        if self_url.replace( "https://", "" )[ : len( service_name )] != service_name:
            cloud_log( "user_ff.invalid_url", f"Register attempt with invalid function url" )
            return ( f'<output>Unprocessable Entity</output>', 422, response_headers )

        # if we get to this point, call central API and try to register this CF

        headers = { "Authorization": f"Bearer {forw_auth}" }
        payload = {
            "task": "register",
            "addr": self_url,
            "user": user,
            "prism": secrets.token_hex( 32 )
        }

        try:
            # call the API to register this user Your-Fable-Cloud instance
            r = requests.post( central_url, data = payload, headers = headers )

            r.raise_for_status() 
            return ( f'<output>Registered - {tstamp}</output>', 200, response_headers )

        except Exception as e:
            cloud_log( "user_ff.register_error", "Error while sending post request to FF" )
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
        "timestamp_ms": int(time.time() * 1000),
        "user_id": user_id
    }

    print( json.dumps( log_entry ))
