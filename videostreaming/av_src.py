#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import pyccn

from audio_src import AudioSrc
from video_src import VideoSrc

if __name__ == '__main__':
	import sys

	gobject.threads_init()

	def usage():
		print "Usage: %s <uri>" % sys.argv[0]
		sys.exit(1)

	if len(sys.argv) != 2:
		usage()

	uri = sys.argv[1]
	audio_uri = "%s/audio" % uri
	video_uri = "%s/video" % uri

	pipeline = gst.parse_launch("VideoSrc location=%s ! \
		ffdec_h264 max-threads=3 skip-frame=5 ! autovideosink \
		AudioSrc location=%s ! ffdec_mp3 ! autoaudiosink" % (video_uri, audio_uri))

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
