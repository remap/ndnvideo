#! /usr/bin/env python

import Queue, struct
import sys, threading
import traceback
from pyccn import *


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
		print "queue size: %d" % self._sink.queue.qsize()
		for i in xrange(3):
			if self._sink.queue.empty():
				return

			try:
				buffer = self._sink.queue.get(block=False)
			except Queue.Empty:
				return

			chunk_off = 0
			while chunk_off < buffer.size:
				chunk_size = min(self._chunk_size, buffer.size - chunk_off)
				chunk = buffer.create_sub(chunk_off, chunk_size)
				chunk_off += chunk_size

				packet = self.preparePacket(self._segment, chunk.data)
				self._segment += 1

				self._flow_controller.put(packet)

			self._sink.queue.task_done()

	def sender(self):
		while self._running:
			self._handle.run(50)
			self.send()


if __name__ == '__main__':
	import pygst
	pygst.require("0.10")
	import gst
	import gobject

	import time

	import utils
	from sink import CCNSink

	gobject.threads_init()

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

	src = gst.element_factory_make("v4l2src")
	src.set_property('do-timestamp', True)

	scale = gst.element_factory_make("videoscale")
	scale.set_property('add_borders', True)

	overlay = gst.element_factory_make("timeoverlay")
	overlay.set_property('shaded-background', True)
#	overlay.set_property('halignment', 'right')
#	overlay.set_property('valignment', 'bottom')

	encoder = gst.element_factory_make("ffenc_h263")

	sink = CCNSink()
	encoder.get_pad("sink").connect("notify::caps", sink.retrieve_framerate)
	transmitter = CCNTransmitter('/videostream', sink)

	pipeline = gst.Pipeline()
	pipeline.add(src, scale, overlay, encoder, sink)

#	gst.element_link_many(src, encoder, muxer, sink)

	src_caps = gst.caps_from_string("video/x-raw-yuv,width=704,height=480")
	src.link_filtered(scale, src_caps)

	scale_caps = gst.caps_from_string("video/x-raw-yuv,width=704,height=576")
	scale.link_filtered(overlay, scale_caps)

	overlay.link(encoder)
	encoder.link(sink)

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

