#!/bin/bash

if [ ! -d "out" ]
then
	mkdir out
	mkdir out/Default
	# Do gclient sync only for initial build,
	# as it takes a long time to do for every build
	gclient sync
	mv -fvn src/* .
	rm -rf src
	sudo apt install ninja-build
fi


# Build AlphaRTC.
gn gen out/Default --args='is_debug=false'

# Build AlphaRTC e2e app that uses GCC (peerconnection_serverless.gcc).
ninja -C out/Default peerconnection_challenge_client
cp out/Default/peerconnection_challenge_client peerconnection_serverless.r3net
