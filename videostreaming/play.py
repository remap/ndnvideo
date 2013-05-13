#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import pygst
pygst.require('0.10')

import gobject
import gtk
import gst

import sys, argparse
import base64

import player, player_gui
import utils
from audio_src import AudioSrc
from video_src import VideoSrc

class GstPlayer(player.GstPlayer):
	__pipeline = """
		multiqueue name=mqueue use-buffering=true max-size-time=500000000
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
			"Multiqueue buffer: %d%% (playing: %s)" % (video_status, audio_status, self.stats_buffering_percent, "Yes" if self.playing else "No"))
		return True

	def set_location(self, location):
		self.vsrc.set_property('location', "%s/video" % location)
		self.asrc.set_property('location', "%s/audio" % location)

		video_input = self.player.get_by_name('video_input')
		audio_input = self.player.get_by_name('audio_input')

		self.vsrc.link(video_input)
		self.asrc.link(audio_input)

	def set_publisher_id(self, publisher_id):
		id = base64.b64encode(publisher_id)
		self.vsrc.set_property('publisher', id)
		self.asrc.set_property('publisher', id)

	def set_parameters(self):
		mqueue = self.player.get_by_name('mqueue')
		mqueue.set_property('use-buffering', self.cmd_args.disable_buffering)
		mqueue.set_property('max-size-time', long(self.cmd_args.max_time * 1000000))

		if self.cmd_args.retry_count is not None:
			self.vsrc.set_property('interest-retry', self.cmd_args.retry_count)
			self.asrc.set_property('interest-retry', self.cmd_args.retry_count)

		if self.cmd_args.video_pipeline_size is not None:
			self.vsrc.set_property('pipeline-size', self.cmd_args.video_pipeline_size)

		if self.cmd_args.audio_pipeline_size is not None:
			self.asrc.set_property('pipeline-size', self.cmd_args.audio_pipeline_size)
def main():
	gobject.threads_init()
	gtk.gdk.threads_init()

	parser = argparse.ArgumentParser(description = 'Plays audio/video stream.', add_help = False)
	parser.add_argument('--player-help', action="help", help = "show this help message and exit")
	parser.add_argument('-l', '--live', action="store_true", help = 'play in live mode')
	parser.add_argument('-d', '--disable-buffering', action="store_false", help = 'disable buffering')
	parser.add_argument('-t', '--max-time', default = 500, type=float, help = 'maximum buffer time for multiqueue (in ms)')
	parser.add_argument('-p', '--publisher-id', help = 'fetch data only from specific publisher (in base64)')
	parser.add_argument('-r', '--retry-count', type=int, help = 'how many times retransmit an interest before giving up')
	parser.add_argument('-v', '--video-pipeline-size', type=int, help = 'Maximum number of pending interests for video stream')
	parser.add_argument('-a', '--audio-pipeline-size', type=int, help = 'Maximum number of pending interests for audio stream')
	parser.add_argument('URI', help = 'URI of the video stream')

	cmd_args = parser.parse_args()

	publisher_id = base64.b64decode(cmd_args.publisher_id) if cmd_args.publisher_id else None

	name, publisher_id = player.get_latest_version(cmd_args.URI, publisher_id)
	if name is None:
		print "No content found at %s" % cmd_args.URI
		return 1

	print("Fetching data from publisher: %s" % base64.b64encode(publisher_id))

	w = player_gui.PlayerWindow(GstPlayer, cmd_args)
	w.load_file(str(name), publisher_id)
	w.show_all()
	gtk.main()

	return 0

if __name__ == '__main__':
	sys.exit(main())
