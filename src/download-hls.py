#!/usr/bin/env python

# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

# This can download HLS VOD streams for local storage, mainly used as a test for m3u module.

import aliases
import argparse
import m3u
import os
import re
import requests
import sys
import urlparse

def download_file(uri, local_path, skip = False):
	
	print(" - %s -> '%s'" % (uri, local_path))

	# Note that it would be unsafe to wipe the output directory.
	local_dir = os.path.dirname(local_path)
	if not os.path.exists(local_dir):
		os.makedirs(local_dir)

	if skip:
		# Note that directory is still created, so we can see the structure.
		print("   skipped.")
	else:		
		r = requests.get(uri)
		r.raise_for_status()
		with open(local_path, 'w') as f:
			f.write(r.content)
	
def download_playlist(playlist_url, local_playlist_path, skip_media, expect_media_playlist = False):
	
	print("Downloading a playlist from '%s' to '%s'..." % (playlist_url, local_playlist_path))
			
	r = requests.get(playlist_url)
	r.raise_for_status()
	playlist = m3u.Playlist(r.text)
	
	output_dir = os.path.dirname(local_playlist_path)
		
	if playlist.is_master_playlist:

		print("This is a master playlist")
		
		if expect_media_playlist:
			raise Exception("Expected a media playlist while got a master one")
			
		# In a master playlist all URIs are other playlists.
		media_dir_seq = 0
		for item in playlist.uris:
			absolute_item_uri = urlparse.urljoin(playlist_url, item.uri)
			
			relative_playlist_path = os.path.join("variants", str(media_dir_seq), "variant.m3u8")			
			playlist_path = os.path.join(output_dir, relative_playlist_path)
			media_dir_seq += 1
			
			download_playlist(absolute_item_uri, playlist_path, skip_media, expect_media_playlist = True)
			item.uri = relative_playlist_path
		
		playlist.save(local_playlist_path)
		print("Saved the master playlist.")
		
	else:
		
		print("This is a media playlist")		

		media_dir = os.path.join(output_dir, "media")
		media_dir_counter = 0
	
		for item in playlist.uris:
			absolute_uri = urlparse.urljoin(playlist_url, item.uri)
			
			# It's handy to preserve the extension, if any.
			extension = os.path.splitext(urlparse.urlparse(item.uri).path)[1]
			local_relative_path = os.path.join("media", str(media_dir_counter) + extension)
			media_dir_counter += 1
						
			download_file(absolute_uri, os.path.join(output_dir, local_relative_path), skip_media)
			
			item.uri = local_relative_path			

		playlist.save(local_playlist_path)
		print("Saved the media playlist.")

parser = argparse.ArgumentParser()
parser.add_argument(
	"url", 
	help = "The URL of the master HLS playlist or an alias for a well-known example, e.g. 'bipbop'."
)
parser.add_argument(
	"-o", "--output-dir", default = './output', 
	help = "The directory for all downloaded files."
)
parser.add_argument(
	"-s", "--skip-media", action='store_true',
	help = "Download playlists only skipping media segments. (Used for debugging.)"
)
args = parser.parse_args()

playlist_path = os.path.join(args.output_dir, "index.m3u8")

download_playlist(
	aliases.resolve_hls(args.url), 
	playlist_path, 
	skip_media = args.skip_media
)

print("Done.")
