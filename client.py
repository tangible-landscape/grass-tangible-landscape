# -*- coding: utf-8 -*-
"""
@brief POPS steering client

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author: Anna Petrasova (akratoc@ncsu.edu)
"""
import os
import tempfile
import shutil
import time
import re
import socket
import threading
import subprocess
import Queue

import grass.script as gscript


class SteeringClient:
    def __init__(self, url, launch_server, log=None):
        self._socket = socket.socket()
        self._threading_event = threading.Event()
        self._log = log
        if not url:
            return
        url = url.replace('http://', '')
        self._url = url.split(':')

        self._simulation_is_running = False
        self._results_queue = Queue.Queue()
        self._client_thread = None
        self._is_client_running = False
        self._tmp_directory = tempfile.mkdtemp()
        self._simulation_done = None
        self._server = None
        if launch_server:
            # should be list
            self._server = subprocess.Popen(['python'] + [str(each) for each in launch_server])
            time.sleep(1)

    def connect(self):
        try:
            self._socket.connect((self._url[0], int(self._url[1])))
        except socket.error, exc:
            if self._log:
                self._log.WriteError("Error connecting to steering server: {}".format(exc))
            self._socket = None
            return
#        self.s = ssl.wrap_socket(self.s, cert_reqs=ssl.CERT_REQUIRED,
#                                 certfile="/etc/ssl/certs/SOD.crt",
#                                 keyfile="/etc/ssl/private/ssl-cert-snakeoil.key",
#                                 ca_certs="/etc/ssl/certs/test_certificate.crt")
        self._is_client_running = True
        self._client_thread = threading.Thread(target=self._client, args=(self._results_queue, self._threading_event))
        self._client_thread.start()

    def disconnect(self):
        self._is_client_running = False
        try:
            # send message to server that we finish sending
            # then we receive empty response, see above
            if self._socket:
                self._socket.shutdown(socket.SHUT_WR)
        except socket.error, e:
            print e
            pass
        # wait for ending the thread
        if self._client_thread and self._client_thread.isAlive():
            self._client_thread.join()
        self._socket = None

        shutil.rmtree(self._tmp_directory)

    def stop_server(self):
        if self._server:
            self._server.terminate()

    def _client(self, results_queue, event):
        while self._is_client_running:
            data = self._socket.recv(1024)
            if not data:
                # GUI received close from server
                # finish while loop
                self._socket.close()
                continue

            message = data.split(':')
            if message[0] == 'clientfile':
                _, fsize, path = message
                with open(message[2], 'rb') as f:
                    data = f.read()
                    try:
                        self._socket.sendall(data)
                    except socket.error:
                        print 'erroro sending file'
            elif message[0] == 'serverfile':
                # receive file
                fsize, path = int(message[1]), message[2]
                self._socket.sendall(data)
                data = self._socket.recv(1024)
                total_received = len(data)
                new_path = os.path.join(self._tmp_directory, os.path.basename(path))
                f = open(new_path, 'wb')
                f.write(data)
                while(total_received < fsize):
                    data = self._socket.recv(1024)
                    total_received += len(data)
                    f.write(data)
                f.close()

                gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
                name = os.path.basename(path).replace('.pack', '')
                # avoid showing aggregate result
                # event_player_year_month_day
                if re.search('[0-9]*_[0-9]*_[0-9]*$', name):
                    results_queue.put(name)

                ##########
            elif message[0] == 'info':
                if message[1] == 'last':
                    if self._simulation_done:
                        name = message[2]
                        self._simulation_done(name)
                elif message[1] == 'received':
                    event.set()
                elif message[1] == 'model_running':
                    self._simulation_is_running = True if message[2] == 'yes' else False
                    event.set()

    def _wait_for_confirmation(self):
        self._threading_event.clear()
        self._threading_event.wait(2000)

    def simulation_start(self, params, region, restart=False):
        if restart:
            message = 'cmd:restart:'
        else:
            message = 'cmd:start:'
        message += "region=" + region
        for key in params:
            message += '|'
            message += '{k}={v}'.format(k=key, v=params[key])
        self._socket.sendall(message)

    def simulation_stop(self):
        self._socket.sendall('cmd:end')

    def simulation_play(self):
        self._socket.sendall('cmd:play')

    def simulation_pause(self):
        self._socket.sendall('cmd:pause')
        self._wait_for_confirmation()

    def simulation_stepf(self):
        self._socket.sendall('cmd:stepf')
        self._wait_for_confirmation()

    def simulation_stepb(self):
        self._socket.sendall('cmd:stepb')
        self._wait_for_confirmation()

    def simulation_goto(self, step):
        self._socket.sendall('cmd:goto:'+ str(step))
        self._wait_for_confirmation()

    def simulation_send_data(self, layer_name, file_name, env):
        path = os.path.join(self._tmp_directory, file_name + '.pack')
        gscript.run_command('r.pack', input=layer_name, output=path, env=env)
        self._socket.sendall('clientfile:{}:{}'.format(os.path.getsize(path), path))
        self._wait_for_confirmation()

    def simulation_load_data(self, step, name):
        self._socket.sendall('load:' + str(step) + ':' + name)
        self._wait_for_confirmation()

    def simulation_sync_runs(self):
        self._socket.sendall('cmd:sync')
        self._wait_for_confirmation()

    def simulation_is_running(self):
        self._socket.sendall('info:model_running')
        self._wait_for_confirmation()
        return self._simulation_is_running

    def set_on_done(self, func):
        self._simulation_done = func

    def results_clear(self):
        with self._results_queue.mutex:
            self._results_queue.queue.clear()

    def results_empty(self):
        return self._results_queue.empty()

    def results_get(self):
        return self._results_queue.get()
