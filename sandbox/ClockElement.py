#! /usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import pygst
pygst.require("0.10")
import gst
import gobject

import threading
from pprint import pprint

def hello(self):
	clock = self.get_clock()

	base_time = self.get_base_time()
	start_time = self.get_start_time()
	absolute_time = clock.get_time()

	position, format = self.query_position(gst.FORMAT_TIME)

	print("Base Time: %fs" % (base_time / gst.SECOND))
	print("Start time:", start_time)
	print("Running time: %fs" % ((absolute_time - base_time) / gst.SECOND))
	print("Position: %fs" % (position / gst.SECOND))

class ClockElement(gst.BaseTransform):
	__gtype_name__ = 'ClockElement'
	__gstdetails__ = ("CCN Audio Source", "Source/Network",
		"Receives audio data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")
	__gsttemplates__ = (
		gst.PadTemplate("src", gst.PAD_SRC, gst.PAD_ALWAYS, gst.caps_new_any()),
		gst.PadTemplate("sink", gst.PAD_SINK, gst.PAD_ALWAYS, gst.caps_new_any())
	)
	passthrough_on_same_caps = True

	def do_start(self):
		print("Start!")

		# Run hello() after 2 seconds
		threading.Timer(2.0, lambda: hello(self)).start()

		return True

	def do_stop(self):
		print("Stop!")
		return True

gst.element_register(ClockElement, 'ClockElement')


if __name__ == '__main__':
	gobject.threads_init()

        pipeline = gst.parse_launch('videotestsrc ! timeoverlay ! ClockElement ! autovideosink')

        loop = gobject.MainLoop()

        pipeline.set_state(gst.STATE_PLAYING)
        print("Entering loop")

        try:
                loop.run()
        except KeyboardInterrupt:
                print("Ctrl+C pressed, exitting")
                pass

        pipeline.set_state(gst.STATE_NULL)
        pipeline.get_state(gst.CLOCK_TIME_NONE)

