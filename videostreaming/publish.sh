#! /bin/sh

while true
do
	#ccndstart

	rm $CCNR_DIRECTORY/import/*
	rm $CCNR_DIRECTORY/repoFile1
	rm -r $CCNR_DIRECTORY/index
	ccnrm /ndn/ucla.edu/apps/video

	ccnr &
	sleep 5
	./publish.py /ndn/ucla.edu/apps/video av
	killall ccnr
done
