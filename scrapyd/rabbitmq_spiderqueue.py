from zope.interface import implements

from scrapyd.interfaces import ISpiderQueue
from scrapyd.config import Config
from twisted.python import log
import json
from rabbitmq_utils import RabbitmqUtils
import errno


class RabbitmqSpiderQueue(object):

    implements(ISpiderQueue)

    def __init__(self, project=None):
        c = Config()
        self.host = c.get('rabbitmq_host')
        self.port = c.get('rabbitmq_port')
        self.vhost = c.get('rabbitmq_vhost')
        self.user = c.get('rabbitmq_user')
        self.password = c.get('rabbitmq_password')
        self.exchange = c.get('rabbitmq_exchange')
        self.exchange_dlq = c.get('rabbitmq_exchange_dlq')
        self.project = project
        self.init =False
        log.msg(project)
        
        
    def getChannel(self):
        channel = RabbitmqUtils.getChannel()
        if self.init == False:
            channel.exchange_declare(exchange=self.exchange, exchange_type='direct', durable=True)
            channel.exchange_declare(exchange=self.exchange_dlq,exchange_type='direct', durable=True)
            args = dict()
            args['x-dead-letter-exchange'] = self.exchange_dlq
            channel.queue_declare(queue=self.project, durable=True, arguments=args)
            channel.queue_bind(queue=self.project, exchange=self.exchange, routing_key=self.project)
            channel.queue_declare(queue=self.project+".dlq", durable=True)
            channel.queue_bind(queue=self.project+".dlq", exchange=self.exchange_dlq, routing_key=self.project)
            self.init = True
            
        return channel
            
    def add(self, name, **spider_args):
        d = spider_args.copy()
        d['name'] = name
        priority = float(d.pop('priority', 0))
        log.msg(json.dumps(d, ensure_ascii=False))
        self.getChannel().basic_publish(self.exchange, self.project, json.dumps(d))
        #ver como priorizar uma msg no rabbitmq
        
    def pop(self):
        while True:
            try:
                method_frame, header_frame, body = self.getChannel().basic_get(self.project)
                obj = json.loads(body)
                obj['delivery_tag'] = method_frame.delivery_tag
                return obj
            except IOError, e:
                if e.errno != errno.EINTR:
                    raise
        
    def count(self):
        while True:
            try:
                queue = self.getChannel().queue_declare(queue=self.project, durable=True, passive=True)
                return int(queue.method.message_count)
            except IOError, e:
                if e.errno != errno.EINTR:
                    raise
        
    def list(self):
        count = self.count()
        if count == None:
            count = 0
        jobs = list()
        job = dict()
        job['name'] = ''
        job['_job'] = count
        if count > 0:
            jobs.append(job)
        return jobs
        #consumer_tag = self.channel._impl._generate_consumer_tag()
        #self.channel._impl._send_method(spec.Basic.GetOk(delivery_tag=consumer_tag, redelivered=True, exchange=self.exchange, routing_key=self.project, message_count=count))

    #def remove(self, func):
        #return self.q.remove(func)

    #def clear(self):
        #self.q.clear()