#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, math, threading, os
import pyccn
from pyccn import _pyccn

import utils

class CCNVideoPacketizer:
	_chunk_size = 4096
	_segment = 0
	_running = False
	_caps = None

	_tc = None

	def __init__(self, uri):
		self._basename = pyccn.Name(uri)
		self._name_segments = self._basename.append("segments")
		self._name_frames = self._basename.append("frames")

		self._key = pyccn.CCN.getDefaultKey()
		self._signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))
		self._signed_info_frames = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))

		#self.queue = Queue.Queue(20)
		handle = pyccn.CCN()
		self.queue = utils.RepoPublisher(handle, '/home/takeda/ccnx/repo', 'video')

	def set_caps(self, caps):
		if not self._caps:
			self._caps = caps
			packet = self.prepare_stream_info_packet(caps)
			self.queue.put(packet)

			framerate = caps[0]['framerate']
			self._tc = utils.TCConverter(framerate)

	def prepare_stream_info_packet(self, caps):
		name = self._basename.append("stream_info")

		co = pyccn.ContentObject(name, self._caps, self._signed_info)
		co.sign(self._key)

		return co

	def prepare_frame_packet(self, frame, segment):
		name = self._name_frames.append(frame)

		co = pyccn.ContentObject(name, segment, self._signed_info_frames)
		co.sign(self._key)

		return co

	def prepare_packet(self, segment, left, data):
		name = self._name_segments.appendSegment(segment)

		packet = utils.buffer2packet(left, data)
		co = pyccn.ContentObject(name, packet, self._signed_info)
		co.sign(self._key)

		return co

	def process_buffer(self, buffer):
		if not buffer.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT):
			frame = self._tc.ts2tc(buffer.timestamp)
			print "frame %s" % frame
			packet = self.prepare_frame_packet(frame, self._segment)
			self.queue.put(packet)

		chunk_size = self._chunk_size - utils.packet_hdr_len
		nochunks = int(math.ceil(buffer.size / float(chunk_size)))

		data_off = 0
		while data_off < buffer.size:
			assert(nochunks > 0)

			data_size = min(chunk_size, buffer.size - data_off)
			chunk = buffer.create_sub(data_off, data_size)
			chunk.stamp(buffer)
			data_off += data_size

			nochunks -= 1
			packet = self.prepare_packet(self._segment, nochunks, chunk)
			self._segment += 1

			self.queue.put(packet)
		assert(nochunks == 0)

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
			'location of the stream in CCNx network',
			'',
			gobject.PARAM_READWRITE)
	}

	packetizer = None

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.packetizer = CCNVideoPacketizer(value)
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

if __name__ == '__main__':
	gobject.threads_init()

	def on_dynamic_pad(demux, pad):
		print "on_dynamic_pad called! %s" % (pad.get_name())
		if pad.get_name() == "video_00":
			pad.link(sink.get_pad('sink'))

	pipeline = gst.parse_launch("autovideosrc ! videorate ! videoscale ! video/x-raw-yuv,width=480,height=360 ! \
		timeoverlay shaded-background=true ! x264enc name=encoder byte-stream=true bitrate=256 speed-preset=veryfast")
	#pipeline = gst.parse_launch("filesrc location=army.mp4 typefind=true ! qtdemux name=demuxer")

	#demuxer = pipeline.get_by_name('demuxer')
	#demuxer.connect('pad-added', on_dynamic_pad)

	sink = gst.element_factory_make("VideoSink")
	sink.set_property('location', '/repo/army')
	pipeline.add(sink)

	encoder = pipeline.get_by_name('encoder')
	encoder.link(sink)

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
