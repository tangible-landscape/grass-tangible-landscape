import os
from watchdog.events import FileSystemEventHandler

class RasterChangeHandler(FileSystemEventHandler):
    """Logs all the events captured."""
    def __init__(self, callback, data):
        super(RasterChangeHandler, self).__init__()
        self.callback = callback
        self.data = data

    def on_created(self, event):
        super(RasterChangeHandler, self).on_created(event)
        if os.path.basename(event.src_path) == self.data['scan'] + 'tmp':
            self.callback()


class DrawingChangeHandler(FileSystemEventHandler):
    """Logs all the events captured."""
    def __init__(self, callback, data):
        super(DrawingChangeHandler, self).__init__()
        self.callback = callback
        self.data = data

    def on_created(self, event):
        super(DrawingChangeHandler, self).on_created(event)
        if os.path.basename(event.src_path) == self.data:
            self.callback()
