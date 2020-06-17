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
from queue import Queue

import wx.lib.newevent
import grass.script as gscript

ProcessForDashboardEvent, EVT_PROCESS_FOR_DASHBOARD_EVENT = wx.lib.newevent.NewEvent()
BaselineDoneEvent, EVT_BASELINE_DONE = wx.lib.newevent.NewEvent()


class SteeringClient:
    def __init__(self, url, port_interface, port_simulation,
                 launch_server, local_gdbase=True, log=None, eventHandler=None):
        self._socket = socket.socket()
        self._threading_event = threading.Event()
        self._local_gdbase = local_gdbase
        self._log = log
        self._eventHandler = eventHandler
        if not url:
            return
        url = url.replace('http://', '')
        self._url = [url, port_interface]

        self._simulation_is_running = False
        self._results_queue = Queue()
        self._client_thread = None
        self._is_client_running = False
        self._tmp_directory = tempfile.mkdtemp()
        self._simulation_done = None
        self._step_done = None
        self._server = None
        self._debug_file = open('/tmp/debug.txt', 'wb')
        self._steering = True
        self._model_params = ''
        self._baseline_params = ''
        self._baseline_computing = False
        if launch_server:
            # should be list
            if port_simulation:
                self._server = subprocess.Popen(['python', launch_server, str(port_interface), str(port_simulation), str(int(local_gdbase))])
            else:
                self._server = subprocess.Popen(['python', launch_server, str(port_interface), str(int(local_gdbase))])
            time.sleep(1)
            relaunch = False
            if self._server.poll() == 1:
                for port in (port_interface, port_simulation):
                    if port:
                        self._kill_process(port)
                        relaunch = True
            time.sleep(1)
            if relaunch:
                if port_simulation:
                    self._server = subprocess.Popen(['python', launch_server, str(port_interface), str(port_simulation), str(int(local_gdbase))])
                else:
                    self._server = subprocess.Popen(['python', launch_server, str(port_interface), str(int(local_gdbase))])
                time.sleep(1)

    def _debug(self, message):
        """Write debug file"""
        if type(message) != bytes:
            message = message.encode()
        self._debug_file.write(message)
        self._debug_file.write(b'\n')
        self._debug_file.flush()

    def _kill_process(self, port):
        """Kill process on specified port, may be dangerous if somebody else is using it."""
        res = subprocess.Popen("netstat -tulpn|grep " + str(port), shell=True, stdout=subprocess.PIPE).communicate()
        if res[0]:
            pid = res[0].strip().split()[-1].split(b'/')[0].decode()
            subprocess.Popen("kill " + pid, shell=True)

    def connect(self):
        try:
            self._socket.connect((self._url[0], int(self._url[1])))
        except socket.error as exc:
            if self._log:
                self._log.WriteError("Error connecting to steering server: {}".format(exc))
            self._socket = None
            self._is_client_running = False
            return False
