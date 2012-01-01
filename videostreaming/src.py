#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue
import traceback

from receiver import CCNReceiver

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

	__gproperties__ = {
		'location' : (gobject.TYPE_STRING,
			'CCNx location',
			'location of the stream in CCNx network',
			'',
			gobject.PARAM_READWRITE)
	}

	_receiver = None
	_sinkpad = None
	_caps = None
	def __init__(self, location=None):
		self.__gobject_init__()
		self.set_format(gst.FORMAT_TIME)
		if location:
			receiver = CCNReceiver(location)
			self.set_receiver(receiver)
		self.seek_in_progress = None

	def do_set_property(self, property, value):
		if property.name == 'location':
			receiver = CCNReceiver(value)
			self.set_receiver(receiver)
		else:
			raise AttributeError, 'unknown property %s' % property.name

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

	def do_get_caps(self):
		print "Called do_get_caps"
		if not self._caps:
			if self._receiver:
				self._caps = self._receiver.fetch_stream_info()
			else:
				return None

		return self._caps

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
		raise Exception("aaaa!")
		return False

	def do_is_seekable(self):
		return True

	def do_check_get_range(self):
		return False

	def do_create(self, offset, size):
		try:
			if not self._receiver:
				raise AssertionError("_receiver not set")

			#print "Offset: %d, Size: %d" % (offset, size)
			try:
				buffer = self._receiver.queue.get(True, 0.5)
			except Queue.Empty:
				return gst.FLOW_OK, gst.Buffer()

			try:
				if self.seek_in_progress and not buffer.flag_is_set(gst.BUFFER_FLAG_DISCONT):
					return gst.FLOW_OK, gst.Buffer()

				if buffer.flag_is_set(gst.BUFFER_FLAG_DISCONT):
					event = gst.event_new_new_segment(False, 1.0, gst.FORMAT_TIME, self.seek_in_progress, -1, self.seek_in_progress)
					self.seek_in_progress = None
					r = self.get_static_pad("src").push_event(event)
					#r = self.new_seamless_segment(buffer.timestamp, -1, buffer.timestamp)
					print "New segment: %s" % r

				return gst.FLOW_OK, buffer
			finally:
				self._receiver.queue.task_done()
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR, None

	def do_do_seek(self, segment):
		print "Asked to seek to %d" % segment.start
		self.seek_in_progress = segment.start
		pos = self._receiver.seek(segment.start)
		return True

	def do_query(self, query):
		if query.type != gst.QUERY_DURATION:
			return gst.BaseSrc.do_query(self, query)

		duration = 60 * gst.SECOND
		query.set_duration(gst.FORMAT_TIME, duration)

		print "Returning %s %d" % (query.parse_duration())

		return True

gobject.type_register(CCNSrc)
gst.element_register(CCNSrc, 'CCNSrc')

if __name__ == '__main__':
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

	def do_seek(pipeline, val):
		res = pipeline.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, long(val * gst.SECOND))
		print "Seek result: %s" % res

	pipeline = gst.parse_launch("CCNSrc location=/videostream ! ffdec_h264 max-threads=3 ! xvimagesink")

	loop = gobject.MainLoop()
	bus = pipeline.get_bus()
	#bus.add_signal_watch()
	#bus.connect('message::eos', on_eos)
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	do_seek(pipeline, 90)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
