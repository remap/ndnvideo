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
from audio_src import AudioSrc
from video_src import VideoSrc

class GstPlayer(player.GstPlayer):
	__pipeline = """
		multiqueue name=mqueue use-buffering=true
		identity name=video_input ! ffdec_h264 ! mqueue. mqueue. ! %s \
		identity name=audio_input ! decodebin ! mqueue. mqueue. ! %s
	""" % (utils.video_sink, utils.audio_sink)

	def init_elements(self):
		self.vsrc = gst.element_factory_make("VideoSrc")
		self.asrc = gst.element_factory_make("AudioSrc")
		self.player.add(self.vsrc)
		self.player.add(self.asrc)
		self.src = self.asrc

	def on_status_update(self):
		video_status = self.vsrc.get_status()
		audio_status = self.asrc.get_status()
		self.emit("status-updated", 
			"Video: %s\n"
			"Audio: %s\n"
			"Buffer: %d%% (playing: %s)" % (video_status, audio_status, self.stats_buffering_percent, "Yes" if self.playing else "No"))
		return True

	def set_location(self, location):
		self.vsrc.set_property('location', "%s/video" % location)
		self.asrc.set_property('location', "%s/audio" % location)

		video_input = self.player.get_by_name('video_input')
		audio_input = self.player.get_by_name('audio_input')

		self.vsrc.link(video_input)
		self.asrc.link(audio_input)

def main():
	gobject.threads_init()
	gtk.gdk.threads_init()

	parser = argparse.ArgumentParser(description = 'Plays audio/video stream.', add_help = False)
	parser.add_argument('--player-help', action="help", help = "show this help message and exit")
	parser.add_argument('-l', '--live', action="store_true", help = 'play in live mode')
	parser.add_argument('URI', help = 'URI of the video stream')

	cmd_args = parser.parse_args()
#
	name = player.get_latest_version(cmd_args.URI)
	if name is None:
		print "No content found at %s" % cmd_args.URI
		return 1

	w = player_gui.PlayerWindow(GstPlayer, cmd_args)
	w.load_file(str(name))
	w.show_all()
	gtk.main()

	return 0

if __name__ == '__main__':
	sys.exit(main())
