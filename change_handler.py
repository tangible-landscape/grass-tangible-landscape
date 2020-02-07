import os
from watchdog.events import FileSystemEventHandler


class SignalFileChangeHandler(FileSystemEventHandler):
    """Logs all the events captured."""
    def __init__(self, callback, filename):
        super(SignalFileChangeHandler, self).__init__()
        self.callback = callback
        self.filename = filename
        self.latest_timestamp = 0

    def on_modified(self, event):
        super(SignalFileChangeHandler, self).on_modified(event)
        if os.path.basename(event.src_path) == self.filename:
            tstamp = os.path.getmtime(event.src_path)
            if self.latest_timestamp != tstamp:
                self.callback()
                self.latest_timestamp = tstamp


class RasterChangeHandler(FileSystemEventHandler):
    """Logs all the events captured."""
    def __init__(self, callback, data):
        super(RasterChangeHandler, self).__init__()
        self.callback = callback
        self.data = data
        self.latest_timestamp = 0

    def on_created(self, event):
        super(RasterChangeHandler, self).on_created(event)
        if os.path.basename(event.src_path) == self.data['scan'] + 'tmp':
            tstamp = os.path.getmtime(event.src_path)
            if self.latest_timestamp != tstamp:
                self.callback()
                self.latest_timestamp = tstamp


class DrawingChangeHandler(FileSystemEventHandler):
    """Logs all the events captured."""
    def __init__(self, callback, data):
        super(DrawingChangeHandler, self).__init__()
        self.callback = callback
        self.data = data
        self.latest_timestamp = 0

    def on_created(self, event):
        super(DrawingChangeHandler, self).on_created(event)
        if os.path.basename(event.src_path) == self.data:
            tstamp = os.path.getmtime(event.src_path)
            if self.latest_timestamp != tstamp:
                self.callback()
                self.latest_timestamp = tstamp
