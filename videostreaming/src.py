#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import traceback, threading
import Queue
from pyccn import *

gobject.threads_init()

class CCNSrc(gst.BaseSrc):
	__gtype_name__ = 'CCNSrc'
	__gstdetails__ = ("CCN source", "Source/Network",
		"Receive data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	_receiver = None

	def __init__(self, name):
		self.__gobject_init__()
		self.set_name(name)

#		gst.info("Creating CCN Src")
#		self.srcpad = gst.Pad(self._srcpadtemplate, "src")
#
#		self.srcpad.set_event_function(self.eventfunc)
#		self.srcpad.set_query_function(self.queryfunc)
#		self.srcpad.set_getcaps_function(gst.Pad.proxy_getcaps)
#		self.srcpad.set_setcaps_function(gst.Pad.proxy_setcaps)
#
#		gst.info("Adding srcpad to self")
#		self.add_pad(self.srcpad)

	def set_property(self, name, value):
		if name == 'location':
			self.uri = Name.Name(value)

	def set_receiver(self, receiver):
		self._receiver = receiver

	def do_create(self, offset, size):
		if not self._receiver:
			raise AssertionError("_receiver not set")

		print "offset: %d, size: %d" % (offset, size)
		buffer = self._receiver.queue.get()
		self._receiver.queue.task_done()
		return gst.FLOW_OK, buffer

	def queryfunc(self, pad, query):
		try:
			print(dir(query))
			self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))
			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

class Receiver(Closure.Closure):
	queue = Queue.Queue(20)

	def __init__(self, uri):
		self._handle = CCN.CCN()
		self._uri = Name.Name(uri)
		self._segment = 0

	def start(self):
		self._receiver_thread = threading.Thread(target=self.run)
		self._running = True
		self._receiver_thread.start()
		self.next_interest()

	def stop(self):
		self._running = False
		self._handle.setTimeout(0)
		self._receiver_thread.join()

	def run(self):
		print "Running ccn loop"
		self._handle.run(-1)
		print "Finished running ccn loop"

	def next_interest(self):
		name = Name.Name(self._uri)
		name.appendSegment(self._segment)
		self._segment += 1

		interest = Interest.Interest(name=name)
		print "Issuing an interest for: %s" % name
		self._handle.expressInterest(name, self, interest)

	def upcall(self, kind, info):
		if kind == Closure.UPCALL_FINAL:
			return Closure.RESULT_OK

		if kind == Closure.UPCALL_CONTENT:
			content = gst.Buffer(info.ContentObject.content)
			self.queue.put(content)
			self.next_interest()
			return Closure.RESULT_OK

		if kind == Closure.UPCALL_INTEREST_TIMED_OUT:
			print "timeout - reexpressing"
			return Closure.RESULT_REEXPRESS

		print "kind: %d" % kind

		return Closure.RESULT_ERR

#gobject.type_register(CCNSrc)
gst.element_register(CCNSrc, 'ccnsrc')

if __name__ == '__main__':
	#def on_eos(bus, msg):
	#	mainloop.quit()
	def on_dynamic_pad(dbin, pad):
		global decoder
		print "Linking dynamically!"
		pad.link(decoder.get_pad("sink"))

	def bus_call(bus, message, loop):
		t = message.type
		if t == gst.MESSAGE_EOS:
			print("End-of-stream")
			loop.quit()
		elif t == gst.MESSAGE_ERROR:
			err, debug = message.parse_error()
			print("Error: %s: %s" % (err, debug))
			loop.quit()
		return True

#	src = gst.element_factory_make('filesrc')
#	src.set_property('location', 'test.ts')

	receiver = Receiver('/videostream')
	src = CCNSrc('source')
	src.set_receiver(receiver)
	receiver.start()

	demuxer = gst.element_factory_make('mpegtsdemux')
	decoder = gst.element_factory_make('ffdec_h264')
	sink = gst.element_factory_make('xvimagesink')

	pipeline = gst.Pipeline()
	pipeline.add(src, demuxer, decoder, sink)

	src.link(demuxer)
	demuxer.connect("pad-added", on_dynamic_pad)
	decoder.link(sink)

	#gst.element_link_many(src, demuxer, decoder, sink)

	loop = gobject.MainLoop()
	bus = pipeline.get_bus()
	#bus.add_signal_watch()
	#bus.connect('message::eos', on_eos)
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
