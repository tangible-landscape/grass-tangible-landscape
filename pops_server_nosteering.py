#!/usr/bin/env python
import os
import socket
import sys
import ssl
from thread import start_new_thread
from threading import Event
import select
import time

import grass.script as gscript

from tangible_utils import get_environment

HOST = ''   # Symbolic name, meaning all available interfaces
PORT = 8888  # Arbitrary non-privileged port
PORT_C = 8000

TMP_DIR = '/tmp/server'
try:
    os.mkdir(TMP_DIR)
except OSError:
    pass

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print 'Sockets created'

# Bind socket to local host and port
try:
    s.bind((HOST, PORT))
except socket.error as msg:
    print 'Bind ' + str(PORT) + ' failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
    sys.exit()

# Bind socket to local host and port
try:
    s_c.bind((HOST, PORT_C))
except socket.error as msg:
    print 'Bind ' + str(PORT_C) + ' failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
    sys.exit()

print 'Sockets bind complete'

# Start listening on socket
s.listen(10)
s_c.listen(10)
print 'Socket now listening'
connections = {}


def run_baseline(settings):
    model = 'r.spread.pest.steering'
    params = {}
    params['nprocs'] = 10
#    params['ip_address'] = 'localhost'
#    params['port'] = 8000
    region = settings.pop('region')
    region = region.split(',')
    env = get_environment(n=region[0], s=region[1], w=region[2], e=region[3], align=region[4])
    params.update(settings)
    print 'computing baseline'

    gscript.run_command(model, overwrite=True, env=env, **params)
    return params['output']


def run_model(settings):
    model = 'r.spread.pest.steering'
    params = {}
    params['nprocs'] = 10
    params['ip_address'] = 'localhost'
    params['port'] = 8000
    region = settings.pop('region')
    region = region.split(',')
    env = get_environment(n=region[0], s=region[1], w=region[2], e=region[3], align=region[4])
    params.update(settings)
    name = settings['output_series']
    gscript.run_command(model, overwrite=True, flags='l', env=env, **params)
    names = gscript.read_command('g.list', mapset='.', pattern="{n}_*".format(n=name), type='raster', separator='comma').strip()
    gscript.run_command('t.create', output=name, type='strds', temporaltype='relative',
                        title='SOD', description='SOD', overwrite=True)
    gscript.run_command('t.register', input=name, maps=names.split(','), start=2000, unit='years', increment=1, overwrite=True)

    return name


def run_model_nonblocking(settings):
    model = 'r.spread.pest.steering'
    params = {}
    params['nprocs'] = 10
    params['ip_address'] = 'localhost'
    params['port'] = 8000
    region = settings.pop('region')
    region = region.split(',')
    env = get_environment(n=region[0], s=region[1], w=region[2], e=region[3], align=region[4])
    params.update(settings)
    p = gscript.start_command(model, overwrite=True, flags='l', env=env, **params)

    return p


def clientGUI(conn, connections, event):
    # Sending message to connected client
    conn.sendall('Welcome to the server.\n')
    # have file list to be sent one after the other
    sod_process = None
    # infinite loop so that function do not terminate and thread do not end.
    while True:
        # receiving from client
        data = conn.recv(1024)
        message = data.split(':')
        if message[0] == 'clientfile':
            # receive file
            fsize, path = int(message[1]), message[2]
            conn.sendall(data)
            server_path = os.path.join(TMP_DIR, os.path.basename(path))
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
                try:
                    conn.sendall(data)
                except socket.error:
                    print 'erroro sending file'
                event.set()
        if message[0] == 'cmd':
            print message
                # series