#        self.s = ssl.wrap_socket(self.s, cert_reqs=ssl.CERT_REQUIRED,
#                                 certfile="/etc/ssl/certs/SOD.crt",
#                                 keyfile="/etc/ssl/private/ssl-cert-snakeoil.key",
#                                 ca_certs="/etc/ssl/certs/test_certificate.crt")
        self._is_client_running = True
        self._client_thread = threading.Thread(target=self._client, args=(self._results_queue, self._threading_event))
        self._client_thread.start()
        return True

    def disconnect(self):
        self._is_client_running = False
        try:
            # send message to server that we finish sending
            # then we receive empty response, see above
            if self._socket:
                self._socket.shutdown(socket.SHUT_WR)
        except socket.error as e:
            print (e)
            pass
        # wait for ending the thread
        if self._client_thread and self._client_thread.isAlive():
            self._client_thread.join()
        self._socket = None
        try:
            shutil.rmtree(self._tmp_directory)
            os.remove(self._debug_file.name)
        except:
            pass

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

            message = data.split(b':')
            self._debug(data)
            if message[0] == b'clientfile':
                _, fsize, path = message
                with open(message[2].decode(), 'rb') as f:
                    data = f.read()
                    try:
                        self._sendall(data)
                    except socket.error:
                        print ('erroro sending file')
            elif message[0] == b'serverfile':
                # receive file
                fsize, path = int(message[1]), message[2].decode()
                self._sendall(data)
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
                try:
                    gscript.run_command('r.unpack', input=new_path, overwrite=True, quiet=True)
                except:
                    self._debug('failed r.unpack '+ new_path)
                name = os.path.basename(path).replace('.pack', '')
                # avoid showing aggregate result
                # event_player_year_month_day
                self._debug('serverfile: ' + name)
                if re.search('[0-9]*_[0-9]*_[0-9]*$', name):
                    self._debug('_step_done: ' + name)
                    if not self._baseline_computing:
                        results_queue.put(name)
                        if self._eventHandler:
                            evt = ProcessForDashboardEvent(name=name)
                            wx.PostEvent(self._eventHandler, evt)

                ##########
            elif message[0] == b'info':
                if message[1] == b'output':
                    name = message[2].decode()
                    if re.search('[0-9]*_[0-9]*_[0-9]*$', name):
                        results_queue.put(name)
                        if self._eventHandler:
                            evt = ProcessForDashboardEvent(name=name)
                            wx.PostEvent(self._eventHandler, evt)
                    self._sendall('info:received')
                elif message[1] == b'last':
                    if self._simulation_done:
                        name = message[2].decode()
                        self._simulation_done(name)
                elif message[1] == b'received':
                    event.set()
                elif message[1] == b'model_running':
                    self._simulation_is_running = True if message[2] == b'yes' else False
                    event.set()
                elif message[1] == b'baseline':
                    if self._eventHandler:
                        evt = BaselineDoneEvent()
                        wx.PostEvent(self._eventHandler, evt)
                        self._baseline_computing = False

    def _wait_for_confirmation(self):
        self._threading_event.clear()
        self._threading_event.wait(5)

    def _sendall(self, message):
        if type(message) != bytes:
            message = message.encode()
        self._socket.sendall(message)

    def set_steering(self, steering):
        self._steering = steering

    def simulation_set_params(self, model_name, params, flags, region):
        message = "model_name=" + model_name
        message += "|region=" + region
        if flags:
            message += "|flags=" + flags
        for key in params:
            message += '|'
            message += '{k}={v}'.format(k=key, v=params[key])
        self._model_params = message

    def baseline_set_params(self, model_name, params, flags, region):
        message = "model_name=" + model_name
        message += "|region=" + region
        if flags:
            message += "|flags=" + flags
        for key in params:
            message += '|'
            message += '{k}={v}'.format(k=key, v=params[key])
        self._baseline_params = message

    def simulation_start(self, restart=False):
        if not self._steering:
            return

        if restart:
            message = 'cmd:restart:'
        else:
            message = 'cmd:start:'

        self._sendall(message + self._model_params)

    def simulation_stop(self):
        self._sendall('cmd:end')

    def simulation_play(self):
        if self._steering:
            self._sendall('cmd:play')
        else:
            self._sendall('cmd:start:' + self._model_params)

    def simulation_pause(self):
        self._sendall('cmd:pause')
        self._wait_for_confirmation()

    def simulation_stepf(self):
        self._sendall('cmd:stepf')
        self._wait_for_confirmation()

    def simulation_stepb(self):
        self._sendall('cmd:stepb')
        self._wait_for_confirmation()

    def simulation_goto(self, step):
        self._sendall('cmd:goto:' + str(step))
        self._wait_for_confirmation()

    def simulation_send_data(self, layer_name, file_name, env):
        if self._local_gdbase:
            return
        self._debug('simulation_send_data')
        path = os.path.join(self._tmp_directory, file_name + '.pack')
        gscript.run_command('r.pack', input=layer_name, output=path, env=env)
        self._sendall('clientfile:{}:{}'.format(os.path.getsize(path), path))
        self._wait_for_confirmation()

    def simulation_load_data(self, name, date, length, application):
        self._debug('simulation_load_data')
        if self._steering:
            self._sendall('load:{n}:{d}:{l}:{a}'.format(n=name, d=date, l=length, a=application))
            self._wait_for_confirmation()
        else:
            self._model_params += '|' + '{k}={v}'.format(k='treatments', v=name)
            self._model_params += '|' + '{k}={v}'.format(k='treatment_date', v=date)

    def simulation_sync_runs(self):
        self._sendall('cmd:sync')
        self._wait_for_confirmation()

    def simulation_is_running(self):
        self._debug('simulation_is_running')
        if self._is_client_running:
            self._sendall('info:model_running')
            self._wait_for_confirmation()
            return self._simulation_is_running
        return False

    def compute_baseline(self):
        self._sendall('baseline:' + self._baseline_params)
        self._baseline_computing = True

    def set_on_done(self, func):
        self._simulation_done = func

    def results_clear(self):
        with self._results_queue.mutex:
            self._results_queue.queue.clear()

    def results_empty(self):
        return self._results_queue.empty()

    def results_get(self):
        return self._results_queue.get()

    def is_steering(self):
        return self._steering
