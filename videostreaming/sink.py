#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

from gst.extend.utils import gst_dump
import Queue, traceback
import pytimecode

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

		#self.sinkpad.connect("notify::caps", self._notify_caps)
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

		if framerate.num == 30 and framerate.denom == 1:
			fr = "30"
		elif framerate.num == 30000 and framerate.denom == 1001:
			fr = "29.97"
		elif framerate.num == 25 and framerate.denom == 1:
			fr = "25"
		else:
			raise Exception("Unsupported framerate: %s" % framerate)

		self._tc = pytimecode.PyTimeCode(fr, frames=0)

	def chainfunc(self, pad, buffer):
		try :
			if not self._tc:
				print "setting tc"
				self._set_tc(pad)

			#self.info("name: %s" % pad.get_name())
			#parent = pad.get_parent_element()
			#self.info("parent %r" % parent)
			#self.info("name: %s" % parent.get_name())
			#caps = pad.get_caps()
			#size = caps.get_size()
			#self.info("size: %d" % size)
			#structure = caps.get_structure(0)
			#self.info("name: %s" % structure.get_name())

			print "offset: %d offset_end: %d" % (buffer.offset, buffer.offset_end)
			self.queue.put((self._tc.make_timecode(), buffer))

			self._tc.next()

			return gst.FLOW_OK
		except:
			traceback.print_exc()
			return gst.FLOW_UNEXPECTED

	def eventfunc(self, pad, event):
		self.info("%s event:%r" % (pad, event.type))
		return True

gobject.type_register(CCNSink)
