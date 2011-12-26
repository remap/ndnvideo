#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

gobject.threads_init()

import traceback

class MySink(gst.Element):
	_sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
		gst.PAD_SINK,
		gst.PAD_ALWAYS,
		gst.caps_new_any())
	_counter = 0

	def __init__(self):
		gst.Element.__init__(self)

		gst.info('creating sinkpad')
		self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")

		gst.info('adding sinkpad to self')
		self.add_pad(self.sinkpad)

		gst.info('setting chain/event functions')
		self.sinkpad.set_chain_function(self.chainfunc)
		self.sinkpad.set_event_function(self.eventfunc)

	def notify_caps(self, pad, args):
		caps = pad.get_negotiated_caps()
		if not caps:
			pad.warning("no negotiated pads available")

		pad.info("My caps: %s" % caps)
		self.framerate = caps[0]['framerate']

	def chainfunc(self, pad, buffer):
		try:
			self._counter += 1
			self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))

#			self.info("offset %d, offset_end %d" % (buffer.offset, buffer.offset_end))
#			self.info("duration %d" % buffer.duration)
#			self.info("flags %s" % buffer.flags)
#			self.info("caps %s" % buffer.caps)

			framerate = buffer.caps[0]['framerate']

#			self.info("framerate: %f" % framerate)
			self.info("frame = %f" % (buffer.timestamp * float(framerate) / gst.SECOND))
			#print dir(buffer)

#			if self._counter > 10:
#				return gst.FLOW_ERROR

			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

gobject.type_register(MySink)

if __name__ == '__main__':
	src = gst.element_factory_make("videotestsrc")
	encoder = gst.element_factory_make("ffenc_h263")
#	sink = gst.element_factory_make("fakesink")
	sink = MySink()

	pipeline = gst.Pipeline()
	pipeline.add(src, encoder, sink)

	caps = gst.caps_from_string("video/x-raw-yuv,width=352,height=288")
	src.link_filtered(encoder, caps)
	encoder.link(sink)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Got an interrupt"
		pipeline.set_state(gst.STATE_NULL)

