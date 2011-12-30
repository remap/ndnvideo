#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

gobject.threads_init()

import traceback
import pytimecode

class MySink(gst.Element):
	_sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
		gst.PAD_SINK,
		gst.PAD_ALWAYS,
		gst.caps_new_any())
	_counter = 0
	_tc = pytimecode.PyTimeCode('29.97', frames=0, drop_frame=False)

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
#			self.info("%s timestamp(buffer):%d" % (pad, buffer.timestamp))

#			self.info("offset %d, offset_end %d" % (buffer.offset, buffer.offset_end))
#			self.info("duration %d" % buffer.duration)
			self.info("flags %s KeyFrame: %s" % (buffer.flags, not buffer.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT)))
#			self.info("caps %s" % buffer.caps)

			if buffer.flags != 256 and buffer.flags != 0:
				return gst.FLOW_ERROR

			framerate = buffer.caps[0]['framerate']

			self.info("timestamp: %d" % buffer.timestamp)
#			self.info("offset %d, offset_end %d" % (buffer.offset, buffer.offset_end))
			self.info("framerate: %s %f" % (framerate, framerate))
			frame_frac = (buffer.timestamp * float(framerate) /  gst.SECOND)
			frame = round(frame_frac)
			self.info("frame = %f %d" % (frame_frac, frame))
			self.info("counter = %d" % self._counter)
			self.info("timecode = %s" % self._tc)
			assert self._counter == frame
			#print dir(buffer)

#			if self._counter > 10:
#				return gst.FLOW_ERROR

			self._tc.next()
			self._counter += 1

			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

gobject.type_register(MySink)

if __name__ == '__main__':
	src = gst.element_factory_make("v4l2src")
	src.set_property('do-timestamp', True)

	scale = gst.element_factory_make("videoscale")
	scale.set_property('add_borders', True)

	encoder = gst.element_factory_make("ffenc_h263")

#	sink = gst.element_factory_make("fakesink")
	sink = MySink()

	pipeline = gst.Pipeline()
	pipeline.add(src, scale, encoder, sink)

	src_caps = gst.caps_from_string("video/x-raw-yuv,width=704,height=480")
	src.link_filtered(scale, src_caps)

	scale_caps = gst.caps_from_string("video/x-raw-yuv,width=704,height=576")
	scale.link_filtered(encoder, scale_caps)

	encoder.link(sink)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Got an interrupt"
		pipeline.set_state(gst.STATE_NULL)

