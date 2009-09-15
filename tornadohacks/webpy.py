"""Hack to run web.py applications using Tornado.
"""

import cStringIO
import sys
import web

from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler, StaticFileHandler
import tornado.web
import tornado.httpserver


class WebpyHandler(RequestHandler):
    """Tornado request handler for web.py"""

    def __init__(self, application, request, webpy_app):
        RequestHandler.__init__(self, application, request)
        self.webpy_app = webpy_app

    def delegate(self):
        # initialize socket-local
        IOLoop.instance().get_current_thread().local = {}

        self.webpy_app.load(self._environ(self.request))
        web.ctx.response = self
    
        try:
            result = self.webpy_app.handle_with_processors()
        except web.HTTPError, e:
            result = e.data

        if result is None:
            return

        def is_generator(x): return x and hasattr(x, 'next')

        if not is_generator(result):
            result = [web.safestr(result)]
        for x in result:
            self.write(web.safestr(x))

    get = post = put = delete = delegate

    def _environ(self, request):
        hostport = request.host.split(":")
        if len(hostport) == 2:
            host = hostport[0]
            port = int(hostport[1])
        else:
            host = request.host
            port = 443 if request.protocol == "https" else 80
        environ = {
            "REQUEST_METHOD": request.method,
            "SCRIPT_NAME": "",
            "PATH_INFO": request.path,
            "QUERY_STRING": request.query,
            "SERVER_NAME": host,
            "SERVER_PORT": port,
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": request.protocol,
            "wsgi.input": cStringIO.StringIO(request.body),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": False,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
        }
        if "Content-Type" in request.headers:
            environ["CONTENT_TYPE"] = request.headers["Content-Type"]
        if "Content-Length" in request.headers:
            environ["CONTENT_LENGTH"] = request.headers["Content-Length"]
        for key, value in request.headers.iteritems():
            environ["HTTP_" + key.replace("-", "_").upper()] = value
        return environ


def asynchronous(method):
    """Wrap webpy handler methods with this if they are asynchronous.

    If this decorator is given, the response is not finished when the
    method returns. It is up to the request handler to call
    web.ctx.response.finish() to finish the HTTP request. Without this
    decorator, the request is automatically finished when the GET() or
    POST() method returns.

       class download:
           @asynchronous
           def get(self):
              http = httpclient.AsyncHTTPClient()
              http.fetch("http://friendfeed.com/", self._on_download)

           def _on_download(self, response):
              web.ctx.response.write("Downloaded!")
              web.ctx.response.finish()
    """
    def wrapper(*a, **kw):
        web.ctx.response._auto_finish = False
        return method(*a, **kw)

    return wrapper

def async_callback(callback):
    """All callback functions used must be decorated with this function.

    This makes sure that the correct socket-local is available to the callback. 
    This should really be taken care by ioloop module.
    """
    thread = IOLoop.instance()._current_thread
    callback = web.ctx.response.async_callback(callback)

    def wrapper(*a, **kw):
        t = IOLoop.instance()._current_thread
        try:
            IOLoop.instance()._current_thread = thread
            return callback(*a, **kw)
        finally:
            IOLoop.instance()._current_thread = t

    return wrapper

def patch_webpy():
    """patch web.py to work with tornado."""
    # monkey-patch web.ThreadedDict
    def getd(self):
        local = IOLoop.instance().get_current_thread().get_local()
        if self not in local:
            local[self] = web.storage()
        return local[self]
        
    web.threadeddict._getd = getd

def tornadorun(webpy_app, port=8080):
    """Run web.py application using tornado."""
    from tornado.options import enable_pretty_logging
    import logging

    patch_webpy()

    # enable pretty logging
    logging.getLogger().setLevel(logging.INFO)
    enable_pretty_logging()

    application = Application([
        (r"/static/(.*)", StaticFileHandler, {'path': 'static'}),
        (r"/.*", WebpyHandler, {'webpy_app': webpy_app}),
    ])
    server = tornado.httpserver.HTTPServer(application)
    server.listen(int(port))
    print "http://0.0.0.0:%d" % port
    IOLoop.instance().start()

import patch
patch.patch_tornado()
