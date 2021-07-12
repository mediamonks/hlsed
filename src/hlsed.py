# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import logging
import m3u
import requests
import scte35
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

def start_time_and_effective_duration(playlist, event_duration, ref_time, current_time):
	# We need to pretend that the event started a bit earlier than the time we started watching this playlist, 
	# so we can vend at least one segment (ideally 3x target durations worth of them).
	start_time = ref_time - 3 * playlist.target_duration()
	effective_duration = min(current_time - start_time, event_duration)
	return start_time, effective_duration

def time_as_iso8601(t):
	return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))

CUE_STYLE_IN_OUT = 0
CUE_STYLE_BUG_OUT = 1

def insert_ad_cues(
	playlist, 
	event_duration, 
	ref_time, 
	current_time, 	
	time_between_ads, 
	ad_duration, 
	style = CUE_STYLE_IN_OUT,
	logger = logging.getLogger(__name__)
):
	"""
	This is to insert ad cue points into a media playlist.

	Parameters:
	- time_between_ads: Time in seconds between the end of the last ad (or the start of the stream) 
		and the start of the next ad.
	- ad_duration: The duration in seconds of each ad slot.

	See event_to_vod() for the other parameters.
	"""
	
	assert(isinstance(playlist, m3u.Playlist) and not playlist.is_master_playlist)	

	start_time, length = start_time_and_effective_duration(playlist, event_duration, ref_time, current_time)
		
	def tag(index, attrs):
		# I don't have a non-raw initializer just yet, but it should be safe to concatenate here.
		return m3u.Tag('#EXT-X-DATERANGE:ID="ad%d",%s' % (index, ','.join(attrs)))
	
	def out_tag(index, t, duration):
		attrs = []
		attrs.append('START-DATE="%s"' % (time_as_iso8601(t),))
		attrs.append('PLANNED-DURATION=%.2f' % (duration,))
		if style == CUE_STYLE_IN_OUT:
			attrs.append('SCTE35-OUT=0x%s' % (scte35.splice_info_with_splice_insert(index, True, t - start_time)))
		elif style == CUE_STYLE_BUG_OUT:
			attrs.append('SCTE35-OUT=0x%s' % (scte35.splice_info_with_splice_insert(index, True, t - start_time, duration, True)))
		else:
			assert(False)
		return tag(index, attrs)

	def in_tag(index, t, duration):
		attrs = []
		attrs.append('END-DATE="%s"' % (time_as_iso8601(t),))
		attrs.append('DURATION=%.2f' % (duration,))
		if style == CUE_STYLE_IN_OUT:
			attrs.append('SCTE35-IN=0x%s' % (scte35.splice_info_with_splice_insert(index, False, t - start_time)))
		elif style == CUE_STYLE_BUG_OUT:
			# Elemental does not produce SCTE35 for the IN cue because it's using auto_return in break_duration().
			pass
		else:
			assert(False)
		return tag(index, attrs)

	index = 0
	t = start_time
	while True:
		t += time_between_ads
		if current_time < t:
			break
		playlist.globals.append(out_tag(index, t, ad_duration))
		# playlist.globals.append(single_tag(index, t, ad_duration))

		t += ad_duration
		if current_time < t:
			break
		playlist.globals.append(in_tag(index, t, ad_duration))
		
		index += 1
	
	return

def event_to_vod(
	playlist, 
	event_duration, 
	ref_time, 
	current_time, 
	program_date_time = False,
	logger = logging.getLogger(__name__)
):
	
	"""
	This is to turn a regular or EVENT media playlist into a VOD after some time passes. 

	Parameters:
	- playlist: -
	- event_duration: How long the stream is expected to stay in the EVENT mode, seconds.
	- ref_time: The real time (Unix timestamp) the streaming started. 
		This is not the real time of the first sample of the stream, which is calculated to be a bit earlier 
		to avoid initial stalls in the playback.
	- current_time: What time is "now" (Unix timestamp). This defined how many segments should be left 
		in the playlist and when it should turn into a VOD.
	- program_date_time: If True, then the real time information corresponding to ref_time is embedded 
		into the playlist via a single `EXT-X-PROGRAM-DATE-TIME` tag before the first segment.
	- logger: -
	"""
	
	assert(isinstance(playlist, m3u.Playlist) and not playlist.is_master_playlist)	
	
	playlist.remove_global_tag('EXT-X-PLAYLIST-TYPE')
	playlist.remove_global_tag('EXT-X-ENDLIST')

	start_time, effective_duration = start_time_and_effective_duration(playlist, event_duration, ref_time, current_time)
	
	# Let's embed the real time tag along the way.
	playlist.globals.append(m3u.Tag('#EXT-X-PROGRAM-DATE-TIME:' + time_as_iso8601(start_time)))
			
	uris = []
	segment_end = 0
	for u in playlist.uris:
		segment_end += u.duration()
		if segment_end > effective_duration:
			break
		uris.append(u)

	playlist.uris = uris
	
	# Where are we within the period.
	if current_time - start_time <= event_duration:
		# We are within the event's duration. Regular or EVENT mode.
		logger.debug("EVENT mode")	
		# TODO: allow to use the regular mode (i.e. when no tag is specified)
		playlist.globals.append(m3u.Tag('#EXT-X-PLAYLIST-TYPE:EVENT'))
	else:
		# The event is over. VOD mode.
		logger.debug("VOD mode")	
		playlist.globals.append(m3u.Tag('#EXT-X-PLAYLIST-TYPE:VOD'))
		playlist.globals.append(m3u.Tag('#EXT-X-ENDLIST'))
