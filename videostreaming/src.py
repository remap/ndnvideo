#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import traceback

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
	_sinkpad = None
	def __init__(self, name):
		self.__gobject_init__()
		self.set_name(name)
		self.set_format(gst.FORMAT_TIME)

	def set_property(self, name, value):
		if name == 'location':
			self.uri = pyccn.Name(value)

	def set_receiver(self, receiver):
		self._receiver = receiver

	# currently not used
	def set_sink_pad(self, sinkpad):
		self._sinkpad = sinkpad
		self._sinkpad.add_event_probe(self.probe_handle_seek)

	# currently not used
	def probe_handle_seek(self, pad, event):
		if event.type != gst.EVENT_SEEK:
			return True

		seek_args = event.parse_seek()

		print "Requesting seek %s" % str(seek_args)
		return False

	def do_start(self):
		print "Called start"
		self._receiver.start()
		return True

	def do_stop(self):
		print "Called stop"
		self._receiver.stop()
		return True

	def do_get_size(self, size):
		print "Called get_size"
		return False

	def do_is_seekable(self):
		print "Called seekable"
		return True

	def do_check_get_range(self):
		print "Called check_get_range"
		return False

#	def do_event(self, event):
#		if event.type in [gst.EVENT_NAVIGATION]:
#			return gst.BaseSrc.do_event(self, event)
#
#		if event.type == gst.EVENT_QOS:
#			return gst.BaseSrc.do_event(self, event)
#			print "QOS: proportion %f, diff: %d timestamp: %d" % event.parse_qos()
#		elif event.type == gst.EVENT_LATENCY:
#			print "Latency %d" % event.parse_latency()
#		elif event.type == gst.EVENT_SEEK:
#			print "Event Seek: rate: %f format %s flags: %s start_type: %s start %d stop_type %s stop %d" % event.parse_seek()
#			return gst.BaseSrc.do_event(self, event)
#
#		print "Got event %s" % event.type
#		return gst.BaseSrc.do_event(self, event)

	def do_create(self, offset, size):
		if not self._receiver:
			raise AssertionError("_receiver not set")

		#print "Offset: %d, Size: %d" % (offset, size)
		buffer = self._receiver.queue.get()
		if buffer.flag_is_set(gst.BUFFER_FLAG_DISCONT):
			r = self.new_seamless_segment(buffer.timestamp, -1, buffer.timestamp)
			print "Seamless segment: %s" % r
		try:
			return gst.FLOW_OK, buffer
		finally:
			self._receiver.queue.task_done()

	def do_do_seek(self, segment):
		pos = self._receiver.seek(segment.time)
		return True

#	def do_prepare_seek_segment(self, seek, segment):
#		print "Called, Prepare seek segment %s %s" % (seek, segment)
#		return True
#		#print "Stream time: %d" % segment.to_stream_time(gst.
#		return gst.BaseSrc.do_prepare_seek_segment(self, seek, segment)

#	def queryfunc(self, pad, query):
#		try:
#			print(dir(query))
#			self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))
#			return gst.FLOW_OK
#		except:
#			traceback.print_exc()
#			return gst.FLOW_ERROR

gst.element_register(CCNSrc, 'ccnsrc')

