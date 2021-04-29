# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import re

class Playlist:
	"""
	Basic M3U playlist wrapper, see https://tools.ietf.org/html/rfc8216.
	
	Something that is enough to do basic modifications in existing valid playlists, 
	there is no goal to support validation or advanced parsing of attributes.
	
	The object exposes 2 main fields:
	
	- globals: A list of 'Tag' objects corresponding to all global and standalone tags.
	
	- uris: A list of 'URI' objects corresponding to all URIs, each with a list of non-global tags 
	  associated with it.
	
	The changes in the above lists would be taken into account when the playlist is re-assembled 
	via text() method.	
	"""
		
	def __init__(self, text):
		
		"""
		Initialized a new playlist by parsing the text of the existing one.
		The parsed content can be accessed and modified via 'globals' and 'uris' fields.
		"""
				
		self.globals = []
		self.uris = []

		# Tags that are applied to the next URI only.
		next_uri_tags = []
		# Tags that are applied to the next and following URIs till another occurrence of the same tag.
		next_occurrence_tags = {}
		
		# See https://tools.ietf.org/html/rfc8216#section-4.1 on the general structure.
		lines = re.split(r'\r?\n', text)
		for line_number, line in enumerate(lines):
			
			# There should not be any leading/trailing spaces, but let's strip in case it was manually edited.
			line = line.strip()
			
			# The playlist is a sequence of lines where each can be a comment, a tag comment, or a URI.

			# Ignoring the empty lines.
			if len(line) == 0:
				continue
				
			# Anything starting with a hash is either a comment or a tag.
			if line.startswith('#'):
				
				# A tag must start with #EXT or that's a comment that we just skip.
				if not line.startswith('#EXT'):
					continue
								
				tag = Tag(line)
				
				info = _TagInfo.get(tag.name)
				
				if info.applicability == _TagInfo.GLOBAL:
					self.globals.append(tag)
				elif info.applicability == _TagInfo.NEXT_OCCURRENCE:
					next_occurrence_tags[tag.name] = tag
					next_uri_tags.append(tag)
				elif info.applicability == _TagInfo.NEXT_URI:
					next_uri_tags.append(tag)
				else:
					assert(False)
			else:
				# Anything else must be a URI.
				self.uris.append(URI(line, next_uri_tags))
				# Keeping the tags that work till their next occurrence for the next URI.
				next_uri_tags = next_occurrence_tags.values()
		
		if len(self.globals) == 0 or self.globals[0].name != 'EXTM3U':
			raise ParsingError("Missing the EXTM3U tag")
		
		# Let's figure out if this is a Master or a Media Playlist.
		is_master = False
		is_media = False
		for tag in self.all_tags():
			info = _TagInfo.get(tag.name)
			if info.playlist == _TagInfo.MEDIA_ONLY:
				is_media = True
			elif info.playlist == _TagInfo.MASTER_ONLY:
				is_master = True

		if is_media and is_master or not (is_media or is_master):
			raise ParsingError("The playlist does not seem to be a master or media playlist")

		# I don't want to introduce a pseudo-enum here, a boolean should be OK.
		self.is_master_playlist = is_master

	def global_tag_by_name(self, name):
		for t in self.globals:
			if t.name == name:
				return t
		return None
		
	def remove_global_tag(self, name):
		self.globals = filter(lambda t: t.name != name, self.globals)
		
	def playlist_type(self):
		"""
		The value of EXT-X-PLAYLIST-TYPE tag, if there is one; '' otherwise.
		See https://tools.ietf.org/html/rfc8216#section-4.3.3.5
		"""
		tag = self.global_tag_by_name('EXT-X-PLAYLIST-TYPE')
		if tag:
			return tag.values[0]
		else:
			return ''
			
	def target_duration(self):
		"""The target segment duration in seconds from EXT-X-TARGETDURATION tag, if there is one; 0 otherwise."""
		tag = self.global_tag_by_name('EXT-X-TARGETDURATION')
		if tag:
			return float(tag.values[0])
		return 0		
			
	def items(self):
		"""
		The list of all tags and URIs (Tag and URI objects).
		The changes in this list per se DO NOT affect the playlist, but changes in its elements do.
		"""
		result = []
		result += self.globals
		for u in self.uris:
			# TODO: skip repeating tags that work for their next occurrence
			result += u.tags
			result.append(u)
		return result
	
	def all_tags(self):
		"""
		A list of tags only, both global and URI-specific, in the order they would appear in the saved playlist.
		The changes in this list per se DO NOT affect the playlist, but changes in its elements do.
		"""
		return filter(lambda x: isinstance(x, Tag), self.items())
	
	def text(self):
		"""A textual representation of this (possibly modified) playlist ready to be saved to a file."""
		return "\n".join(map(lambda item: item.text(), self.items())).encode('utf_8')
		
	def save(self, path):
		"""A convenience saving this (possibly modified) playlist to a file."""
		with open(path, 'wb') as f:
			f.write(self.text())
				
