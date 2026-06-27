import asyncio
import http
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import time

subnet = "10.10.1."
server_lock = asyncio.Lock()
active_websocket = None

# triangle must be received from the cloud function
key_string = "0" * 64

try:
    with open("/opt/app-ff/.triangle", "r" ) as f:
        content = f.read().strip()
        if content:
            key_string = f.read().strip()
except FileNotFoundError:
    pass

triangle = AESGCM( bytes.fromhex( key_string ))


async def process_request( connection, request ):
    global triangle, subnet, active_websocket

    headers = request.headers

    is_websocket_handshake = (
        "upgrade" in headers.get( "Connection", "" ).lower() and 
        headers.get( "Upgrade", "" ).lower() == "websocket"
    )

    if is_websocket_handshake:
        return None  # it is a websocket request, go to handle_connection

    conn_ip = connection.remote_address[ 0 ]

    if conn_ip.startswith( subnet ):
        token = headers.get( "X-Triangle-Token" )

        if not token:
            # it is an attack or irregular call - http from the VPC must inform a new triangle
            connection.transport.close()
            # empty/fake response just to follow the function signature
            # - but here the connection is already closed
            return ( http.HTTPStatus.NOT_ACCEPTABLE, [], b"" )

        async with server_lock:
            if active_websocket:
                # 1012 code is for "Service Restart" - we know that the socket is half-dead because
                # a new key will only be sent in a new login, and in this case there is no socket 
                # on the client yet
                await active_websocket.close( code = 1012, reason = "Key rotating" )
                active_websocket = None

            triangle = AESGCM( bytes.fromhex( token ))

            with open("/opt/app-ff/.triangle", "w" ) as f:
                f.write( token )

            return (
                http.HTTPStatus.OK,
                [( "Content-Type", "text/plain; charset=utf-8" )],
                "OK".encode("utf-8" )
            )

    # it is an attack or irregular call - no http from the internet is accepted
    connection.transport.close()
    return ( http.HTTPStatus.NOT_ACCEPTABLE, [], b"" )


async def handle_connection( websocket, path = None ):
    global key_string, triangle, server_lock, active_websocket

    if server_lock.locked():
        # just 1 socket
        websocket.writer.close()
        return

    # we cannot open a socket if there is no key
    if key_string == "0" * 64:
        websocket.writer.close()
        return

    headers = websocket.request_headers

    signed_token = headers.get( "X-Access-Token" )
    real_ip = headers.get( "CF-Connecting-IP" )

    if not signed_token or not real_ip:
        # it is an attack, or incorrect request - do not generate egress
        # (to avoid burn the 1GiB egress free limit)
        websocket.writer.close()
        return

    try:
        token_bytes = bytes.fromhex( signed_token )
        iv = token_bytes[ :12 ]
        ciphertext = token_bytes[ 12: ]

        decrypted_meta = triangle.decrypt( iv, ciphertext, None ).decode()
        # expected: "IP:TIMESTAMP" (ex: "200.100.50.1:1719435600")
        token_ip, token_timestamp = decrypted_meta.split( ":" )

        if token_ip != real_ip or ( time.time() - float( token_timestamp )) > 30:
            raise ValueError( "Expired Token or IP mismatch" )

    except Exception:
        # it is an attack, or incorret request - all requests to open a socket must have
        # the security tokens
        websocket.writer.close()
        return

    async with server_lock:
        # renew conn if the underlying channel is lost
        if active_websocket is not None:
            # kill the half-dead previous socket without sendind egress or awaiting
            active_websocket.writer.close()
            active_websocket = None

        active_websocket = websocket

    try:
        async for message in active_websocket:
            if isinstance( message, bytes ):
                try:
                    iv = message[ :12 ]
                    ciphertext_with_tag = message[ 12: ]

                    decrypted_data = triangle.decrypt( iv, ciphertext_with_tag, None )

                    with open("/opt/app-ff/arquivo_recebido.bin", "ab" ) as f:
                        f.write( decrypted_data )

                    await active_websocket.send( "ACK" )

                except Exception as e:
                    # TODO: DEBUG: trocar por active_websocket.close(code=1012, reason="crypto") + break
                    await active_websocket.send( f"crypto: {str(e)}" )

    except websockets.exceptions.ConnectionClosed:
        pass


async def main():
    port = 8080 
    async with websockets.serve(
            handle_connection, 
            "0.0.0.0", 
            port, 
            backlog = 1, 
            process_request = process_request,
            ping_interval=20,  
            ping_timeout=20  
        ):
    
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
