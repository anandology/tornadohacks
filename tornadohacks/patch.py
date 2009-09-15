"""Patch Tornado ioloop to support SocketThreads.
"""
import tornado.ioloop

def patch_tornado():
    """Patch Tornado ioloop to support SocketThreads.
    """
    tornado.ioloop.IOLoop._instance = IOLoop()

class SocketThread:
    """In Tornado http server, the stream of execution are associated with sockets. 
    This class provides thread like interface for those streams of execution.
    """
    def __init__(self, fd, parent):
        self.fd = fd
        self.parent = parent
        self.local = None

    def get_local(self):
        if self.local is not None:
            return self.local
        else:
            return self.parent and self.parent.get_local()

class IOLoop(tornado.ioloop.IOLoop):
    """IOLoop extension to support SocketThreads."""
    def __init__(self, impl=None):
        self.threads = {}
        self._current_thread = None
        tornado.ioloop.IOLoop.__init__(self, impl)

    def add_handler(self, fd, handler, events):
        def xhandler(_fd, _events):
            self._current_thread = self.threads[_fd]
            return handler(_fd, _events)

        self.threads[fd] = SocketThread(fd, self._current_thread)
        tornado.ioloop.IOLoop.add_handler(self, fd, xhandler, events)

    def remove_handler(self, fd):
        tornado.ioloop.IOLoop.remove_handler(self, fd)
        del self.threads[fd]

    def get_current_thread(self):
        return self._current_thread

