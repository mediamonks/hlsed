# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import hlsed
import inspect
import m3u
import unittest
import urlparse

class MiscTestCase(unittest.TestCase):
	def test_1(self):
		self.assertEqual(
			hlsed.url_overriding_query_param("http://example.com/", "name", "value"),
			"http://example.com/?name=value"
		)
	def test_2(self):
		self.assertEqual(
			hlsed.url_overriding_query_param("http://example.com/?name=value", "name", "new-value"),
			"http://example.com/?name=new-value"
		)
	def test_3(self):
		self.assertEqual(
			hlsed.url_overriding_query_param(
				"http://example.com/?name=value&somethingelse=value2", 
				"name", "new-value"
			),
			"http://example.com/?name=new-value&somethingelse=value2"
		)

class EventToVODTestCase(unittest.TestCase):
	
	def setUp(self):
		self.playlist = m3u.Playlist(inspect.cleandoc(
			"""
			#EXTM3U
			#EXT-X-TARGETDURATION:5
			#EXT-X-VERSION:3
			#EXTINF:5,
			http://media.example.com/0.ts
			#EXTINF:10,
			http://media.example.com/1.ts
			#EXTINF:10,
			http://media.example.com/2.ts
			#EXTINF:10,
			http://media.example.com/3.ts
			#EXTINF:15,
			http://media.example.com/4.ts
			#EXT-X-ENDLIST
			"""
		))
		self.ref_time = 1234

	def toggle(self, current_time):
		hlsed.event_to_vod(
			self.playlist, 
			event_duration = 50,
			ref_time = self.ref_time,
			current_time = current_time
		)
		
	def test_0(self):
		# When the list is fetched initially, then it should be already going for at least 3 target durations.
		self.toggle(self.ref_time + 0)
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-TARGETDURATION:5
				#EXT-X-VERSION:3
				#EXT-X-PLAYLIST-TYPE:EVENT
				#EXTINF:5,
				http://media.example.com/0.ts
				#EXTINF:10,
				http://media.example.com/1.ts
				"""
			)
		)

	def test_5(self):
		self.toggle(self.ref_time + 5)
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-TARGETDURATION:5
				#EXT-X-VERSION:3
				#EXT-X-PLAYLIST-TYPE:EVENT
				#EXTINF:5,
				http://media.example.com/0.ts
				#EXTINF:10,
				http://media.example.com/1.ts
				"""
			)
		)

	def test_11(self):
		self.toggle(self.ref_time + 11)
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-TARGETDURATION:5
				#EXT-X-VERSION:3
				#EXT-X-PLAYLIST-TYPE:EVENT
				#EXTINF:5,
				http://media.example.com/0.ts
				#EXTINF:10,
				http://media.example.com/1.ts
				#EXTINF:10,
				http://media.example.com/2.ts
				"""
			)
		)

	def test_35(self):
		self.toggle(self.ref_time + 35)
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-TARGETDURATION:5
				#EXT-X-VERSION:3
				#EXT-X-PLAYLIST-TYPE:EVENT
				#EXTINF:5,
				http://media.example.com/0.ts
				#EXTINF:10,
				http://media.example.com/1.ts
				#EXTINF:10,
				http://media.example.com/2.ts
				#EXTINF:10,
				http://media.example.com/3.ts
				#EXTINF:15,
				http://media.example.com/4.ts
				"""
			)
		)

	def test_36(self):
		self.toggle(self.ref_time + 36)
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-TARGETDURATION:5
				#EXT-X-VERSION:3
				#EXT-X-PLAYLIST-TYPE:VOD
				#EXT-X-ENDLIST
				#EXTINF:5,
				http://media.example.com/0.ts
				#EXTINF:10,
				http://media.example.com/1.ts
				#EXTINF:10,
				http://media.example.com/2.ts
				#EXTINF:10,
				http://media.example.com/3.ts
				#EXTINF:15,
				http://media.example.com/4.ts
				"""
			)
		)

class DownloadAndRebaseTestCase(unittest.TestCase):
	
	def test_content_type(self):
		with self.assertRaisesRegexp(Exception, "content type"):
			hlsed.download_and_rebase("https://httpbin.org/html", "http://example.com/")

	def test_apple(self):
		playlist = hlsed.download_and_rebase(
			"https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_4x3/bipbop_4x3_variant.m3u8", 
			"http://monkapps.com:11000/hlsed?something=value"
		)
		self.assertGreater(len(playlist.uris), 0)
		for uri in playlist.uris:
			self.assertEqual(urlparse.urlparse(uri.uri).netloc, "monkapps.com:11000")

class RebaseTestCase(unittest.TestCase):
	
	def test_master(self):
		self.playlist = m3u.Playlist(inspect.cleandoc(
			"""
			#EXTM3U
			#EXT-X-STREAM-INF:BANDWIDTH=1280000,AVERAGE-BANDWIDTH=1000000
			http://example.com/low.m3u8
			#EXT-X-STREAM-INF:BANDWIDTH=2560000,AVERAGE-BANDWIDTH=2000000
			mid.m3u8
			"""
		))
		hlsed.rebase(
			self.playlist, 
			"https://another.example.com/playlist/index.m3u8", 
			"http://monkapps.com:11000/hlsed?something=value"
		)
		# Note that the first URI should remain absolute.
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=1000000,BANDWIDTH=1280000
				http://monkapps.com:11000/hlsed?something=value&url=http%3A%2F%2Fexample.com%2Flow.m3u8
				#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=2000000,BANDWIDTH=2560000
				http://monkapps.com:11000/hlsed?something=value&url=https%3A%2F%2Fanother.example.com%2Fplaylist%2Fmid.m3u8
				"""
			)
		)

	def test_media(self):
		self.playlist = m3u.Playlist(inspect.cleandoc(
			"""
			#EXTM3U
			#EXT-X-VERSION:3
			#EXT-X-TARGETDURATION:8
			#EXT-X-MEDIA-SEQUENCE:2680

			#EXTINF:7.975,
			fileSequence2680.ts
			#EXTINF:7.941,
			https://priv.example.com/fileSequence2681.ts
			"""
		))
		hlsed.rebase(
			self.playlist, 
			"https://another.example.com/playlist/index.m3u8", 
			"http://monkapps.com:11000/hlsed?something=value"
		)
		# No proxying for media playlists, only correcting relative URIs.
		self.assertEqual(
			self.playlist.text(),
			inspect.cleandoc(
				"""
				#EXTM3U
				#EXT-X-VERSION:3
				#EXT-X-TARGETDURATION:8
				#EXT-X-MEDIA-SEQUENCE:2680
				#EXTINF:7.975,
				https://another.example.com/playlist/fileSequence2680.ts
				#EXTINF:7.941,
				https://priv.example.com/fileSequence2681.ts
				"""
			)
		)

if __name__ == '__main__':
	unittest.main()