#                pack_path = TMP_DIR + params['output_series']
#                gscript.run_command('t.rast.export', input=name, output=pack_path, format='pack', quiet=True, overwrite=True)
#
#                if 'GUI' in connections:
#                    connections['GUI'].sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))


                    #connections['GUI'].sendall('info:last:' + names[-1])
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
                    sod_process = run_model_nonblocking(params)
            elif message[1] == 'baseline':
                print message
                if len(message) == 3:  # additional parameters
                    params = {}
                    for each in message[2].split('|'):
                        key, val = each.split('=')
                        try:
                            params[key] = float(val)
                        except ValueError:
                            params[key] = val
                    name = run_baseline(params)
                    pack_path = os.path.join(TMP_DIR, name + '.pack')
                    gscript.run_command('r.pack', input=name, output=pack_path, overwrite=True)
                    if 'GUI' in connections:
                        connections['GUI'].sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
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
                sod_process = run_model_nonblocking(params)
            elif message[1] == 'play':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:play;')
            elif message[1] == 'pause':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:pause;')
            elif message[1] == 'stepf':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:stepf;')
            elif message[1] == 'stepb':
                if 'computation' in connections:
                    connections['computation'].sendall('cmd:stepb;')
            elif message[1] == 'goto':
                connections['computation'].sendall('goto:' + message[2] + ';')
                conn.sendall('info:received')
            elif message[1] == 'sync':
                connections['computation'].sendall('sync;')
                conn.sendall('info:received')
        elif message[0] == 'load':
            if 'computation' in connections:
                connections['computation'].sendall('load:' + message[1] + ':' + message[2] + ';')
                conn.sendall('info:received')
        elif message[0] == 'info':
            if message[1] == 'model_running':
                if 'GUI' in connections:
                    if sod_process :
                        connections['GUI'].sendall('info:model_running:yes')
                    else:
                        connections['GUI'].sendall('info:model_running:no')

        # client closed
        if not data:
            break
    # came out of loop
    conn.shutdown(socket.SHUT_WR)
    conn.close()
    del connections['GUI']


def checkOutput(connection, basename, sod_process, event):
    old_found = []
    event.set()
    while sod_process.poll() is None:
        time.sleep(0.1)
        found = gscript.list_grouped(type='raster', pattern=basename + '_*')[gscript.gisenv()['MAPSET']]
        for each in found:
            if each not in old_found:
                event.wait(2000)
                pack_path = os.path.join(TMP_DIR, each + '.pack')
                gscript.run_command('r.pack', input=each, output=pack_path, overwrite=True)
                event.clear()
                connection.sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
                old_found.append(each)
    sod_process.wait()
    sod_process = None
    pack_path = os.path.join(TMP_DIR, basename + '.pack')
    gscript.run_command('r.pack', input=basename, output=pack_path, overwrite=True)
    event.wait(2000)
    event.clear()
    connection.sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
    event.wait(2000)
    connection.sendall('info:last:' + basename)


def clientComputation(conn, connections, event):
    # Sending message to connected client
    conn.sendall('Welcome to the server.\n')  # send only takes string
    # this event blocks sending messages to GUI
    # when GUI expects files
    event.set()
    while True:
        event.wait(2000)
        data = conn.recv(200)
        message = data.split('|')
        for m in message:
            lm = m.split(':')
            event.wait(2000)
            if lm[0] == 'output':
                # r.pack
                pack_path = os.path.join(TMP_DIR, lm[1] + '.pack')
                gscript.run_command('r.pack', input=lm[1], output=pack_path, overwrite=True)
                if 'GUI' in connections:
                    event.clear()
                    connections['GUI'].sendall('serverfile:{}:{}'.format(os.path.getsize(pack_path), pack_path))
            elif lm[0] == 'info':
                if lm[1] == 'last':
                    connections['GUI'].sendall(m)

        if not data:
            break

    # came out of loop
    conn.close()

event = Event()
while True:
    read, write, error = select.select([s, s_c], [s, s_c], [])
    for r in read:
        conn, addr = r.accept()
        if r == s:
#            conn = ssl.wrap_socket(conn, server_side=True, cert_reqs=ssl.CERT_REQUIRED,
#                                 ca_certs="/etc/ssl/certs/SOD.crt",
#                                 certfile="/etc/ssl/certs/server.crt",
#                                 keyfile="/etc/ssl/private/server.key")
            connections['GUI'] = conn
            start_new_thread(clientGUI, (conn, connections, event))
        else:
            connections['computation'] = conn
            start_new_thread(clientComputation, (conn, connections, event))
