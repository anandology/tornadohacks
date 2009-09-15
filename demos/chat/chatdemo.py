"""Tornado chat demo adopted for web.py + tornado.

Authentication has been removed for simplicity.

Start the server and go to http://0.0.0.0:8080/joe to become user joe.
"""
import web
import uuid
import simplejson
import logging

from tornadohacks.webpy import asynchronous, async_callback, tornadorun

urls = (
    '/(\w+)', 'index',
    '/(\w+)/new', 'new',
    '/(\w+)/updates', 'update'
)
app = web.application(urls, globals())

_globals = {}
render = web.template.render('templates', globals=_globals)
_globals['render'] = render

class MessageMixin(object):
    waiters = []
    cache = []
    cache_size = 200

    def wait_for_messages(self, callback, cursor=None):
        cls = MessageMixin
        if cursor:
            index = 0
            for i in xrange(len(cls.cache)):
                index = len(cls.cache) - i - 1
                if cls.cache[index]["id"] == cursor: break
            recent = cls.cache[index + 1:]
            if recent:
                callback(recent)
                return
        cls.waiters.append(callback)

    def new_messages(self, messages):
        cls = MessageMixin
        logging.info("Sending new message to %r listeners", len(cls.waiters))
        for callback in cls.waiters:
            try:
                callback(messages)
            except:
                logging.error("Error in waiter callback", exc_info=True)
        cls.waiters = []
        cls.cache.extend(messages)
        if len(cls.cache) > self.cache_size:
            cls.cache = cls.cache[-self.cache_size:]
            
class index:
    def GET(self, username):
        return render.index(username, MessageMixin.cache)
        
class new(MessageMixin):
    def POST(self, username):
        i = web.input(body="", next=None)
        message = {
            "id": str(uuid.uuid4()),
            "from": username,
            "body": i.body,
        }
        message["html"] = web.safestr(render.message(message))

        self.new_messages([message])
        if i.next:
            web.ctx.status = "303 See Other"
            web.header("Location", i.next)
        else:
            return simplejson.dumps(message)
            
class update(MessageMixin):
    @asynchronous
    def POST(self, username):
        i = web.input(cursor=None)
        self.wait_for_messages(async_callback(self.on_new_messages), cursor=i.cursor)

    def on_new_messages(self, messages):
        web.ctx.response.write(simplejson.dumps(dict(messages=messages)))
        web.ctx.response.finish()
  
if __name__ == '__main__':
    tornadorun(app, 8080)
