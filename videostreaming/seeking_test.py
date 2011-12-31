#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject


import traceback
import pytimecode
import threading

class MySrc(gst.BaseSrc):
	__gtype_name__ = 'mysrc'
	__gstdetails__ = ("CCN source", "Source/Network",
		"Receive data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")
	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	def __init__(self):
		self.__gobject_init__()
#		self.set_live(True)
		self.set_format(gst.FORMAT_TIME)
#		self.set_name(name)

	def do_start(self):
		print "Called do_start"
		self.file = open("../pyaccess/army.mp4", "r")
		return True

	def do_stop(self):
		print "Called do_stop"
		self.file.close()
		return True

	def do_is_seekable(self):
		print "Called do_is_seekable"
		return True

	def do_event(self, event):
		print "Called event: %s" % event.type
		if event.type == gst.EVENT_SEEK:
			print "rate %f format %s flags %s start_type %s start %d stop_type %s stop %f" % event.parse_seek()
#			return True
		return gst.BaseSrc.do_event(self, event)

	_tries = 0
	def do_create(self, offset, size):
		try:
			print "offset %d size %d" % (offset, size)
#			if offset > 250000000:
#				if self._tries == 0:
#					print "Simulate not having"
#					return gst.FLOW_NOT_SUPPORTED
#				else:
#					self._tries -= 1

#			self.file.seek(offset)
			data = self.file.read(size)
			buf = gst.Buffer(data)

			return gst.FLOW_OK, buf
		except:
			traceback.format_exc()

	def do_do_seek(self, segment):
		print "Called do_do_seek"
		print "format: %s start: %d stop: %d time: %d" % (segment.format, segment.start, segment.stop, segment.time)
		self.file.seek(segment.start)
		return True
#		return gst.BaseSrc.do_do_seek(self, segment)

	def do_query(self, query):
		print "Called do_query: %s" % query.type
		if query.type == gst.QUERY_CONVERT:
			r = query.parse_convert()
			print "src_format %s src_value %d dest_format: %s dest_value %d" % r
			query.set_convert(r[0], r[1], r[2], 9000)
			return True

		return gst.BaseSrc.do_query(self, query)

	def do_check_get_range(self):
		print "Called do_check_get_range"
		return False

	def do_prepare_check_segment(self, seek, segment):
		print "Called do_prepare_check_segment"
		return gst.BaseSrc.do_prepare_check_segment(self, seek, segment)

gst.element_register(MySrc, 'mysrc')

if __name__ == '__main__':
	def seek_stuff():
		print "Issuing seek"
		ret = pipeline.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, 20 * 60 * gst.SECOND)
		print "Seek result: %s" % ret

	def event(pad, event):
		if event.type == gst.EVENT_SEEK:
			print "Called probe event: %s" % event.type
			print "rate %f format %s flags %s start_type %s start %d stop_type %s stop %f" % event.parse_seek()
			return False
		return True

	gobject.threads_init()

	pipeline = gst.parse_launch("mysrc ! video/quicktime, variant=iso ! qtdemux ! ffdec_h264 ! timeoverlay shaded-background=true ! xvimagesink")

	sink = pipeline.get_by_name('xvimagesink0')
	print sink
	sink.get_pad("sink").add_event_probe(event)


#	src = gst.element_factory_make("videotestsrc")
#	#src = gst.element_factory_make("mysrc")
#
#	timeoverlay = gst.element_factory_make("timeoverlay")
#	timeoverlay.set_property('shaded-background', True)
#
#	sink = gst.element_factory_make("xvimagesink")
#
#	pipeline = gst.Pipeline()
#	pipeline.add(src, timeoverlay, sink)
#
#	gst.element_link_many(src, timeoverlay, sink)

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	timer = threading.Timer(5, seek_stuff)
	timer.start()

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Got an interrupt"
		pipeline.set_state(gst.STATE_NULL)

