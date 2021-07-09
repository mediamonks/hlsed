# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

# This is to maintain a list of publically available HLS examples that can be easily referred to.

HLS = {
	"apple1": "https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_4x3/bipbop_4x3_variant.m3u8",
	"apple2": "https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_16x9/bipbop_16x9_variant.m3u8",
	"apple3": "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_ts/master.m3u8",
	"elephant": "https://cdn.theoplayer.com/video/elephants-dream/playlist.m3u8"
}

def resolve_hls(url_or_alias):	
	# We could check if url_or_alias is not a full URL first, but seems easier to look it up in our list instead.
	url = HLS.get(url_or_alias.lower())
	if url:
		return url
	else:
		return url_or_alias
