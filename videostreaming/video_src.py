#! /usr/bin/env python

import pygst
import ElementBase
pygst.require("0.10")
import gst
import gobject

import base64

import utils
from ElementBase import CCNDepacketizer

def debug(cls, text):
	print "%s: %s" % (cls.__class__.__name__, text)

class CCNVideoDepacketizer(CCNDepacketizer):
	pass
#	def __init__(self, uri, window = None, timeout = None):
#		CCNDepacketizer.__init__(self, uri, window, timeout)
#		self._tc = None
#
#	def post_fetch_stream_info(self, caps):
#		framerate = caps[0]['framerate']
#		self._tc = utils.TCConverter(framerate)
#
#	def ts2index(self, ts):
#		return self._tc.ts2tc(ts)
#
#	def ts2index_add_1(self, ts):
#		tc = self._tc.ts2tc_obj(ts)
#		tc.next()
#		return tc.make_timecode()
#
#	def index2ts(self, index):
#		return self._tc.tc2ts(index)

class VideoSrc(ElementBase.CCNElementSrc):
	__gtype_name__ = 'VideoSrc'
	__gstdetails__ = ("CCN Video Source", "Source/Network",
		"Receives video data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	__gproperties__ = {
		'location' : (gobject.TYPE_STRING,
			'CCNx location',
			'location of the stream in CCNx network',
			'',
			gobject.PARAM_READWRITE),
		'publisher' : (gobject.TYPE_STRING,
			'Publisher ID',
			'base64 encoding of publisher\'s public key',
			'',
			gobject.PARAM_READWRITE),
		'interest-retry' : (gobject.TYPE_UINT,
			'Number of Interest retries',
			'How many times reexpress interest before giving up',
			0, 255, 1,
			gobject.PARAM_READWRITE),
		'pipeline-size' : (gobject.TYPE_UINT,
			'Size of the pipeline',
			'Maximum number of pending interests',
			1, 256, 18,
			gobject.PARAM_READWRITE)
	}

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.depacketizer = CCNVideoDepacketizer(value, 18)
		elif property.name == 'publisher':
			self.depacketizer.publisher_id = base64.b64decode(value)
		elif property.name == 'interest-retry':
			self.depacketizer.interest_retries = value
		elif property.name == 'pipeline-size':
			self.depacketizer.window = value
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_set_state(self, state):
		print "CHANGING STATE %s" % state

gst.element_register(VideoSrc, 'VideoSrc')

if __name__ == '__main__':
	import sys

	gobject.threads_init()

	if len(sys.argv) != 2:
		print "Usage: %s <uri>" % sys.argv[0]
		exit(1)

	uri = sys.argv[1]

	pipeline = gst.parse_launch('VideoSrc location=%s ! decodebin ! ximagesink' % uri)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exiting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
