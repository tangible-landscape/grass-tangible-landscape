#!/usr/bin/env python
import os
import socket
import sys
import ssl
import tempfile
import shutil
import atexit
from thread import start_new_thread
from threading import Event
import select
import time

import grass.script as gscript

from tangible_utils import get_environment


def run_model(settings, steering):
    model = settings.pop('model_name')
    if steering:
        settings['ip_address'] = 'localhost'
        settings['port'] = port_computation
    region = settings.pop('region').split(',')
    env = get_environment(n=region[0], s=region[1], w=region[2], e=region[3], align=region[4])
    flags = settings.pop('flags')
    gscript.run_command('g.remove', flags='fe', type='raster', quiet=True,
                        pattern=settings['output_series'] + '_[0-9]{4}_[0-9]{2}_[0-9]{2}')
    p = gscript.start_command(model, overwrite=True, flags=flags, env=env, **settings)

    return p


def clientInterface(conn, connections, event, steering):
    # Sending message to connected client
    conn.sendall('Welcome to the server.\n')
    # have file list to be sent one after the other
    sod_process = None
    # infinite loop so that function do not terminate and thread do not end.
    _debug_file = open('/tmp/debugServer.txt', 'w')
    while True:
        # receiving from client
        data = conn.recv(1024)
        message = data.split(':')
        if message[0] == 'clientfile':
            # receive file
            fsize, path = int(message[1]), message[2]
            conn.sendall(data)
            server_path = os.path.join(tmp_directory, os.path.basename(path))
            name = os.path.basename(path).split('.')[0]
            f = open(server_path, 'wb')
            data = conn.recv(1024)
            total_received = len(data)
            f.write(data)
            while(total_received < fsize):
                data = conn.recv(1024)
                total_received += len(data)
                f.write(data)
            f.close()
            gscript.run_command('r.unpack', input=server_path, output=name, overwrite=True)
#            if 'computation' in connections:
#                connections['computation'].sendall('load:{}'.format(name) + ';')
            conn.sendall('info:received')
        if message[0] == 'serverfile':
            fsize, path = int(message[1]), message[2]
            with open(path, 'rb') as f:
                data = f.read()
#                try:
                conn.sendall(data)
#                except socket.error:
#                    print 'erroro sending file'
                event.set()
        if message[0] == 'cmd':
            if message[1] == 'start':
                params = {}
                if len(message) == 3:  # additional parameters
                    for each in message[2].split('|'):
                        key, val = each.split('=')
                        try:
                            params[key] = float(val)
                        except ValueError:
                            params[key] = val
                if 'computation' not in connections:
                    if steering:
                        sod_process = run_model(params, True)
                    else:
                        sod_process = run_model(params, False)
                        start_new_thread(check_output, (connections['interface'], params['output_series'], sod_process, event))
            elif message[1] == 'end':
                print "server: get stop from GUI"
                if 'computation' in connections:
                    print "server: send stop from GUI to SOD"
                    connections['computation'].sendall('cmd:stop;')
                    sod_process.wait()
                    sod_process = None

                    connections['computation'].close()
                    del connections['computation']
            elif message[1] == 'restart':
                print "server: get restart from GUI"
                if 'computation' in connections:
                    print "server: send stop from GUI to SOD"
                    connections['computation'].sendall('cmd:stop;')
                    sod_process.wait()
                    sod_process = None
                    connections['computation'].close()
                    del connections['computation']
                # start again
                params = {}
                for each in message[2].split('|'):
                    key, val = each.split('=')
                    try:
                        params[key] = float(val)
                    except ValueError:
                        params[key] = val
                sod_process = run_model(params, True)
            elif message[1] == 'play':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:play;')
            elif message[1] == 'pause':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:pause;')
                conn.sendall('info:received')
            elif message[1] == 'stepf':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:stepf;')
                conn.sendall('info:received')
            elif message[1] == 'stepb':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:stepb;')
                conn.sendall('info:received')
            elif message[1] == 'goto':
                if 'computation' in connections:
                    connections['computation'].sendall('goto:' + message[2] + ';')
                conn.sendall('info:received')
            elif message[1] == 'sync':
                if 'computation' in connections:
                    connections['computation'].sendall('sync;')
                conn.sendall('info:received')
        elif message[0] == 'load':
            if 'computation' in connections:
                connections['computation'].sendall('load:' + message[1] + ':' + message[2] + ';')
                conn.sendall('info:received')
        elif message[0] == 'info':
            if message[1] == 'model_running':
                if 'interface' in connections:
                    try:
                        if sod_process and sod_process.poll() is None:
                            print 'sod_processes is running'
                            connections['interface'].sendall('info:model_running:yes')
                        else:
                            print 'sod_processes is not running'
                            connections['interface'].sendall('info:model_running:no')
                            print 'sod_processes is not running after'
                    except socket.error:
                        print "timeout"
                        break

        # client closed
        if not data:
            break
    # came out of loop
    conn.shutdown(socket.SHUT_WR)
    conn.close()
    del connections['interface']


