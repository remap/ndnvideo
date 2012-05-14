#! /usr/bin/env python

import pygst
import ElementBase
pygst.require("0.10")
import gst
import gobject

import Queue, traceback
import pyccn

from ElementBase import CCNDepacketizer

CMD_SEEK = 1

def debug(cls, text):
	print "%s: %s" % (cls.__class__.__name__, text)

class CCNAudioDepacketizer(CCNDepacketizer):
	pass

class AudioSrc(ElementBase.CCNElementSrc):
	__gtype_name__ = 'AudioSrc'
	__gstdetails__ = ("CCN Audio Source", "Source/Network",
		"Receives audio data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = ElementBase.CCNElementSrc.__gsttemplates__

	def __init__(self):
		super(AudioSrc, self).__init__(CCNAudioDepacketizer, 3)

gst.element_register(AudioSrc, 'AudioSrc')

if __name__ == '__main__':
	import sys

	gobject.threads_init()

	if len(sys.argv) != 2:
		print "Usage: %s <uri>" % sys.argv[0]
		sys.exit(1)

	uri = sys.argv[1]

	pipeline = gst.parse_launch('AudioSrc location=%s ! decodebin ! autoaudiosink' % uri)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
