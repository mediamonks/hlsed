# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import inspect
import m3u
import unittest

class TagTestCase(unittest.TestCase):
	
	def test_no_value(self):
		t = m3u.Tag('#EXT-X-ENDLIST')
		self.assertIsNone(t.values)
		self.assertIsNone(t.attributes)
	
	def test_single_value(self):
		t = m3u.Tag('#EXT-X-PLAYLIST-TYPE:VOD')
		self.assertEqual(t.values, ['VOD'])
		self.assertIsNone(t.attributes)
		
	def test_two_values(self):
		t = m3u.Tag('#EXTINF:10.5,')
		self.assertEqual(t.values, ['10.5', ''])
		self.assertIsNone(t.attributes)
		t = m3u.Tag('#EXTINF:10.5,Title?')
		self.assertEqual(t.values, ['10.5', 'Title?'])
		self.assertIsNone(t.attributes)
		
	def test_attributes(self):
		t = m3u.Tag('#EXT-X-MEDIA:TYPE=AUDIO,DEFAULT=YES,AUTOSELECT=YES,LANGUAGE="en",URI="main,audio.m3u8"')
		self.assertIsNone(t.values)
		self.assertEqual(t.attributes['TYPE'].value, 'AUDIO')
		self.assertEqual(t.attributes['DEFAULT'].value, 'YES')
		self.assertEqual(t.attributes['AUTOSELECT'].value, 'YES')
		self.assertEqual(t.attributes['LANGUAGE'].value, 'en')
		self.assertEqual(t.attributes['URI'].value, 'main,audio.m3u8')
		t.attributes['URI'].value = 'another.m3u8'
		self.assertEqual(t.text(),'#EXT-X-MEDIA:AUTOSELECT=YES,DEFAULT=YES,LANGUAGE="en",TYPE=AUDIO,URI="another.m3u8"')
		
class PlaylistTestCase(unittest.TestCase):

	def test_unknown_tag(self):
		with self.assertRaisesRegexp(m3u.ParsingError, "Unknown tag"):
			l = m3u.Playlist(inspect.cleandoc("""
				#EXTM3U
				#EXT-X-SOMETHING:3
		   		"""
			))
		with self.assertRaisesRegexp(m3u.ParsingError, "does not seem to be a master or media playlist"):
			l = m3u.Playlist(inspect.cleandoc("""
				#EXTM3U
				#EXT-X-TARGETDURATION:10
				#EXT-X-STREAM-INF:BANDWIDTH=1280000,AVERAGE-BANDWIDTH=1000000
				http://example.com/low.m3u8
		   		"""
			))

	def test_example_8_1(self):
		l = m3u.Playlist(inspect.cleandoc("""
			#EXTM3U
			#EXT-X-TARGETDURATION:10
			#EXT-X-VERSION:3
			#EXTINF:9.009,
			http://media.example.com/first.ts
			#EXTINF:9.009,
			http://media.example.com/second.ts
			#EXTINF:3.003,
			http://media.example.com/third.ts
			#EXT-X-ENDLIST
	   		"""
		))
		self.assertFalse(l.is_master_playlist)
		self.assertEqual(len(l.globals), 4)
		self.assertEqual(len(l.uris), 3)
		
		self.assertEqual(l.target_duration(), 10)		
	
		del l.uris[0]
		l.uris[0].uri = "edited.ts"
		self.assertEqual(l.uris[0].duration(), 9.009)
		self.assertEqual(l.uris[1].duration(), 3.003)
		
		l.remove_global_tag('EXT-X-ENDLIST')
			
		# Note that the 'EXT-X-ENDLIST' has changed order, but it's fine, it's a global one.
		self.assertEqual(l.text(), inspect.cleandoc("""
			#EXTM3U
			#EXT-X-TARGETDURATION:10
			#EXT-X-VERSION:3
			#EXTINF:9.009,
			edited.ts
			#EXTINF:3.003,
			http://media.example.com/third.ts
	   		"""
		))
	
	def test_example_8_4(self):
		# https://tools.ietf.org/html/rfc8216#section-8.4
		l = m3u.Playlist(inspect.cleandoc("""
		   #EXTM3U
		   #EXT-X-STREAM-INF:BANDWIDTH=1280000,AVERAGE-BANDWIDTH=1000000
		   http://example.com/low.m3u8
		   #EXT-X-STREAM-INF:BANDWIDTH=2560000,AVERAGE-BANDWIDTH=2000000
		   http://example.com/mid.m3u8
		   #EXT-X-STREAM-INF:BANDWIDTH=7680000,AVERAGE-BANDWIDTH=6000000
		   http://example.com/hi.m3u8
		   #EXT-X-STREAM-INF:BANDWIDTH=65000,CODECS="mp4a.40.5"
		   http://example.com/audio-only.m3u8
		   """
		))
		self.assertTrue(l.is_master_playlist)
		self.assertEqual(len(l.globals), 1)
		self.assertEqual(len(l.uris), 4)

if __name__ == '__main__':
	unittest.main()