class ParsingError(Exception):
	pass

class _TagInfo:	
	"""
	We need to store a bit of info about each tag type supported in order to:
	- distinguish master and media playlists,
	- know how the value of each tag might look,
	- and which tag applies to an URI and which to the whole file. 
	
	This class serves as such a meta info store.
	"""
	
	class Info:	
		def __init__(self, name, applicability, playlist, value):
			self.name = name
			self.applicability = applicability
			self.playlist = playlist
			self.value = value
		
	# (Not using enums so it works with older Pythons.)

	# Possible values for Info.applicability.

	# The tag applies to the whole file.
	GLOBAL = 0	
	# The tag applies only to the next media segment or playlist URI.
	NEXT_URI = 1
	# The tag applies to all URIs following till the next occurrence of the same tag.
	NEXT_OCCURRENCE = 2

	# Possible values for Info.playlist.

	# The tag can appear in any playlist type.
	MASTER_AND_MEDIA = 0
	# The tag can appear only in the master playlist.
	MASTER_ONLY = 1
	# The tag can appear only in the media playlist.
	MEDIA_ONLY = 2

	# Possible values for Info.value.
	
	# The tag has a list of comma-separated attribute/value pairs.
	ATTR_LIST = 3
	# The tag has a list of comma-separated values.
	VALUE_LIST = 2
	SINGLE_VALUE = 1
	NO_VALUE = 0

	_known_tags = [
		# Basic Tags: https://tools.ietf.org/html/rfc8216#section-4.3.1
		Info('EXTM3U',							GLOBAL,				MASTER_AND_MEDIA,	NO_VALUE),
		Info('EXT-X-VERSION',					GLOBAL,				MASTER_AND_MEDIA,	SINGLE_VALUE),
		
		# Media Segment Tags: https://tools.ietf.org/html/rfc8216#section-4.3.2
		Info('EXTINF',							NEXT_URI,			MEDIA_ONLY,			VALUE_LIST),
		Info('EXT-X-BYTERANGE', 				NEXT_URI,			MEDIA_ONLY,			SINGLE_VALUE),
		Info('EXT-X-DISCONTINUITY', 			NEXT_URI, 			MEDIA_ONLY,			NO_VALUE),
		Info('EXT-X-KEY', 						NEXT_OCCURRENCE,	MEDIA_ONLY,			ATTR_LIST),
		Info('EXT-X-MAP', 						NEXT_OCCURRENCE,	MEDIA_ONLY,			ATTR_LIST),
		Info('EXT-X-PROGRAM-DATE-TIME', 		NEXT_URI,			MEDIA_ONLY,			SINGLE_VALUE),		
		Info('EXT-X-DATERANGE', 				GLOBAL,				MEDIA_ONLY,			ATTR_LIST),
		
		# Media Playlist Tags: https://tools.ietf.org/html/rfc8216#section-4.3.3
		Info('EXT-X-TARGETDURATION', 			GLOBAL,				MEDIA_ONLY,			SINGLE_VALUE),
		Info('EXT-X-MEDIA-SEQUENCE', 			GLOBAL,				MEDIA_ONLY,			SINGLE_VALUE),
		Info('EXT-X-DISCONTINUITY-SEQUENCE',	NEXT_OCCURRENCE,	MEDIA_ONLY,			SINGLE_VALUE),
		Info('EXT-X-ENDLIST', 					GLOBAL,				MEDIA_ONLY,			NO_VALUE),
		Info('EXT-X-PLAYLIST-TYPE',				GLOBAL,				MEDIA_ONLY,			SINGLE_VALUE),
		Info('EXT-X-I-FRAMES-ONLY', 			GLOBAL,				MEDIA_ONLY,			NO_VALUE),
		
		# Master Playlist Tags: https://tools.ietf.org/html/rfc8216#section-4.3.4
		Info('EXT-X-MEDIA', 					GLOBAL,				MASTER_ONLY,		ATTR_LIST),
		Info('EXT-X-STREAM-INF', 				NEXT_URI,			MASTER_ONLY,		ATTR_LIST),
		Info('EXT-X-I-FRAME-STREAM-INF', 		GLOBAL,				MASTER_ONLY,		ATTR_LIST),
		Info('EXT-X-SESSION-DATA', 				GLOBAL,				MASTER_ONLY,		ATTR_LIST),
		Info('EXT-X-SESSION-KEY', 				GLOBAL,				MASTER_ONLY,		ATTR_LIST),
		
		# Media or Master Playlist Tags: https://tools.ietf.org/html/rfc8216#section-4.3.5
		Info('EXT-X-INDEPENDENT-SEGMENTS', 		GLOBAL,				MASTER_AND_MEDIA,	NO_VALUE),
		Info('EXT-X-START', 					GLOBAL,				MASTER_AND_MEDIA,	ATTR_LIST),
		
		# New RFC tags, see https://tools.ietf.org/html/draft-pantos-hls-rfc8216bis-08.		
		Info('EXT-X-GAP', 						NEXT_URI,			MEDIA_ONLY,			NO_VALUE),		
		Info('EXT-X-BITRATE', 					NEXT_OCCURRENCE,	MEDIA_ONLY,			SINGLE_VALUE),
		# TODO: This ones does not seem to fit our parsing model, check.
		Info('EXT-X-PART', 						NEXT_OCCURRENCE,	MEDIA_ONLY,			ATTR_LIST),	
		# Seems like something outdated?
		Info('EXT-X-ALLOWCACHE', 				GLOBAL,				MEDIA_ONLY,			SINGLE_VALUE)		
	]
	_known_tags_by_name = dict(map(lambda t: (t.name, t), _known_tags))
	
	@classmethod
	def get(cls, name):			
		info = cls._known_tags_by_name.get(name)
		# Note that the spec tells that unknown tags should be ignored when parsing but that would make 
		# no sense in our case, so let's flag unknown tags as soon as possible.
		if not info:
			raise ParsingError("Unknown tag: '%s'" % (name,))
		return info
	
