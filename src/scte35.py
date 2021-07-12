# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import binascii
import struct

def splice_info_with_splice_insert(
	event_id, 
	out_of_network_indicator, 
	pts_time_seconds, 
	break_duration_seconds = None, 
	auto_return = False,
	unique_program_id = 0xa1e, 
	avail_num = 0, 
	avails_expected = 0,
	pts_adjustment_seconds = 0
):
	"""
	splice_insert() command wrapped into splice_info() and hex-encoded.
	"""
	command_type, command = _splice_insert(
		event_id, 
		out_of_network_indicator, 
		pts_time_seconds,
		break_duration_seconds,
		auto_return,
		unique_program_id,
		avail_num,
		avails_expected
	)
	return _splice_info_section(command_type, command, pts_adjustment_seconds)

def splice_insert(
	event_id,
	out_of_network_indicator,
	pts_time_seconds,	
	break_duration_seconds = None,
	auto_return = False,
	unique_program_id = 0xa1e,
	avail_num = 0,
	avails_expected = 0
):
	"""
	splice_insert() command, hex-encoded.
	"""
	command_type, command = _splice_insert(
		event_id,
		out_of_network_indicator,
		pts_time_seconds,
		break_duration_seconds,
		auto_return,
		unique_program_id,
		avail_num,
		avails_expected
	)
	return binascii.hexlify(command).upper()

def _splice_info_section(splice_command_type, splice_command, pts_adjustment_seconds):
	
	"""
	Wraps the binary splice_command of type splice_command_type as splice_info() 
	and returns it hex-encoded.
	"""
	
	# 1 when the packet is encrypeted. We don't use this.
	encrypted_packet = 0 # 1 bit.
	encryption_algorithm = 0 # 6 bits.
	# The offset to add to all 'pts_time' fields.
	pts_adjustment = int(pts_adjustment_seconds * 90000) # 33 bits.
	
	# The index of the key ("control word") for encrypted packets. Not used here.
	cw_index = 0 # 8 bits.
	# Can be between 0 and 0xFFF, the latter is ignored.
	tier = 0xFFF # 12 bits.
	# Note that splice_command_type is excluded.
	splice_command_length = len(splice_command) # 12 bits.

	descriptor_loop_length = 0 # 16 bits
	
	body = struct.pack(	
		">BBLBBHB",
		0x00, # protocol_version
		(encrypted_packet << 7) | (encryption_algorithm << 1) | ((pts_adjustment >> 32) & 1),
		pts_adjustment & 0xFFFFFFFF,
		cw_index,
		tier >> 4, 
		((tier << 12) & 0xF000) | splice_command_length,
		splice_command_type
	) 
	body += splice_command 
	body += struct.pack(">H", descriptor_loop_length)

	# The number of remaining bytes following section_length.
	section_length = len(body) # 12 bits
		
	header = struct.pack(
		">BH", 
		0xFC, # table_id
		# Note that section_syntax_indicator, private_indicator and reserved take 4 bits and are all 0.
		section_length
	)
		
	splice_info_section = header + body
	
	# We don't have to align things when encryption is not used.
	#~ encrypted_len = 1 + len(splice_command) + 2
	#~ padding = ((encrypted_len + 7) & 0xFFF8) - encrypted_len
	#~ splice_info_section += '\xaa' * padding
	
	crc32 = struct.pack(">l", binascii.crc32(splice_info_section))

	return binascii.hexlify(splice_info_section + crc32).upper()

def _flag_and_time(flag, pts_time_seconds):
	pts_time = int(pts_time_seconds * 90000)
	return struct.pack(
		">BL", 
		(flag << 7) | (pts_time >> 32), # flag | 6 reserved | the MSB bit of pts_time.
		pts_time & 0xFFFFFFFF
	)

def splice_time(pts_time_seconds):
	return _flag_and_time(1, pts_time_seconds)

def break_duration(pts_time_seconds, auto_return = False):
	if auto_return:
		return _flag_and_time(1, pts_time_seconds)
	else:
		return _flag_and_time(0, pts_time_seconds)

def _splice_insert(
	event_id,
	out_of_network_indicator,
	pts_time_seconds,
	break_duration_seconds,
	auto_return,
	unique_program_id,
	avail_num,
	avails_expected
):
	splice_event_cancel_indicator = 0 # 1 bit.
	
	# Want to allow using booleans for this one.
	if out_of_network_indicator:
		_out_of_network_indicator = 1 # 1 bit.
	else:
		_out_of_network_indicator = 0 # 1 bit.

	# When 1, then "all PIDs/components of the program are to be spliced". 
	# We're not interested in "Component Splice Mode".
	program_splice_flag = 1 # 1 bit.
	
	# 1 if break duration is specified.
	if break_duration_seconds is not None:
		duration_flag = 1 # 1 bit.
	else:
		duration_flag = 0 # 1 bit.

	# 1 when no time is provided, but the splice should happen asap. We are not interested in that.
	splice_immediate_flag = 0 # 1 bit.
	
	r = struct.pack(
		">LB", 
		event_id, # 32 bit
		((splice_event_cancel_indicator & 0x01) << 7) # 7 bits reserved.
	)
	if splice_event_cancel_indicator == 0:
		
		r += struct.pack(
			">B",
			(_out_of_network_indicator << 7) | (program_splice_flag << 6) | (duration_flag << 5) | (splice_immediate_flag << 4) # 4 bits reserved.
		)
		
		# We support only one mode here.
		assert(program_splice_flag == 1 and splice_immediate_flag == 0)
		r += splice_time(pts_time_seconds)
		
		if duration_flag == 1:
			r += break_duration(break_duration_seconds, auto_return)
		
		r += struct.pack(
			">HBB",
			unique_program_id,
			avail_num,
			avails_expected
		)
		
	return 0x05, r
