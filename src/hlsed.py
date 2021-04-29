# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import logging
import m3u
import requests
import time
import urllib
import urlparse

def url_overriding_query_param(url, name, value):
	parsed = urlparse.urlparse(url)
	query = dict(urlparse.parse_qsl(parsed.query))
	query[name] = value
	return urlparse.urlunparse(urlparse.ParseResult(
		scheme = parsed.scheme,
		netloc = parsed.netloc,
		path = parsed.path,
		params = parsed.params,
		query = urllib.urlencode(sorted(query.items(), key = lambda x: x[0])),
		fragment = parsed.fragment
	))
	
def rebase(playlist, playlist_url, proxy_url):
	
	"""
	Modifies the given M3U playlist so:
	- all relative URIs are becoming absolute relative to `playlist_url`;
	- all stream variant playlist URIs (in a master playlist) are proxied via `proxy_url` in its 'url' 
	  query string parameter.
	"""
	
	def make_absolute(uri):
		return urlparse.urljoin(playlist_url, uri) 
			
	# Let's fix up relative URIs in attributes of most of the tags except the ones that will be proxied.
	proxied_tags = ['EXT-X-I-FRAME-STREAM-INF', 'EXT-X-MEDIA']
	for tag in playlist.all_tags():
		if tag.name not in proxied_tags and tag.attributes:
			# We could be checking tags by names, but all the valid tags use 'URI' attributes similarly.
			uri_attr = tag.attributes.get('URI')
			if uri_attr:
				uri_attr.value = make_absolute(uri_attr.value)
	
	if playlist.is_master_playlist:
		# All URIs in a master playlist point to media playlists, which we need to proxy via us.
		# We also need to make original URLs absolute as we are changing the base URL now.
		for item in playlist.uris:			
			item.uri = url_overriding_query_param(proxy_url, "url", make_absolute(item.uri))
		# Some tags refer to playlists as well and we need to proxy them too.
		for tag in playlist.globals:
			if tag.name in proxied_tags:
				uri_attr = tag.attributes.get('URI')
				if uri_attr:
					uri_attr.value = url_overriding_query_param(proxy_url, "url", make_absolute(uri_attr.value))
	else:
		# For media playlists we need to make sure that all segments use absolute URIs.
		for item in playlist.uris:
			item.uri = make_absolute(item.uri)
	
	return playlist
	
def download_and_rebase(playlist_url, proxy_url):
	
	"""
	Downloads and returns an HLS playlist from `playlist_url` rebasing all the URIs in it along the way (see rebase()).
	"""
	
	r = requests.get(playlist_url)
	r.raise_for_status()
	content_type = r.headers.get('content-type')
	if content_type not in ['application/vnd.apple.mpegurl', 'audio/mpegurl', 'vnd.apple.mpegurl', 'application/x-mpegurl']:
		raise Exception("The playlist has unsupported content type ('%s')" % (content_type,))

	playlist = m3u.Playlist(r.text)	
	rebase(playlist, playlist_url, proxy_url)
	return playlist
	
def event_to_vod(playlist, event_duration, ref_time, current_time, logger = logging.getLogger(__name__)):
	
	"""
	This is to turn a regular or EVENT media playlist into a VOD after some time passes. 
	"""
	
	assert(isinstance(playlist, m3u.Playlist))
	
	# This modification is not applicable to master playlists.
	assert(not playlist.is_master_playlist)
	
	playlist.remove_global_tag('EXT-X-PLAYLIST-TYPE')
	playlist.remove_global_tag('EXT-X-ENDLIST')

	# We need to pretend that the event started a bit earlier than the time we started watching this playlist, 
	# so we can vend at least one segment (ideally 3x target durations worth of them).
	target_duration = playlist.target_duration()
	start_time = ref_time - 3 * target_duration
	
	t = current_time - start_time
	
	# logger.debug("event_duration: %f, t: %.0f, target_duration: %.3f" % (event_duration, t, target_duration))
	
	uris = []
	segment_end = 0
	for u in playlist.uris:
		segment_end += u.duration()
		if segment_end > min(t, event_duration):
			break
		uris.append(u)
		
	# logger.debug("segments: %d out of %d" % (len(uris), len(playlist.uris)))	

	playlist.uris = uris
	
	# Where are we within the period.
	if t <= event_duration:
		# Regular/EVENT mode.		
		logger.debug("EVENT mode")	
		# TODO: allow to use regular (no type tag)
		playlist.globals.append(m3u.Tag('#EXT-X-PLAYLIST-TYPE:EVENT'))
	else:
		# VOD mode.
		logger.debug("VOD mode")	
		playlist.globals.append(m3u.Tag('#EXT-X-PLAYLIST-TYPE:VOD'))
		playlist.globals.append(m3u.Tag('#EXT-X-ENDLIST'))
