#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, math, threading, os
import pyccn
from pyccn import _pyccn

import utils

class CCNAudioPacketizer:
	_chunk_size = 4096
	_segment = 0
	_running = False
	_caps = None

	def __init__(self, uri):
		self._basename = pyccn.Name(uri)
		self._name_segments = self._basename + "segments"
		self._name_index = self._basename + "index"

		self._key = pyccn.CCN.getDefaultKey()
		self._signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))
		self._signed_info_index = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))

		#self.queue = Queue.Queue(20)
		handle = pyccn.CCN()
		self.queue = utils.RepoPublisher(handle, '/home/takeda/ccnx/repo', 'audio')

	def set_caps(self, caps):
		if not self._caps:
			self._caps = caps
			packet = self.prepare_stream_info_packet(caps)
			self.queue.put(packet)

	def prepare_stream_info_packet(self, caps):
		name = self._basename.append("stream_info")

		co = pyccn.ContentObject(name, self._caps, self._signed_info)
		co.sign(self._key)

		return co

	def prepare_index_packet(self, index, segment):
		name = self._name_index.appendSegment(index)

		co = pyccn.ContentObject(name, segment, self._signed_info_index)
		co.sign(self._key)

		return co

	def prepare_packet(self, segment, left, data):
		name = self._name_segments.appendSegment(segment)

		packet = utils.buffer2packet(left, data)
		co = pyccn.ContentObject(name, packet, self._signed_info)
		co.sign(self._key)

		return co

	def process_buffer(self, buffer):
#		if not buffer.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT):

		print "index %s" % buffer.timestamp
		packet = self.prepare_index_packet(buffer.timestamp, self._segment)
		self.queue.put(packet)

		chunk_size = self._chunk_size - utils.packet_hdr_len
		nochunks = int(math.ceil(buffer.size / float(chunk_size)))

		data_off = 0
		while data_off < buffer.size:
			assert(nochunks > 0)

			data_size = min(chunk_size, buffer.size - data_off)
			chunk = buffer.create_sub(data_off, data_size)
			data_off += data_size

			nochunks -= 1
			packet = self.prepare_packet(self._segment, nochunks, chunk)
			self._segment += 1

			self.queue.put(packet)
		assert(nochunks == 0)

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
			gobject.PARAM_READWRITE)
	}

	packetizer = None

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.packetizer = CCNAudioPacketizer(value)
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_set_caps(self, caps):
		print "Caps: %s" % caps
		self.packetizer.set_caps(caps)
		return True

	def do_start(self):
		print "Starting!"
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
		print "Buffer timestamp %d %d %d %s" % (buffer.timestamp, buffer.duration, buffer.flags, buffer.caps)
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