def check_output(connection, basename, sod_process, event):
    _debug_file = open('/tmp/debugCheck.txt', 'w')
    old_found = []
    event.set()
    is_running = True
    _debug(_debug_file, basename)
    while is_running:
        is_running = sod_process.poll() is None
        time.sleep(0.1)
        # should catch both infected and probability
        found = gscript.list_grouped(type='raster', flag='e',
                                     pattern=basename + '_[0-9]{4}_[0-9]{2}_[0-9]{2}')[gscript.gisenv()['MAPSET']]
        last = None
        if found:
            last = found[-1]
        for each in found:
            if each not in old_found:
                event.wait(5)
                pack_path = os.path.join(tmp_directory, each + '.pack')
                gscript.run_command('r.pack', input=each, output=pack_path, overwrite=True)
                event.clear()
                connection.sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
                old_found.append(each)
                _debug(_debug_file, 'serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path) + '\n')
        if not is_running:
            event.wait(5)
            _debug(_debug_file, 'info:last:' + last)
            connection.sendall('info:last:' + last)
    sod_process.wait()
    sod_process = None


def clientComputation(conn, connections, event):
    # Sending message to connected client
    conn.sendall('Welcome to the server.\n')  # send only takes string
    # this event blocks sending messages to GUI
    # when GUI expects files
    event.set()
    while True:
        event.wait(5)
        data = conn.recv(2000)
        message = data.split('|')
        for m in message:
            lm = m.split(':')
            event.wait(5)
            if lm[0] == 'output':
                # r.pack
                pack_path = os.path.join(tmp_directory, lm[1] + '.pack')
                gscript.run_command('r.pack', input=lm[1], output=pack_path, overwrite=True)
                if 'interface' in connections:
                    event.clear()
                    connections['interface'].sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
            elif lm[0] == 'info':
                if lm[1] == 'last':
                    connections['interface'].sendall(m)

        if not data:
            break

    # came out of loop
    conn.close()


def _debug(dfile, message):
        """Write debug file"""
        dfile.write(message + '\n')
        dfile.flush()


def cleanup():
    shutil.rmtree(tmp_directory)


if __name__ == '__main__':
    if len(sys.argv) == 4:
        port_interface = int(sys.argv[1])
        port_computation = int(sys.argv[2])
        local_gdbase = int(sys.argv[3])
    elif len(sys.argv) == 3:
        port_interface = int(sys.argv[1])
        local_gdbase = int(sys.argv[2])
        port_computation = None
    else:
        print 'Incorrect number of arguments, is {a1}, should be {a2}'.format(a1=len(sys.argv) - 1, a2=" 2 or 3")
        sys.exit(1)

    host = ''   # Symbolic name, meaning all available interfaces

    tmp_directory = tempfile.mkdtemp()
    atexit.register(cleanup)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if port_computation:
        s_c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_c.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    else:
        s_c = None
    print 'Sockets created'

    # Bind socket to local host and port
    try:
        s.bind((host, port_interface))
    except socket.error as msg:
        print 'Bind ' + str(port_interface) + ' failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
        sys.exit(1)

    # Bind socket to local host and port
    if s_c:
        try:
            s_c.bind((host, port_computation))
        except socket.error as msg:
            print 'Bind ' + str(port_computation) + ' failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
            sys.exit(1)

    print 'Sockets bind complete'

    # Start listening on socket
    s.listen(10)
    if s_c:
        s_c.listen(10)
    print 'Socket now listening'
    connections = {}

    event = Event()
    while True:
        if s_c:
            read, write, error = select.select([s, s_c], [s, s_c], [])
        else:
            read, write, error = select.select([s, ], [s, ], [])
        for r in read:
            conn, addr = r.accept()
            if r == s:
    #            conn = ssl.wrap_socket(conn, server_side=True, cert_reqs=ssl.CERT_REQUIRED,
    #                                 ca_certs="/etc/ssl/certs/SOD.crt",
    #                                 certfile="/etc/ssl/certs/server.crt",
    #                                 keyfile="/etc/ssl/private/server.key")
                connections['interface'] = conn
                start_new_thread(clientInterface, (conn, connections, event, bool(s_c)))
            elif r == s_c:
                connections['computation'] = conn
                start_new_thread(clientComputation, (conn, connections, event))
