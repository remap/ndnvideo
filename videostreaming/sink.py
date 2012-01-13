#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

from gst.extend.utils import gst_dump
import Queue, traceback

import pytimecode
import utils

class CCNSink(gst.Element):
	_sinkpadtemplate = gst.PadTemplate("sinkpadtemplate",
		gst.PAD_SINK,
		gst.PAD_ALWAYS,
		gst.caps_new_any())

	queue = Queue.Queue(20)
	_tc = None

	def __init__(self):
		gst.Element.__init__(self)

		gst.info("Creating CCN Sink")
		self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")

		gst.info("Adding sinkpad to self")
		self.add_pad(self.sinkpad)

		self.sinkpad.set_chain_function(self.chainfunc)
		self.sinkpad.set_event_function(self.eventfunc)

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

	def _set_tc(self, pad):
		caps = pad.get_negotiated_caps()[0]

		framerate = caps['framerate']
		self._tc = utils.TCConverter(framerate)

	def chainfunc(self, pad, buffer):
		try :
			if not self._tc:
				print "setting up tc"
				self._set_tc(pad)

			#print "offset: %d offset_end: %d" % (buffer.offset, buffer.offset_end)
			#self.queue.put((self._tc.make_timecode(), buffer))
			tc = self._tc.ts2tc(buffer.timestamp).make_timecode()
			print "Publishing %s" % tc
			self.queue.put((tc, buffer))

			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_UNEXPECTED

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

gobject.type_register(CCNSink)
