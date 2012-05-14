import pygtk
pygtk.require('2.0')
import pygst
pygst.require('0.10')

import gobject
import gtk
import gst

import pyccn

def get_latest_version(name):
	n = pyccn.Name(name)
	i = pyccn.Interest(childSelector = 1, answerOriginKind = pyccn.AOK_NONE)

	handle = pyccn.CCN()
	co = handle.get(n, i)
	if co is None:
		return None

	return co.name[:len(n) + 1]

class GstPlayer(gobject.GObject):
	__gsignals__ = {
		'status-updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
			(str,))
	}

	__pipeline = None

	def __init__(self, videowidget, cmd_args):
		gobject.GObject.__init__(self)
		self.playing = False

		self.player = gst.parse_launch(self.__pipeline)
		self.cmd_args = cmd_args
		self.init_elements()

		self.videowidget = videowidget
		self.on_eos = False

		bus = self.player.get_bus()
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		bus.connect('sync-message::element', self.on_sync_message)
		bus.connect('message', self.on_message)

		self.started_buffering = False
		self.stats_buffering_percent = 0

		gobject.timeout_add(100, self.on_status_update)

	def init_elements(self):
		pass

	def on_sync_message(self, bus, message):
		if message.structure is None:
			return

		if message.structure.get_name() == 'prepare-xwindow-id':
			# Sync with the X server before giving the X-id to the sink
			gtk.gdk.threads_enter()
			gtk.gdk.display_get_default().sync()
			self.videowidget.set_sink(message.src)
			message.src.set_property('force-aspect-ratio', True)
			gtk.gdk.threads_leave()

	def on_message(self, bus, message):
		t = message.type
		if t == gst.MESSAGE_ERROR:
			err, debug = message.parse_error()
			print "Error: %s" % err, debug
			if self.on_eos:
				self.on_eos()
			self.playing = False
		elif t == gst.MESSAGE_EOS:
			if self.on_eos:
				self.on_eos()
			self.playing = False
		elif t == gst.MESSAGE_BUFFERING:
			self.process_buffering_stats(message)

	def process_buffering_stats(self, message):
		percent = message.parse_buffering()
		self.stats_buffering_percent = percent

		if percent < 100 and not self.started_buffering:
			self.started_buffering = True
			self.was_playing = self.is_playing()
			if self.was_playing:
				self.pause()

		if percent == 100 and self.started_buffering:
			self.started_buffering = False
			if self.was_playing:
				self.real_play()

	def on_status_update(self):
		return False

	def set_location(self, location):
		pass

	def query_position(self):
		"Returns a (position, duration) tuple"
		try:
			position, format = self.player.query_position(gst.FORMAT_TIME)
		except:
			position = gst.CLOCK_TIME_NONE

		try:
			duration, format = self.player.query_duration(gst.FORMAT_TIME)
		except:
			duration = gst.CLOCK_TIME_NONE

		return (position, duration)

	def seek(self, location):
		"""
		@param location: time to seek to, in nanoseconds
		"""
		gst.debug("seeking to %r" % location)
		event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
			gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
			gst.SEEK_TYPE_SET, location,
			gst.SEEK_TYPE_NONE, 0)

		res = self.player.send_event(event)
		if res:
			gst.info("setting new stream time to 0")
			self.player.set_new_stream_time(0L)
		else:
			gst.error("seek to %r failed" % location)

	def pause(self):
		gst.info("pausing player")
		self.player.set_state(gst.STATE_PAUSED)
		self.playing = False

	def play(self):
		if not self.cmd_args.live:
			self.real_play()
			return
		self.seek_latest()

	def real_play(self):
		gst.info("playing player")
		self.player.set_state(gst.STATE_PLAYING)
		self.playing = True

	def stop(self):
		self.player.set_state(gst.STATE_NULL)
		gst.info("stopped player")

	def get_state(self, timeout = 1):
		return self.player.get_state(timeout = timeout)

	def is_playing(self):
		return self.playing

	def seek_latest(self):
		def on_message(bus, message):
			if message.type != gst.MESSAGE_ASYNC_DONE:
				return

			print "Got message:", bus, message

			duration = self.src.query_duration()
			bus.disconnect(handle)
			bus.remove_signal_watch()
			self.seek(duration)
			self.real_play()

		bus = self.player.get_bus()
		handle = bus.connect('message', on_message)
		bus.add_signal_watch()
		self.pause()

