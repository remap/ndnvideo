#! /bin/sh

# this is a variation of publish crash-protection loop
# that allows for interactive URI from user input
# intended for use on NDN Node Testbed

echo "what is intended URI of stream ? ie: /ndn/ucla.edu/apps/video"

read URI

while true
do
	#ccndstart

	rm $CCNR_DIRECTORY/import/*
	rm $CCNR_DIRECTORY/repoFile1
	rm -r $CCNR_DIRECTORY/index
	ccnrm $URI

	ccnr &
	sleep 5
	./publish.py $URI av
	killall ccnr
done
