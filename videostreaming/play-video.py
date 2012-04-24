#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import pygst
pygst.require('0.10')

import gobject
import gtk
import gst

import sys, argparse

import player, player_gui
import utils
from video_src import VideoSrc

class GstPlayer(player.GstPlayer):
	__pipeline = """
		queue2 name=video_input use-buffering=true ! decodebin2 ! %s
	""" % utils.video_sink

	def init_elements(self):
		self.vsrc = gst.element_factory_make("VideoSrc")
		self.player.add(self.vsrc)
		self.src = self.vsrc

	def on_status_update(self):
		video_status = self.vsrc.get_status()
		self.emit("status-updated", 
			"Video: %s\n"
			"Buffer: %d%% (playing: %s)" % (video_status, self.stats_buffering_percent, "Yes" if self.playing else "No"))
		return True

	def set_location(self, location):
		self.vsrc.set_property('location', location)
		video_input = self.player.get_by_name('video_input')
		self.vsrc.link(video_input)

def main(args):
	gobject.threads_init()
	gtk.gdk.threads_init()

	parser = argparse.ArgumentParser(description = 'Plays video stream.', add_help = False)
	parser.add_argument('--player-help', action="help", help = "show this help message and exit")
	parser.add_argument('-l', '--live', action="store_true", help = 'play in live mode')
	parser.add_argument('URI', help = 'URI of the video stream')

	cmd_args = parser.parse_args()

	w = player_gui.PlayerWindow(GstPlayer, cmd_args)
	w.load_file(cmd_args.URI)
	w.show_all()

	gtk.main()

if __name__ == '__main__':
	sys.exit(main(sys.argv))
