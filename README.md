#Install & Usage
This readme record how I installed and made this app come in to work. Chinese readme version: [NDNvideo安装测试记录](https://github.com/jinpf/CCN_Note/blob/master/%E5%BA%94%E7%94%A8-Ndnvideo%E5%AE%89%E8%A3%85%E6%B5%8B%E8%AF%95%E8%AE%B0%E5%BD%95.md).

Any questions contact: **Email: jpflcj@sina.com**

##Environment
I`ve tested on: Ubuntu14.04、VirtualBox4.3.18 and a PC with camera.

For [Virtualbox](https://www.virtualbox.org/wiki/Downloads), be aware to install [VM VirtualBox Extension Pack](http://download.virtualbox.org/virtualbox/4.3.18/Oracle_VM_VirtualBox_Extension_Pack-4.3.18-96516.vbox-extpack).

##Install
In official [BUILD](https://github.com/jinpf/ndnvideo/blob/master/BUILD):
> - ccnx (includes ccnr)
>   If you plan streaming and ccnr crashes when it reaches size around 2GB.
>   Create file `csrc/conf/local.mk` with:
>   `PLATCFLAGS= -O2 -D_FILE_OFFSET_BITS=64 -fPIC`
> 
> - pyccn (git://github.com/remap/PyCCN.git)
> - ndnvideo (play_latest branch - git://github.com/remap/ndnvideo.git)
> 
> - gstreamer 0.10 - will NOT WORK with 1.0... must restrict packages to 0.10 for ndnvideo compatibilty.

###CCNx
see: [https://github.com/ProjectCCNx/ccnx](https://github.com/ProjectCCNx/ccnx)

###PyCCN
see: [https://github.com/named-data/PyCCN](https://github.com/named-data/PyCCN)

###gstreamer
For Ubuntu 14.04:
<!--lang:shell-->
	sudo apt-get update
	sudo apt-get install gstreamer0.10-plugins-ugly python-gst0.10-dev gstreamer0.10-ffmpeg

After installation, simple test for gstreamer:
<!--lang:shell-->
	gst-launch-0.10 videotestsrc ! ximagesink

	# With camera. If you want to test it in a VM, you need to share the real camera with the VM.
	gst-launch-0.10 v4l2src ! ffmpegcolorspace ! ximagesink
	gst-launch-0.10 v4l2src ! 'video/x-raw-yuv,width=400,height=300,format=(fourcc)YUY2;video/x-raw-yuv,format=(fourcc)YV12' ! ffmpegcolorspace ! ximagesink
	gst-launch-0.10 v4l2src ! videoscale ！ 'video/x-raw-yuv,width=400,height=300 ! ffmpegcolorspace ! ximagesink

###NDNvideo
<!--lang:shell-->
	git clone https://github.com/remap/ndnvideo.git
	cd ndnvideo
	git checkout <the latest branch>

##Usage
First, set the ccnx working environment, modify `~/.profile`, at the tail add this(you can change the dir anywhere you like):
<!--lang:shell-->
	# ccnd configure
	export CCND_LOG=$HOME/.ccn/ccnd_log

	# ccnr configure
	export CCNR_DIRECTORY=$HOME/.ccn/repo
	export CCNR_STATUS_PORT=9680

run:
<!--lang:shell-->
	source ~/.profile
	ccndstart
	ccnr &

###Publish video/audio
####local video:
`cd` into `ndnvideo/videostreaming/` and run:
<!--lang:shell-->
	./ccn_launch.py filesrc location=<your video location> ! typefind ! qtdemux name=mux \
	mux.video_00 ! queue ! VideoSink location=/<your designated prefix>/video/video \
	mux.audio_00 ! queue ! AudioSink location=/<your designated prefix>/video/audio

For example, I run this at my experiment:
<!--lang:shell-->
	./ccn_launch.py filesrc location=/home/jinpf/1.mp4 ! typefind ! qtdemux name=mux \
	mux.video_00 ! queue ! VideoSink location=/jinpf/video/video \
	mux.audio_00 ! queue ! AudioSink location=/jinpf/video/audio

####use camera
Make sure you have a camera, and gstreamer test works well.

if you want to have different resolution, modify source code in  `ndnvideo/videostreaming/video_sink.py` like:

![](https://github.com/jinpf/CCN_Note/raw/master/pic/ndnvideo4.png)

`cd` into `ndnvideo/videostreaming/` and run:
<!--lang:shell-->
	# publish video
	./video_sink.py /<your designated prefix>/streaminfo/video

	# publish audio
	./audio_sink.py /<your designated prefix>/streaminfo/audio

For example, I run this at my experiment:
<!--lang:shell-->
	# publish video
	./video_sink.py /jinpf/streaminfo/video

	# publish audio
	./audio_sink.py /jinpf/streaminfo/audio


![](https://github.com/jinpf/CCN_Note/raw/master/pic/ndnvideo5.png)

After published the video into your local ccnx repo, you can use this to have a visual look:
<!--lang:shell-->
	ccnexplore &

**Attention：Don`t use the same prefix/name at different video, if this happened, clear the ccnr repo：**
<!--lang:shell-->
	ccndstop
	cd $CCNR_DIRECTORY
	rm -r *

	#start ccnd
	ccndstart
	ccnr &

###Play video/audio
`cd` into `ndnvideo/videostreaming/` and run:
<!--lang:shell-->
	./play.py /<your designated prefix>

For example, I run this at my experiment:
<!--lang:shell-->
	./play.py /jinpf | tee video_log
This will record play log in file `video_log` if you have problem.