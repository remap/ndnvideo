#! /usr/bin/env python

import Queue, struct, sys, threading, math
import traceback
import pyccn

import utils

class CCNTransmitter():
	_chunk_size = 4096
	_segment = 0
	_running = False
	_caps = None

	def __init__(self, uri, sink):
		self._sink = sink

		self._handle = pyccn.CCN()
		self._basename = pyccn.Name(uri)
		self._name_segments = self._basename.append("segments")
		self._name_frames = self._basename.append("frames")
		self._key = self._handle.getDefaultKey()
		self._flow_controller = utils.FlowController(self._basename, self._handle)

		self._signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))
		self._signed_info_frames = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))

	def publish_stream_info(self, pad, args):
		if self._caps:
			return

		self._caps = pad.get_negotiated_caps()

		name = self._basename.append("stream_info")

		print "Publishing %s under %s" % (self._caps, name)
		co = pyccn.ContentObject(name, self._caps, self._signed_info)
		co.sign(self._key)

		self._flow_controller.put(co)

	def start(self):
		self._sender_thread = threading.Thread(target=self.sender)
		self._running = True
		self._sender_thread.start()

	def stop(self):
		self._running = False
		self._sender_thread.join()

	def prepareFramePacket(self, frame, segment):
		name = self._name_frames.append(frame)

		co = pyccn.ContentObject(name, segment, self._signed_info_frames)
		co.sign(self._key)

		return co

	def preparePacket(self, segment, left, data):
		name = self._name_segments.appendSegment(segment)

		print("preparing %s" % name)

		packet = utils.buffer2packet(left, data)
		co = pyccn.ContentObject(name, packet, self._signed_info)
		co.sign(self._key)

		return co

	def send(self):
		print "queue size: %d" % self._sink.queue.qsize()
		for i in xrange(3):
			if self._sink.queue.empty():
				return

			try:
				entry = self._sink.queue.get(block=False)
			except Queue.Empty:
				return

			frame, buffer = entry

			if not buffer.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT):
				packet = self.prepareFramePacket(frame, self._segment)
				self._flow_controller.put(packet)

			chunk_size = self._chunk_size - utils.packet_hdr_len
			nochunks = int(math.ceil(buffer.size / float(chunk_size)))

			data_off = 0
			while data_off < buffer.size:
				assert(nochunks > 0)
				data_size = min(chunk_size, buffer.size - data_off)
				chunk = buffer.create_sub(data_off, data_size)
				data_off += data_size

				nochunks -= 1
				packet = self.preparePacket(self._segment, nochunks, chunk)
				self._segment += 1

				self._flow_controller.put(packet)
			assert(nochunks == 0)

			self._sink.queue.task_done()

	def sender(self):
		while self._running:
			self._handle.run(50)
			self.send()


if __name__ == '__main__':
	import sys
	import pygst
	pygst.require("0.10")
	import gst
	import gobject

	import time

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

	if len(sys.argv) != 2:
		print "Usage: %s <URI>" % sys.argv[0]
		sys.exit(1)

	dest = sys.argv[1]

#	src = gst.element_factory_make("videotestsrc")
	src = gst.element_factory_make("v4l2src")
	src_caps = gst.caps_from_string("video/x-raw-yuv,width=704,height=480")

	rate = gst.element_factory_make("videorate")
	rate_caps = gst.caps_from_string("video/x-raw-yuv,framerate=30000/1001")

	overlay = gst.element_factory_make("timeoverlay")
	overlay.set_property('shaded-background', True)
	overlay.set_property('halignment', 'right')
#	overlay.set_property('valignment', 'bottom')

	encoder = gst.element_factory_make("x264enc")
	encoder.set_property('bitrate', 256)
	encoder.set_property('byte-stream', True)

	sink = CCNSink()
	transmitter = CCNTransmitter(dest, sink)
	encoder.get_pad("src").connect("notify::caps", transmitter.publish_stream_info)

	pipeline = gst.Pipeline()
	pipeline.add(src, rate, overlay, encoder, sink)

#	gst.element_link_many(src, encoder, muxer, sink)

	src.link_filtered(rate, src_caps)
	rate.link_filtered(overlay, rate_caps)
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

