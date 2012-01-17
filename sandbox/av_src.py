#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

from audio_src import AudioSrc
from video_src import VideoSrc

if __name__ == '__main__':
	gobject.threads_init()

	pipeline = gst.parse_launch("VideoSrc ! ffdec_h264 ! autovideosink AudioSrc ! ffdec_aac ! autoaudiosink")

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
