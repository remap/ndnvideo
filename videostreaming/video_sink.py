#! /usr/bin/env python
import sys
import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, math, threading, os
import pyccn
from pyccn import _pyccn

import utils
from ElementBase import CCNPacketizer

class CCNVideoPacketizer(CCNPacketizer):
	_tc = None

	def __init__(self, repolocation, uri):
		handle = pyccn.CCN()
		publisher = utils.RepoPublisher(handle, 'video', repolocation)
		super(CCNVideoPacketizer, self).__init__(publisher, uri)

	def post_set_caps(self, caps):
		framerate = caps[0]['framerate']
		self._tc = utils.TCConverter(framerate)

	def pre_process_buffer(self, buffer):
		if not buffer.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT):
			frame = self._tc.ts2tc(buffer.timestamp)
			print "frame %s" % frame
			packet = self.prepare_frame_packet(frame, self._segment)
			self.publisher.put(packet)

class VideoSink(gst.BaseSink):
	__gtype_name__ = 'VideoSink'
	__gstdetails__ = ("CCN Video Sink", "Sink/Network",
		"Publishes data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("sink",
			gst.PAD_SINK,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	__gproperties__ = {
		'location' : (gobject.TYPE_STRING,
			'CCNx location',
			'location of the video stream in CCNx network',
			'',
			gobject.PARAM_READWRITE),
		'repolocation' : (gobject.TYPE_STRING,
			'CCNx repo location',
			'location of the repo directory within the filesystem',
			'',
			gobject.PARAM_READWRITE)
	}

	pr_location = None
	pr_repolocation = None
	packetizer = None

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.pr_location = value
		elif property.name == 'repolocation':
			self.pr_repolocation = value
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_get_property(self, property):
		if property.name == 'location':
			return self.pr_location
		elif property.name == 'repolocation':
			return self.pr_repolocation
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_set_caps(self, caps):
		print "Caps: %s" % caps
		self.packetizer.set_caps(caps)
		return True

	def do_start(self):
		print "Starting!"
		if not self.pr_location:
			print "No location set"
			return False

		self.packetizer = CCNVideoPacketizer(self.get_property('repolocation'), self.pr_location)
		return True

	def do_stop(self):
		print "Stopping!"
		return True

	def do_unlock(self):
		print "Unlock!"
		return False

	def do_event(self, ev):
		print "Got event of type %s" % ev.type
		return gst.FLOW_OK

	def do_render(self, buffer):
		#print "Buffer timestamp %d %d %d %s %d %d" % (utils.signed(buffer.timestamp), utils.signed(buffer.duration), buffer.flags, buffer.caps, utils.signed(buffer.offset), utils.signed(buffer.offset_end))
		self.packetizer.process_buffer(buffer)
		return gst.FLOW_OK

	def do_preroll(self, buf):
		print "Preroll"
		return gst.FLOW_OK

	def do_unlock_stop(self):
		print "Stop Unlock!"
		return False

	def do_render_list(self, buffer_list):
		return gst.BaseSrc.do_render_list(self, buffer_list)

	def do_query(self, query):
		print "Query: %s" % query.type
		return gst.BaseSink.do_query(self, query)

gst.element_register(VideoSink, 'VideoSink')


def usage():
	print("Usage: %s <stream publish URI>" % sys.argv[0])
	sys.exit(1)

if __name__ == '__main__':
	if (len(sys.argv) != 2):
		usage()
	uri=argv[1]
	gobject.threads_init()
	
	def on_dynamic_pad(demux, pad):
		print "on_dynamic_pad called! %s" % (pad.get_name())
		if pad.get_name() == "video_00":
			pad.link(sink.get_pad('sink'))

	pipeline = gst.parse_launch("autovideosrc ! videorate ! videoscale ! video/x-raw-yuv,width=480,height=360 ! \
		timeoverlay shaded-background=true ! x264enc name=encoder byte-stream=true bitrate=256 speed-preset=veryfast ! \
		VideoSink location="+uri)
	#pipeline = gst.parse_launch("filesrc location=army.mp4 typefind=true ! qtdemux name=demuxer")

	#demuxer = pipeline.get_by_name('demuxer')
	#demuxer.connect('pad-added', on_dynamic_pad)

	#sink = gst.element_factory_make("VideoSink")
	#sink.set_property('location', '/repo/army')
	#pipeline.add(sink)

	#encoder = pipeline.get_by_name('encoder')
	#encoder.link(sink)

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
