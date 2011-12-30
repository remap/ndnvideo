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

	def __init__(self, name):
		self.__gobject_init__()
		self.set_name(name)
		#self.set_format(gst.FORMAT_TIME)

	def set_property(self, name, value):
		if name == 'location':
			self.uri = pyccn.Name(value)

	def set_receiver(self, receiver):
		self._receiver = receiver

	def do_start(self):
		print "Called start"
		return True

	def do_stop(self):
		print "Called stop"
		self._receiver.stop()
		return True

	def do_is_seekable(self):
		print "Called seekable"
		return True

	def do_check_get_range(self):
		print "Called do_check"
		return True


	def do_event(self, event):
		if event.type == gst.EVENT_QOS:
			return False
			print "QOS: proportion %f, diff: %d timestamp: %d" % event.parse_qos()
		print "Got event %s" % event
		return True

	def do_create(self, offset, size):
		if not self._receiver:
			raise AssertionError("_receiver not set")

		print "offset: %d, size: %d" % (offset, size)
		buffer = self._receiver.queue.get()
		try:
			return gst.FLOW_OK, buffer
		finally:
			self._receiver.queue.task_done()

	def do_do_seek(self, segment):
		print "Seeking: %s" % segment
		if segment.start == 0:
			return True
		print "abs_rate: %s" % segment.abs_rate
		print "accum: %s" % segment.accum
		print "duration: %s" % segment.duration
		print "flags: %s" % segment.flags
		print "format: %s" % segment.format
		print "last_stop: %s" % segment.last_stop
		print "rate: %s" % segment.rate
		print "start: %s" % segment.start
		print "stop: %s" % segment.stop
		print "time: %s" % segment.time
		return False

	def do_prepare_seek_segment(self, seek, segment):
		print "Called, Prepare seek segment"
		return True

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


#gobject.type_register(CCNSrc)
gst.element_register(CCNSrc, 'ccnsrc')

