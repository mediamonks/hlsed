# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

from flask import Flask, request, url_for, make_response, abort, render_template
import aliases
import hlsed
import m3u
import urllib
import urlparse
import time

app = Flask(__name__)

# Parameter names for our main endpoint, to be able to rename them in one place and let them show up in help.
URL_ARG = "url"
START_TIME_ARG = "ref_time"
EVENT_DURATION_ARG = "duration"

@app.route('/')
def help():
	return render_template(	
		'index.html', 
		aliases = aliases.HLS,
		url_arg = URL_ARG,
		start_time_arg = START_TIME_ARG,
		event_duration_arg = EVENT_DURATION_ARG
	)

def string_param(name, default = None):
	v = request.args.get(name)
	if v:
		return v
	else:
		if default:
			return default
		else:
			raise Exception("Parameter '%s' is required" % (name,))

def int_param(name, default = None):
	return int(string_param(name, default))
	
@app.route('/v1/eventify')
def proxy():
		
	try:
	
		# Note that we cannot support URLs that are served by us, that would cause a deadlock, 
		# and thus we don't attempt to make them absolute.
		playlist_url = aliases.resolve_hls(string_param(URL_ARG))
	
		proxy_url = request.url

		# Let's use the current server time as a reference when the playlist is accessed withot one.
		start_time = int_param(START_TIME_ARG, int(time.time()))
		proxy_url = hlsed.url_overriding_query_param(proxy_url, START_TIME_ARG, str(start_time))
	
		try:
			playlist = hlsed.download_and_rebase(playlist_url, proxy_url)
		except Exception as e:
			return ("Could not download or parse the given playlist: %s." % (e), 400)

		if playlist.is_master_playlist:
			# Not much things to do for the master playlist yet.
			pass
		else:
			hlsed.event_to_vod(
				playlist, 
				event_duration = int_param(EVENT_DURATION_ARG, 60), 
				ref_time = start_time, 
				current_time = time.time(),
				logger = app.logger
			)
	except Exception as e:
		app.logger.error("Error: %s" % (e))
		return ("Unable to proxy: %s." % (e), 400)
		
	text = playlist.text()
	#~ app.logger.debug(text)
	response = make_response(text)
	response.mimetype = "application/vnd.apple.mpegurl"
	response.headers["Cache-Control"] = "max-age=2"
	return response
