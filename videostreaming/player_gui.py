import pygtk
pygtk.require('2.0')
import pygst
pygst.require('0.10')

import gobject
import gtk
import gst

import datetime

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

gobject.type_register(VideoWidget)

class PlayerWindow(gtk.Window):
	UPDATE_INTERVAL = 500

	def __init__(self, gst_player, cmd_args):
		gtk.Window.__init__(self)
		self.set_default_size(670, 580)

		self.create_ui()

		self.player = gst_player(self.videowidget, cmd_args)
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

		seconds = int(real / gst.SECOND)
		return str(datetime.timedelta(seconds = seconds))

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
				self.player.real_play()

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

gobject.type_register(PlayerWindow)
