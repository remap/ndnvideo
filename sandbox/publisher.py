#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys, time
import ConfigParser

from sink import CCNSink
from transmitter_repo import CCNTransmitter

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

def set_defaults(cp):
	cp.add_section('network')
	cp.set('network', 'root', '/repo/vs')

	cp.add_section('videosrc')
	cp.set('videosrc', 'element', 'videotestsrc')
	cp.set('videosrc', 'element_caps', 'video/x-raw-yuv,width=704,height=480')
	cp.set('videosrc', 'rate_caps', 'video/x-raw-yuv,framerate=30000/1001')
	cp.set('videosrc', 'timeoverlay', "yes")

	cp.add_section('encoder')
	cp.set('encoder', 'bitrate', "256")

if __name__ == '__main__':
	gobject.threads_init()

	cp = ConfigParser.SafeConfigParser()
	if cp.read(['publisher.cfg']) == []:
		set_defaults(cp)
		with open('publisher.cfg', 'w') as of:
			cp.write(of)
			of.close()

	root = cp.get('network', 'root')

	src = gst.element_factory_make(cp.get('videosrc', 'element'))
	src_caps = gst.caps_from_string(cp.get('videosrc', 'element_caps'))

	rate = gst.element_factory_make("videorate")
	rate_caps = gst.caps_from_string(cp.get('videosrc', 'rate_caps'))

	overlay = gst.element_factory_make("timeoverlay")
	overlay.set_property('shaded-background', True)
	overlay.set_property('halignment', 'right')
#	overlay.set_property('valignment', 'bottom')

	encoder = gst.element_factory_make("x264enc")
	encoder.set_property('byte-stream', True)
	encoder.set_property('bitrate', cp.getint('encoder', 'bitrate'))

	sink = CCNSink()
	transmitter = CCNTransmitter(root, sink)
	encoder.get_pad("src").connect("notify::caps", transmitter.publish_stream_info)

	pipeline = gst.Pipeline()
	pipeline.add(src, rate)
	if cp.getboolean('videosrc', 'timeoverlay'):
		pipeline.add(overlay)
	pipeline.add(encoder, sink)

	src.link_filtered(rate, src_caps)
	if cp.getboolean('videosrc', 'timeoverlay'):
		rate.link_filtered(overlay, rate_caps)
		overlay.link(encoder)
	else:
		rate.link_filtered(encoder, rate_caps)

	encoder.link(sink)

	loop = gobject.MainLoop()
	bus = pipeline.get_bus()
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PAUSED)
	transmitter.start()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pipeline.set_state(gst.STATE_NULL)
		time.sleep(2)
		transmitter.stop()

	print "exited"
	pipeline.set_state(gst.CLOCK_TIME_NONE)

