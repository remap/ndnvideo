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
		videomixer name=mix ! ffmpegcolorspace ! videoscale ! %s
		identity name=video_input_1 ! ffdec_h264 !
			textoverlay font-desc="Sans 24" text="CAM1" valign=top halign=left shaded-background=true !
			videobox border-alpha=0 top=0 left=0 ! mqueue. mqueue. ! mix.
		identity name=video_input_2 ! ffdec_h264 !
			textoverlay font-desc="Sans 24" text="CAM2" valign=top halign=left shaded-background=true !
			videobox border-alpha=0 top=0 left=-352 ! mqueue. mqueue. ! mix.
		identity name=video_input_3 ! ffdec_h264 !
			textoverlay font-desc="Sans 24" text="CAM3" valign=top halign=left shaded-background=true !
			videobox border-alpha=0 top=-0 left=-704 ! mqueue. mqueue. ! mix.
		identity name=video_input_main ! ffdec_h264 !
			textoverlay font-desc="Sans 12" text="MAIN" valign=top halign=left shaded-background=true !
			videobox border-alpha=0 top=-240 left=0 ! mqueue. mqueue. ! mix.
		identity name=audio_input ! ffdec_mp3 ! audioconvert ! mqueue. mqueue. ! %s
	""" % (utils.video_sink, utils.audio_sink)

	def init_elements(self):
		'''
		self.vsrc = gst.element_factory_make("VideoSrc")
		self.asrc = gst.element_factory_make("AudioSrc")
		self.player.add(self.vsrc)
		self.player.add(self.asrc)
		self.src = self.asrc
		'''
		self.vsrc_main = gst.element_factory_make("VideoSrc")
		self.vsrc_1 = gst.element_factory_make("VideoSrc")
		self.vsrc_2 = gst.element_factory_make("VideoSrc")
		self.vsrc_3 = gst.element_factory_make("VideoSrc")
		self.asrc = gst.element_factory_make("AudioSrc")
		
		self.player.add(self.vsrc_main)
		self.player.add(self.vsrc_1)
		self.player.add(self.vsrc_2)
		self.player.add(self.vsrc_3)
		self.player.add(self.asrc)
		
		self.src = self.asrc
		
	def on_status_update(self):
		video0_status = self.vsrc_main.get_status()
		video1_status = self.vsrc_1.get_status()
		video2_status = self.vsrc_2.get_status()
		video3_status = self.vsrc_3.get_status()
		audio_status = self.asrc.get_status()
		self.emit("status-updated", 
			"Video0: %s\n"
			"Video1: %s\n"
			"Video2: %s\n"
			"Video3: %s\n"
			"Audio: %s\n"
			"Buffer: %d%% (playing: %s)" % (video0_status, video1_status, video2_status, video3_status, audio_status, self.stats_buffering_percent, "Yes" if self.playing else "No"))
		return True

	def set_location(self, location):
		'''
		self.vsrc.set_property('location', "%s/video" % location)
		self.asrc.set_property('location', "%s/audio" % location)
		video_input = self.player.get_by_name('video_input')
		audio_input = self.player.get_by_name('audio_input')
		self.vsrc.link(video_input)
		self.asrc.link(audio_input)
		'''
		
		self.vsrc_main.set_property('location', "%s/mainvideo/video" % location)
		self.vsrc_1.set_property('location', "%s/video1" % location)
		self.vsrc_2.set_property('location', "%s/video2" % location)
		self.vsrc_3.set_property('location', "%s/video3" % location)
		self.asrc.set_property('location', "%s/mainvideo/audio" % location)
		
		video_input_main = self.player.get_by_name('video_input_main')
		video_input_1 = self.player.get_by_name('video_input_1')
		video_input_2 = self.player.get_by_name('video_input_2')
		video_input_3 = self.player.get_by_name('video_input_3')
		audio_input = self.player.get_by_name('audio_input')
		
		self.vsrc_main.link(video_input_main)
		self.vsrc_1.link(video_input_1)
		self.vsrc_2.link(video_input_2)
		self.vsrc_3.link(video_input_3)
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

	name = name

	w = player_gui.PlayerWindow(GstPlayer, cmd_args)
	w.load_file(str(name))
	w.show_all()
	gtk.main()

	return 0

if __name__ == '__main__':
	sys.exit(main())
