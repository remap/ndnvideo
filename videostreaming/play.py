#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import pygtk
pygtk.require('2.0')

import sys
import os

import gobject
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import gtk
gtk.gdk.threads_init()

import utils
from video_src import VideoSrc
from audio_src import AudioSrc

class GstPlayer(gobject.GObject):
	__gsignals__ = {
		'status-updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
			(str,))
	}

	def __init__(self, videowidget):
		gobject.GObject.__init__(self)
		self.playing = False

		self.player = gst.parse_launch("multiqueue use-buffering=true name=mqueue \
				identity name=video_input ! mqueue. mqueue. ! ffdec_h264 max-threads=3 ! %s \
				identity name=audio_input ! mqueue. mqueue. ! ffdec_mp3 ! %s" % (utils.video_sink, utils.audio_sink))
		self.vsrc = gst.element_factory_make("VideoSrc")
		self.asrc = gst.element_factory_make("AudioSrc")
		self.player.add(self.vsrc)
		self.player.add(self.asrc)

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
				self.play()

	def on_status_update(self):
		video_status = self.vsrc.get_status()
		audio_status = self.asrc.get_status()
		self.emit("status-updated", "Video: %s\n"
				"Audio: %s\n"
				"Buffer: %d%% (playing: %s)" % (video_status, audio_status, self.stats_buffering_percent, self.playing))
		return True

	def set_location(self, location):
		self.vsrc.set_property('location', "%s/video" % location)
		self.asrc.set_property('location', "%s/audio" % location)

		video_input = self.player.get_by_name('video_input')
		audio_input = self.player.get_by_name('audio_input')
		self.vsrc.link(video_input)
		self.asrc.link(audio_input)

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

class VideoWidget(gtk.DrawingArea):
	def __init__(self):
		gtk.DrawingArea.__init__(self)
		self.imagesink = None
		self.unset_flags(gtk.DOUBLE_BUFFERED)

	def do_expose_event(self, event):
		if self.imagesink:
			self.imagesink.expose()
			return False
		else:
			return True

	def set_sink(self, sink):
		assert self.window.xid
		self.imagesink = sink
		self.imagesink.set_xwindow_id(self.window.xid)

