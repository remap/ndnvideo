#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, math, threading, os
import pyccn
from pyccn import _pyccn

import utils
from ElementBase import CCNPacketizer

class CCNAudioPacketizer(CCNPacketizer):
	index_frequency = 2000
	last_index = None

	def __init__(self, repolocation, uri):
		handle = pyccn.CCN()
		publisher = utils.RepoPublisher(handle, 'audio', repolocation)
		super(CCNAudioPacketizer, self).__init__(publisher, uri)

	def pre_process_buffer(self, buffer):
		timestamp = buffer.timestamp
		if self.last_index is not None and \
				(timestamp - self.last_index) < self.index_frequency * 1000000:
			return

		print "index %f" % (timestamp / 1000000000.)
		packet = self.prepare_frame_packet(pyccn.Name.num2seg(timestamp), self._segment)
		self.publisher.put(packet)
		self.last_index = timestamp

class AudioSink(gst.BaseSink):
	__gtype_name__ = 'AudioSink'
	__gstdetails__ = ("CCN Audio Sink", "Sink/Network",
		"Publishes audio data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("sink",
			gst.PAD_SINK,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	__gproperties__ = {
		'location' : (gobject.TYPE_STRING,
			'CCNx location',
			'location of the audio stream in CCNx network',
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

		self.packetizer = CCNAudioPacketizer(self.get_property('repolocation'), self.pr_location)
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
		#print "Buffer timestamp %d %d %d %s %d" % (buffer.timestamp, buffer.duration, buffer.flags, buffer.caps, len(buffer.data))
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

gst.element_register(AudioSink, 'AudioSink')

if __name__ == '__main__':
	gobject.threads_init()

	def on_dynamic_pad(demux, pad):
		print "on_dynamic_pad called! %s" % (pad.get_name())
		if pad.get_name() == "audio_00":
			pad.link(sink.get_pad('sink'))

	#pipeline = gst.parse_launch("autovideosrc ! videorate ! videoscale ! video/x-raw-yuv,width=480,height=360 ! timeoverlay shaded-background=true ! x264enc name=encoder byte-stream=true bitrate=256 speed-preset=veryfast")
	#pipeline = gst.parse_launch("filesrc location=army.mp4 typefind=true ! qtdemux name=demuxer")
	pipeline = gst.parse_launch("pulsesrc ! ffenc_aac name=encoder")
	encoder = pipeline.get_by_name('encoder')

	#demuxer = pipeline.get_by_name('demuxer')
	#demuxer.connect('pad-added', on_dynamic_pad)

	sink = gst.element_factory_make("AudioSink")
	pipeline.add(sink)
	sink.set_property('location', '/repo/audio1')
	encoder.link(sink)

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	while True:
		try:
			loop.run()
		except KeyboardInterrupt:
			print "Ctrl+C pressed, exitting"
			eos = gst.event_new_eos()
			pipeline.send_event(eos)
			continue

		break

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)

