#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import pyccn

from audio_sink import AudioSink
from video_sink import VideoSink

if __name__ == '__main__':
	gobject.threads_init()

	pipeline = gst.parse_launch("autovideosrc ! videorate ! videoscale ! video/x-raw-yuv,width=240,height=180 ! \
		timeoverlay shaded-background=true ! x264enc byte-stream=true speed-preset=ultrafast ! \
		VideoSink name=video \
		autoaudiosrc ! ffenc_aac ! AudioSink name=audio")

	video = pipeline.get_by_name("video")
	audio = pipeline.get_by_name("audio")

	video.set_property('location', '/repo/video')
	audio.set_property('location', '/repo/audio')

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
