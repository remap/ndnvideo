#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import struct

hdr_fmt = "!LQQi"
hdr_len = struct.calcsize(hdr_fmt)

class VideoSrc(gst.BaseSrc):
	__gtype_name__ = 'VideoSrc'
	__gstdetails__ = ("Video Source", "Source/Network",
		"Receive data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	caps = None
	of = None

	def do_get_caps(self):
		print "Get caps"
		if not self.caps:
			if self.of:
				caps_str = self.of.readline()
				self.caps = gst.caps_from_string(caps_str.rstrip('\n'))
			else:
				return None
		return self.caps

	def do_set_caps(self, caps):
		print "Caps: %s" % caps
		return True

	def do_start(self):
		print "Starting!"
		self.of = open("video.bin", "rb")
		return True

	def do_stop(self):
		print "Stopping!"
		self.of.close()
		return True

	def do_is_seekable(self):
		print "Is seekable?"
		return False

	def do_event(self, ev):
		print "Got event of type %s" % ev.type
		return gst.FLOW_OK

	def do_create(self, offset, size):
		hdr = self.of.read(hdr_len)
		size, timestamp, duration, flags = struct.unpack(hdr_fmt, hdr)

		buffer = gst.Buffer(self.of.read(size))
		buffer.timestamp = timestamp
		buffer.duration = duration
		#buffer.flags = flags

		print "buffer timestamp %d %d %d" % (buffer.timestamp, buffer.duration, buffer.flags)
		return gst.FLOW_OK, buffer

	def do_check_get_range(self):
		return False

gst.element_register(VideoSrc, 'VideoSrc')

if __name__ == '__main__':
	gobject.threads_init()

	pipeline = gst.parse_launch("VideoSrc ! ffdec_h264 max-threads=3 skip-frame=1 ! autovideosink")

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
