#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

from audio_sink import AudioSink
from video_sink import VideoSink

if __name__ == '__main__':
	gobject.threads_init()

	pipeline = gst.parse_launch("autovideosrc ! videorate ! timeoverlay shaded-background=true ! x264enc byte-stream=true bitrate=256 speed-preset=veryfast ! VideoSink autoaudiosrc ! ffenc_aac ! AudioSink")

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