class PlayerWindow(gtk.Window):
	UPDATE_INTERVAL = 500

	def __init__(self):
		gtk.Window.__init__(self)
		self.set_default_size(704, 480)

		self.create_ui()

		self.player = GstPlayer(self.videowidget)
		self.player.connect("status-updated", self._status_updated)

		def on_eos():
			self.player.seek(0L)
			self.play_toggled()
		self.player.on_eos = lambda * x: on_eos()

		self.update_id = -1
		self.changed_id = -1
		self.seek_timeout_id = -1

		self.p_position = gst.CLOCK_TIME_NONE
		self.p_duration = gst.CLOCK_TIME_NONE

		def on_delete_event():
			self.player.stop()
			gtk.main_quit()
		self.connect('delete-event', lambda * x: on_delete_event())

	def load_file(self, location):
		self.player.set_location(location)

	def create_ui(self):
		vbox = gtk.VBox()
		self.add(vbox)

		self.videowidget = VideoWidget()
		vbox.pack_start(self.videowidget)

		hbox = gtk.HBox()
		vbox.pack_start(hbox, fill = False, expand = False)

		self.pause_image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
			gtk.ICON_SIZE_BUTTON)
		self.pause_image.show()
		self.play_image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
			gtk.ICON_SIZE_BUTTON)
		self.play_image.show()
		self.button = button = gtk.Button()
		button.add(self.play_image)
		button.set_property('can-default', True)
		button.set_focus_on_click(False)
		button.show()
		hbox.pack_start(button, False)
		button.set_property('has-default', True)
		button.connect('clicked', lambda * args: self.play_toggled())

		self.adjustment = gtk.Adjustment(0.0, 0.00, 100.0, 0.1, 1.0, 1.0)
		hscale = gtk.HScale(self.adjustment)
		hscale.set_digits(2)
		hscale.set_update_policy(gtk.UPDATE_CONTINUOUS)
		hscale.connect('button-press-event', self.scale_button_press_cb)
		hscale.connect('button-release-event', self.scale_button_release_cb)
		hscale.connect('format-value', self.scale_format_value_cb)
		hbox.pack_start(hscale)
		self.hscale = hscale

		self.img_forward = gtk.image_new_from_stock(gtk.STOCK_MEDIA_FORWARD,
			gtk.ICON_SIZE_BUTTON)
		self.img_forward.show()
		self.btn_live = button = gtk.Button()
		button.add(self.img_forward)
		button.set_focus_on_click(False)
		button.show()
		hbox.pack_start(button, False)
		button.connect('clicked', lambda * args: self.seek_latest())

		frame = gtk.Frame("Status")
		self.lbl_status = gtk.Label()
		self.lbl_status.set_justify(gtk.JUSTIFY_LEFT)
		self.lbl_status.set_text("Hello")
		frame.add(self.lbl_status)
		vbox.pack_end(frame, False)

		self.videowidget.connect_after('realize',
				lambda * x: self.play_toggled())

	def play_toggled(self):
		self.button.remove(self.button.child)
		if self.player.is_playing():
			self.player.pause()
			self.button.add(self.play_image)
		else:
			self.player.play()
			if self.update_id == -1:
				self.update_id = gobject.timeout_add(self.UPDATE_INTERVAL,
				                 self.update_scale_cb)
			self.button.add(self.pause_image)

	def seek_latest(self):
		unused_position, duration = self.player.query_position()
		self.player.seek(duration)

	def scale_format_value_cb(self, scale, value):
		if self.p_duration == -1:
			real = 0
		else:
			real = value * self.p_duration / 100

		seconds = real / gst.SECOND
		minutes = seconds / 60

		hours = minutes / 60
		minutes %= 60
		seconds %= 60

		return "%02d:%02d:%02d" % (hours, minutes, seconds)

	def scale_button_press_cb(self, widget, event):
		# see seek.c:start_seek
		gst.debug('starting seek')

		self.button.set_sensitive(False)
		self.btn_live.set_sensitive(False)
		self.was_playing = self.player.is_playing()
		if self.was_playing:
			self.player.pause()

		# don't timeout-update position during seek
		if self.update_id != -1:
			gobject.source_remove(self.update_id)
			self.update_id = -1

		# make sure we get changed notifies
		if self.changed_id == -1:
			self.changed_id = self.hscale.connect('value-changed',
				self.scale_value_changed_cb)

	def scale_value_changed_cb(self, scale):
		self.seek_to = long(scale.get_value() * self.p_duration / 100) # in ns
#		# see seek.c:seek_cb
#		real = long(scale.get_value() * self.p_duration / 100) # in ns
#		gst.debug('value changed, perform seek to %r' % real)
#		self.player.seek(real)
#		# allow for a preroll
#		self.player.get_state(timeout=50*gst.MSECOND) # 50 ms

	def scale_button_release_cb(self, widget, event):
		# see seek.c:seek_cb
		real = self.seek_to
		gst.debug('value changed, perform seek to %r' % real)
		self.player.seek(real)
		# allow for a preroll
		#self.player.get_state(timeout=50*gst.MSECOND) # 50 ms

		# see seek.cstop_seek
		widget.disconnect(self.changed_id)
		self.changed_id = -1

		self.btn_live.set_sensitive(True)
		self.button.set_sensitive(True)
		if self.seek_timeout_id != -1:
			gobject.source_remove(self.seek_timeout_id)
			self.seek_timeout_id = -1
		else:
			gst.debug('released slider, setting back to playing')
			if self.was_playing:
				self.player.play()

		if self.update_id != -1:
			self.error('Had a previous update timeout id')
		else:
			self.update_id = gobject.timeout_add(self.UPDATE_INTERVAL,
				self.update_scale_cb)

	def update_scale_cb(self):
		self.p_position, self.p_duration = self.player.query_position()
		if self.p_position != gst.CLOCK_TIME_NONE:
			value = self.p_position * 100.0 / self.p_duration
			self.adjustment.set_value(value)

		return True

	def _status_updated(self, player, value):
		self.lbl_status.set_text(value)

def main(args):
	def usage():
		sys.stderr.write("usage: %s URI-OF-MEDIA-FILE\n" % args[0])
		sys.exit(1)

	# Need to register our derived widget types for implicit event
	# handlers to get called.
	gobject.type_register(PlayerWindow)
	gobject.type_register(VideoWidget)

	w = PlayerWindow()

	if len(args) != 2:
		usage()

	w.load_file(args[1])
	w.show_all()

	gtk.main()

if __name__ == '__main__':
	sys.exit(main(sys.argv))