class URI:
	"""
	A single URI from an M3U playlist along with all tags applicable to this URI, 
	i.e. excluding the global/standalone tags.
	"""
	
	def __init__(self, uri, tags):
		self.uri = uri
		self.tags = tags
		
	def __str__(self):
		return "URI: '%s', tags: %s" % (self.uri, self.tags)
		
	def tag_by_name(self, name):
		for t in self.tags:
			if t.name == name:
				return t
		return None
		
	def duration(self):
		"""A floating-point duration of a media segment URI from its EXTINF tag; 0 if not applicable."""
		extinf = self.tag_by_name('EXTINF')
		if not extinf:
			return 0
		return float(extinf.values[0])

	def text(self):
		return self.uri
		
	def remove_tag(self, name):
		"""Removes all tags with the given name from this URI."""
		self.tags = filter(lambda t: t.name != name, self.tags)

class Tag:
	
	"""
	A single tag from an M3U playlist.
	
	Depending on the type of the tag the values are available for modifications either 
	via 'attributes' dictionary, 'values' list or not available at all.
	"""
		
	def __init__(self, raw):
		
		self.raw = raw
		
		m = re.match(r'#(?P<name>EXT[A-Z0-9-]+)(\:(?P<value>.+))?$', raw)
		if not m:
			raise ParsingError("Invalid tag")
			
		self.name = m.group('name')
		
		value = m.group('value') 
		if not value:
			value = ''
			
		self.values = None
		self.attributes = None			
		
		self.value_type = _TagInfo.get(self.name).value
		
		if self.value_type == _TagInfo.NO_VALUE:			
			
			if len(value):
				raise ParsingError("Unexpected a value for tag '%s'" % (self.name,))
				
		elif self.value_type == _TagInfo.SINGLE_VALUE or self.value_type == _TagInfo.VALUE_LIST:
						
			# We are treating single values as lists of one element because they don't have commas 
			# and because we don't have to be strict.
			if len(value) == 0:
				raise ParsingError("Expected at least one value for tag '%s'" % (self.name,))
			self.values = value.split(',')
			
		elif self.value_type == _TagInfo.ATTR_LIST:
			
			self.attributes = {}
			pos = 0
			while pos < len(value):

				m = Tag._pair_re.match(value, pos)
				if not m:
					raise ParsingError("Invalid attribute list in '%s' (%d): '%s'" % (self.name, pos, value))

				name = m.group('name')
				if name in self.attributes:
					raise ParsingError("Duplicate attribute in '%s'" % (self.name,))
				
				if m.group('number'):
					self.attributes[name] = Tag.NumberValue(m.group('number'))
				elif m.group('hex'):
					self.attributes[name] = Tag.HexValue(m.group('hex'))
				elif m.group('string'):
					self.attributes[name] = Tag.StringValue(m.group('string'))
				elif m.group('enum'):
					self.attributes[name] = Tag.EnumValue(m.group('enum'))
				elif m.group('resolution'):
					self.attributes[name] = Tag.ResolutionValue(m.group('width'), m.group('height'))
				else:
					assert(False)
				
				pos = m.end()
			
		else:
			assert(False)
			
	# A regexp for name/value attributes, see https://tools.ietf.org/html/rfc8216#section-4.2.
	# Note that we cannot simply split on commas because there might be commas in quoted strings.
	# We could simplify by dividing values into strings and everything else, but it should not hurt 
	# to validate the format.
	_pair_re = re.compile(r"""
		(?P<name>[A-Z0-9-]+)
		=
		(?P<value>
			# decimal-integer, decimal-floating-point, or signed-decimal-floating-point.
			(?P<number>-?[0-9]+(\.[0-9]+)?) |
			# hexadecimal-sequence.
			(0[xX](?P<hex>[0-9A-F]+)) |
			# quoted-string.
			("(?P<string>[^"]*)") |
			# enumerated-string.
			(?P<enum>[A-Z0-9-]+) |
			# decimal-resolution.
			(?P<resolution>(?P<width>[0-9]+)x(?P<height>[0-9]+))
		)
		(,|$)
		""", 
		re.X
	)
	
	###			
			
	class Value:
		def __str__(self):
			return self.text()
	
	class NumberValue(Value):
		def __init__(self, raw):
			self.value = float(raw)
		def text(self):
			return "%.20g" % self.value
			
	class HexValue(Value):
		def __init__(self, raw):
			self.value = raw
		def text(self):
			return "0x%s" % str(self.value)
	
	class StringValue(Value):
		def __init__(self, raw):
			self.value = raw
		def text(self):
			return "\"%s\"" % self.value
			
	class EnumValue(Value):
		def __init__(self, raw):
			self.value = raw
		def text(self):
			return "%s" % self.value.upper()
	
	class ResolutionValue(Value):
		def __init__(self, width, height):
			self.width = int(width)
			self.height = int(height)
		def text(self):
			return "%dx%d" % (self.width, self.height)
				
	###
			
	def __str__(self):
		return "Tag '%s'" % (self.name)

	def _raw_value(self):
				
		if self.value_type == _TagInfo.NO_VALUE:
			return ""
		elif self.value_type == _TagInfo.SINGLE_VALUE or self.value_type == _TagInfo.VALUE_LIST:
			return ":" + ",".join(self.values)
		elif self.value_type == _TagInfo.ATTR_LIST:
			
			def value_text(v):
				if isinstance(v, Tag.Value):
					return v.text()
				else:
					return Tag.StringValue(v).text()

			string_pairs = map(
				lambda p: "%s=%s" % (p[0], value_text(p[1])), 
				sorted(self.attributes.items(), key = lambda x: x[0])
			)

			return ":" + ",".join(string_pairs)
		else:
			assert(False)
		
	def text(self):
		return "#%s%s" % (self.name, self._raw_value())
