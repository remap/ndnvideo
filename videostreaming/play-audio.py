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

class GstPlayer(player.GstPlayer):
	__pipeline = """
		queue2 name=audio_input use-buffering=true ! ffdec_mp3 !
		tee name=t ! queue ! %s
		t. ! queue ! goom ! colorspace ! %s
	""" % (utils.audio_sink, utils.video_sink)

	def init_elements(self):
		self.asrc = gst.element_factory_make("AudioSrc")
		self.player.add(self.asrc)
		self.src = self.asrc

	def on_status_update(self):
		audio_status = self.asrc.get_status()
		self.emit("status-updated", 
			"Audio: %s\n"
			"Buffer: %d%% (playing: %s)" % (audio_status, self.stats_buffering_percent, "Yes" if self.playing else "No"))
		return True

	def set_location(self, location):
		self.asrc.set_property('location', location)
		audio_input = self.player.get_by_name('audio_input')
		self.asrc.link(audio_input)

def main(args):
	gobject.threads_init()
	gtk.gdk.threads_init()

	parser = argparse.ArgumentParser(description = 'Plays audio stream.', add_help = False)
	parser.add_argument('--player-help', action="help", help = "show this help message and exit")
	parser.add_argument('-l', '--live', action="store_true", help = 'play in live mode')
	parser.add_argument('URI', help = 'URI of the audio stream')

	cmd_args = parser.parse_args()

	w = player_gui.PlayerWindow(GstPlayer, cmd_args)
	w.load_file(cmd_args.URI)
	w.show_all()

	gtk.main()

if __name__ == '__main__':
	sys.exit(main(sys.argv))
