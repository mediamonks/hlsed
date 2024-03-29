# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

from flask import Flask, request, url_for, make_response, abort, render_template
import aliases
import hlsed
import m3u
import time
import urllib
import urlparse

app = Flask(__name__)

# Parameter names for our main endpoint, to be able to rename them in one place and let them show up in help.
URL_ARG = "url"
START_TIME_ARG = "ref_time"
EVENT_DURATION_ARG = "duration"
AD_INTERVAL_ARG = "ad_interval"
AD_DURATION_ARG = "ad_duration"
AD_STYLE_ARG = "ad_style"

@app.route('/')
def help():
	return render_template(	
		'index.html', 
		aliases = aliases.HLS,
		url_arg = URL_ARG,
		start_time_arg = START_TIME_ARG,
		event_duration_arg = EVENT_DURATION_ARG,
		ad_interval_arg = AD_INTERVAL_ARG,
		ad_duration_arg = AD_DURATION_ARG,
		ad_style_arg = AD_STYLE_ARG
	)

def string_param(name, default = None):
	v = request.args.get(name)
	if v:
		return v
	else:
		if default is not None:
			return default
		else:
			raise Exception("Parameter '%s' is required" % (name,))

def int_param(name, default = None):
	return int(string_param(name, default))

def url_overriding_scheme(url, scheme):
	parsed = urlparse.urlparse(url)
	return urlparse.urlunparse(urlparse.ParseResult(
		scheme = scheme,
		netloc = parsed.netloc,
		path = parsed.path,
		params = parsed.params,
		query = parsed.query,
		fragment = parsed.fragment
	))
	
@app.route('/v1/eventify')
@app.route('/v1/eventify.m3u8') # Chrome on Android apparently relies on the extension instead of the content type!
def proxy():
		
	try:
		
		# Note that we cannot support URLs that are served by us, that would cause a deadlock, 
		# and thus we don't attempt to make them absolute.
		playlist_url = aliases.resolve_hls(string_param(URL_ARG))
		
		# Let's force 'https' for our own redirects when not debugging because 
		# nginx might be using `http` with us. 
		# TODO: get the scheme of the original request from the proxy.
		if app.debug:
			proxy_url = request.url
		else:
			proxy_url = url_overriding_scheme(request.url, "https")

		# Let's use the current server time as a reference when the playlist is accessed withot one.
		start_time = int_param(START_TIME_ARG, int(time.time()))
		proxy_url = hlsed.url_overriding_query_param(proxy_url, START_TIME_ARG, str(start_time))

		event_duration = int_param(EVENT_DURATION_ARG, 60), 
		ad_interval = int_param(AD_INTERVAL_ARG, 0)
		ad_duration = int_param(AD_DURATION_ARG, 30)
		ad_style = int_param(AD_STYLE_ARG, hlsed.CUE_STYLE_IN_OUT)
	
		try:
			playlist = hlsed.download_and_rebase(playlist_url, proxy_url)
		except Exception as e:
			return ("Could not download or parse the given playlist: %s." % (e), 400)
		
		if playlist.is_master_playlist:
			# Not much things to do for the master playlist yet.
			pass
		else:
			current_time = time.time()
			hlsed.event_to_vod(
				playlist, 
				event_duration = event_duration,
				ref_time = start_time, 
				current_time = current_time,
				program_date_time = True,
				logger = app.logger
			)
			if ad_interval > 0 and ad_duration > 0:
				hlsed.insert_ad_cues(
					playlist,
					event_duration = event_duration,
					ref_time = start_time, 
					current_time = current_time,
					time_between_ads = ad_interval,
					ad_duration = ad_duration, 
					style = ad_style,
					logger = app.logger
				)

	except Exception as e:
		app.logger.error("Error: %s" % (e))
		return ("Unable to proxy: %s." % (e), 400)
		
	text = playlist.text()
	if app.debug:
		app.logger.debug(text)
	response = make_response(text)
	response.mimetype = "application/x-mpegurl"
	response.headers["Cache-Control"] = "max-age=2"
	return response
