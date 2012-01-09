#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import traceback, threading
import Queue
from pyccn import *

gobject.threads_init()

if __name__ == '__main__':
	#def on_eos(bus, msg):
	#	mainloop.quit()
	def on_dynamic_pad(dbin, pad):
		global decoder

		print "Linking dynamically!"
		pad.link(decoder.get_pad("sink"))

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

	src = gst.element_factory_make('filesrc')
	src.set_property('location', 'test.ts')
	demuxer = gst.element_factory_make('mpegtsdemux')
	decoder = gst.element_factory_make('ffdec_h264')
	sink = gst.element_factory_make('xvimagesink')

	pipeline = gst.Pipeline()
	pipeline.add(src, demuxer, decoder, sink)

	src.link(demuxer)
	demuxer.connect("pad-added", on_dynamic_pad)
	decoder.link(sink)

	#gst.element_link_many(src, demuxer, decoder, sink)

	loop = gobject.MainLoop()

	bus = pipeline.get_bus()
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
