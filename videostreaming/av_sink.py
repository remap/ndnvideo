#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import pyccn

from audio_sink import AudioSink
from video_sink import VideoSink

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

	pipeline = gst.parse_launch("autovideosrc ! videorate ! \
		videoscale ! video/x-raw-yuv,width=320,height=240 ! \
		timeoverlay shaded-background=true ! \
		x264enc byte-stream=true bitrate=128 speed-preset=ultrafast ! \
		VideoSink location=%s \
		autoaudiosrc ! lamemp3enc bitrate=96 ! AudioSink location=%s" % (video_uri, audio_uri))

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exiting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
