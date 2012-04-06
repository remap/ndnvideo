#! /bin/sh

while true
do
	ccndstart
	ccnrdel
	ccnr &
	sleep 5
	./publish.py /ndn/ucla.edu/apps/video m
	killall ccnr
done
