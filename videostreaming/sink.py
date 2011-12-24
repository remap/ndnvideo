#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

from gst.extend.utils import gst_dump

import Queue, struct
import sys, threading
import traceback
from pyccn import *

import utils

gobject.threads_init()

class CCNSink(gst.Element):
	_sinkpadtemplate = gst.PadTemplate("sinkpadtemplate",
		gst.PAD_SINK,
		gst.PAD_ALWAYS,
		gst.caps_new_any())

	queue = Queue.Queue(20)

	def __init__(self):
		gst.Element.__init__(self)

		gst.info("Creating CCN Sink")
		self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")

		gst.info("Adding sinkpad to self")
		self.add_pad(self.sinkpad)

		#self.sinkpad.connect("notify::caps", self._notify_caps)
		self.sinkpad.set_chain_function(self.chainfunc)
		self.sinkpad.set_event_function(self.eventfunc)

		self.count = 0

	def retrieve_framerate(self, pad, args):
		caps = pad.get_negotiated_caps()
		if not caps:
			pad.warning("no negotiated caps available")
			return

		pad.info("My Caps: %s" % caps)
		#storing framerate (can be retrieved by float() or .num and .denom)
		self.framerate = caps[0]['framerate']

	def _notify_caps(self, pad, args):
		caps = caps.get_negotiated_caps()
		if not caps:
			pad.warning("no negotiated caps available")
			return

		pad.info("My Caps: %s" % caps)
		#storing framerate (can be retrieved by float() or .num and .denom)
		self.framerate = caps[0]['framerate']

	def chainfunc(self, pad, buffer):
		try :
			#self.info("name: %s" % pad.get_name())
			#parent = pad.get_parent_element()
			#self.info("parent %r" % parent)
			#self.info("name: %s" % parent.get_name())
			#caps = pad.get_caps()
			#size = caps.get_size()
			#self.info("size: %d" % size)
			#structure = caps.get_structure(0)
			#self.info("name: %s" % structure.get_name())
			self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))
			self.queue.put(buffer)
#			self.count += 1
#
#			if self.count > 10:
#				return gst.FLOW_UNEXPECTED

			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_UNEXPECTED

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

class CCNTransmitter():
	_chunk_size = 4000
	_segment = 0
	_running = False

	def __init__(self, uri, sink):
		self._sink = sink

		self._handle = CCN.CCN()
		self._basename = Name.Name(uri)
		self._key = self._handle.getDefaultKey()
		self._flow_controller = utils.FlowController(self._basename, self._handle)

		si = ContentObject.SignedInfo()
		si.type = ContentObject.ContentType.CCN_CONTENT_DATA
		si.publisherPublicKeyDigest = self._key.publicKeyID
		si.keyLocator = Key.KeyLocator(self._key)
		self._signed_info = si

	def start(self):
		self._sender_thread = threading.Thread(target=self.sender)
		self._running = True
		self._sender_thread.start()

	def stop(self):
		self._running = False
		self._sender_thread.join()

	def preparePacket(self, segment, data):
		name = Name.Name(self._basename)
		name.appendSegment(segment)

		print("preparing %s" % name)

		co = ContentObject.ContentObject(name, data, self._signed_info)
		co.sign(self._key)

		return co

	def send(self):
		print "size: %d" % self._sink.queue.qsize()
		for i in xrange(3):
			if self._sink.queue.empty():
				return

			try:
				buffer = self._sink.queue.get(block=False)
			except Queue.Empty:
				return

			packet = self.preparePacket(self._segment, buffer.data)
			self._segment += 1
			self._flow_controller.put(packet)
			self._sink.queue.task_done()

	def sender(self):
		while self._running:
			self._handle.run(50)
			self.send()

gobject.type_register(CCNSink)

if __name__ == '__main__':
	import time

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

	#src = gst.element_factory_make("v4l2src")

	src = gst.element_factory_make("videotestsrc")
	encoder = gst.element_factory_make("x264enc")
	encoder.set_property('bitrate', 256)
	muxer = gst.element_factory_make("mpegtsmux")

	sink = CCNSink()
	encoder.get_pad("sink").connect("notify::caps", sink.retrieve_framerate)
	transmitter = CCNTransmitter('/videostream', sink)

	pipeline = gst.Pipeline()
	pipeline.add(src, encoder, muxer, sink)

	gst.element_link_many(src, encoder, muxer, sink)
#	src.link(encoder)
#	encoder.link(muxer)
#	muxer.link(sink)

	loop = gobject.MainLoop()
	bus = pipeline.get_bus()
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PAUSED)

	transmitter.start()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pipeline.set_state(gst.STATE_NULL)
		time.sleep(2)
		transmitter.stop()

	print "exited"
	pipeline.set_state(gst.CLOCK_TIME_NONE)

