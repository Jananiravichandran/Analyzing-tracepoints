# This script reads trace output and shows latencies
# Usage: python analyse_latencies.py -s /path/to/trace_pipe -t THRESHOLD

import argparse
import re

#constants for events
SLOWPATH_BEGIN              = 0

DIRECT_RECLAIM_BEGIN        = 1
SHRINK_ZONES_BEGIN          = 2
SOFTLIMIT_RECLAIM_START     = 3
SHRINK_ZONE_BEGIN           = 4
SHRINK_ZONE_MEMCG_BEGIN     = 5
SHRINK_LIST_BEGIN           = 6
SHRINK_SLAB_CACHES_BEGIN    = 7
SHRINK_SLAB_BEGIN           = 8

COMPACTION_BEGIN            = 9
COMPACTION_ZONE_BEGIN       = 10

# Parse command line arguments
parser = argparse.ArgumentParser(description='Parser for latency analyzer')

parser.add_argument('-s', '--source', action ='store', 
                    default='/sys/kernel/debug/tracing/trace_pipe',
                    dest='source_path',
                    help='Specify source file to read tracepoints from')
parser.add_argument('-t', '--threshold', action='store', default=0.0,
                    dest='threshold', type=float)
args = parser.parse_args()

source_path = args.source_path
threshold = args.threshold

# Regexes for tracepoints
tracepoint_pattern = re.compile(r'\s*([\w-]+)\s+(\[\d+\])\s+(.*)\s+(\d+\.\d+):\s+(\w+):\s+(.*)')

# Regexes for slowpath trace information
slowpath_begin_pattern = re.compile(r'gfp_mask:(\w*) order=(\d*)')
slowpath_end_pattern = re.compile(r'page=(\w*) pfn=(\d*)')

# Regexes for direct reclaim trace information
direct_reclaim_begin_pattern = re.compile(r'order=(\d*) may_writepage=([01]) gfp_flags=(\w*)')
direct_reclaim_end_pattern = re.compile(r'nr_reclaimed=(\d*)')
shrink_zones_begin_pattern = re.compile(r'priority=(\d*) may_thrash=([01]) may_writepage=([01])')
shrink_zones_end_pattern = re.compile(r'total_scanned=(\d*) nr_scanned=(\d*) nr_reclaimed=(\d*) nr_to_reclaim=(\d*) compaction_ready=([01])')
softlimit_reclaim_begin_pattern = re.compile(r'nid=(\d*) zid=(\d*) gfp_mask=(\w*)')
softlimit_reclaim_end_pattern = re.compile(r'nr_soft_reclaimed=(\d*) nr_reclaimed=(\d*) nr_soft_scanned=(\d*) nr_scanned=(\d*)')
shrink_zone_begin_pattern = re.compile(r'nid=(\d*) zid=(\d*) is_classzone=(\w*)')
shrink_zone_end_pattern = re.compile(r'nr_reclaimed=(\d*) nr_scanned=(\d*) reclaimable=(\w*)')
shrink_zone_memcg_begin_pattern = re.compile(r'zone_lru_pages=(\d*) nr_reclaimed=(\d*) nr_scanned=(\d*)')
shrink_zone_memcg_end_pattern = re.compile(r'lru_pages=(\d*) nr_reclaimed=(\d*) nr_scanned=(\d*)')
shrink_list_begin_pattern = re.compile(r'lru=(\d*) nr_to_scan=(\d*) nr_lru=(\d*)')
shrink_list_end_pattern = re.compile(r'nr_reclaimed=(\d*) nr_to_reclaim=(\d*) scan_adjusted=(\w*)')
shrink_slab_caches_begin_pattern = re.compile(r'nr_scanned=(\d*) nr_eligible=(\d*)')
shrink_slab_caches_end_pattern = re.compile(r'freed=(\d*)')
# TODO: add regexes for shrink_slab_start and shrink_slab_end

# Regexes for direct compact trace information 
compact_begin_pattern = re.compile(r'order=(\d*) gfp_mask=(\w*) mode=(\d*)')
compact_end_pattern = re.compile(r'rc=(\w*) contended=(\d*)')
compact_zone_begin_pattern = re.compile(r'nid=(\d*) zid=(\d*) zone_start=(\w*) migrate_pfn=(\w*) free_pfn=(\w*) zone_end=(\w*) mode=(\w*)')
compact_zone_end_pattern = re.compile(r'zone_start=(\w*) migrate_pfn=(\w*) free_pfn=(\w*) zone_end=(\w*), mode=(\w*) status=(\w*)')

# The dictionary which holds information from tracepoints for all the processes
all_information = {}

# Converts raw string time to milliseconds  
def convert_time(raw_time): 
    time_components = raw_time.split('.')
    return float(time_components[0]) * 1000 + float(time_components[1]) / 1000

# Ensures there is an entry in the dictionary for a given process
def add_process_key_if_needed(process):
    if process in all_information:
        return
    all_information[process] = {}
    all_information[process]["timestamps"] = {}
    all_information[process]["info"] = {}

# Records the start time of a given event
def set_begin_time(process_info, EVENT, timestamp):
    add_process_key_if_needed(process_info)
    per_process_data = all_information.get(process_info, None)
    per_process_time = per_process_data.get("timestamps", None)
    per_process_time[EVENT] = timestamp

# Calculates time elapsed from the start of the event to the end
def find_latency(process_info, BEGIN_EVENT, timestamp):
    per_process_data = all_information.get(process_info, None)
    if per_process_data:
        per_process_time = per_process_data.get("timestamps", None)
        if per_process_time:
            begin_timestamp = per_process_time.get(BEGIN_EVENT, None)
            if begin_timestamp:
                time_elapsed = timestamp - begin_timestamp
                time_elapsed = round(time_elapsed, 3)
                if time_elapsed > threshold:
                    return (True, time_elapsed)
    return (False, 0.0)

# Prints latency and begin info of events
def print_info(process_info, message, EVENT, time):
    print '\n' + process_info + ' : ' + message + ' : time = ' + str(time) + ' ms'
    begin_info = get_info_dict_for_event(process_info, EVENT)
    if begin_info:
        print 'start : ',
        for key, value in begin_info.iteritems():
            print key + ' = ' + value + ' ',
        print '\n',

# Returns information dictionary for a specific event
def get_info_dict_for_event(process_info, EVENT):
    process_info_dict = get_info_dict_for_process(process_info)
    if process_info_dict:
        dict_for_event = process_info_dict.get(EVENT, None)
        return dict_for_event
    return None

# Returns information dictionary for a process
def get_info_dict_for_process(process_info):
    process_data = all_information.get(process_info, None)
    if process_data:
        return process_data.get("info", None)
    return None

def follow(thefile):
    while True:
        line = thefile.readline()
        if not line:
            continue
        yield line

trace_file = open(source_path)
output_lines = follow(trace_file)

# TODO: 1. The if else here should be changed to an equivalent of switch case
#       2. Print information for shrink_slab
for line in output_lines:
    matches = re.match(tracepoint_pattern, line)
    if matches:
        process_info = matches.group(1)
        timestamp = convert_time(matches.group(4))
        tracepoint_name = matches.group(5)
        trace_info = matches.group(6)

        if tracepoint_name == 'mm_slowpath_begin':
            set_begin_time(process_info, SLOWPATH_BEGIN, timestamp)
            match_format = re.match(slowpath_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["gfp_mask"] = match_format.group(1)
                info_to_add["order"] = match_format.group(2)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SLOWPATH_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_slowpath_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SLOWPATH_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "slowpath", SLOWPATH_BEGIN,
                            time_elapsed)
                match_format = re.match(slowpath_end_pattern, trace_info)
                if match_format:
                    print trace_info
                    print match_format.group(1), match_format.group(2)
                    print 'end :  page = ' + match_format.group(1) + ' pfn = ' + match_format.group(2)

        elif tracepoint_name == 'mm_vmscan_direct_reclaim_begin':
            set_begin_time(process_info, DIRECT_RECLAIM_BEGIN, timestamp)
            match_format = re.match(direct_reclaim_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["order"] = match_format.group(1)
                info_to_add["gfp_flags"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[DIRECT_RECLAIM_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_direct_reclaim_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      DIRECT_RECLAIM_BEGIN,
                                                      time_elapsed)
            if delay_status:
                print_info(process_info, "direct reclaim", 
                            DIRECT_RECLAIM_BEGIN, timestamp)
                match_format = re.match(direct_reclaim_end_pattern, trace_info)
                if match_format:
                    print 'end : nr_reclaimed = ' + match_format.group(1)

        elif tracepoint_name == 'mm_vmscan_shrink_zones_begin':
            set_begin_time(process_info, SHRINK_ZONES_BEGIN, timestamp)
            match_format = re.match(shrink_zones_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["priority"] = match_format.group(1)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_ZONES_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_shrink_zones_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_ZONES_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "shrink zones",
                           SHRINK_ZONES_BEGIN, time_elapsed)
                match_format = re.match(shrink_zones_end_pattern, trace_info)
                if match_format:
                    print 'end : total_scanned = ' + match_format.group(1) + ' nr_scanned = ' + match_format.group(2) + ' nr_reclaimed = ' + match_format.group(3) + ' nr_to_reclaim = ' + match_format.group(4) + ' compaction_ready = ' + match_format.group(5)

        elif tracepoint_name == 'mm_vmscan_softlimit_reclaim_start':
            set_begin_time(process_info, SOFTLIMIT_RECLAIM_START, timestamp)
            match_format = re.match(softlimit_reclaim_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["nid"] = match_format.group(1)
                info_to_add["zid"] = match_format.group(2)
                info_to_add["is_classzone"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SOFTLIMIT_RECLAIM_START] = info_to_add

        elif tracepoint_name == 'mm_vmscan_softlimit_reclaim_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SOFTLIMIT_RECLAIM_START,
                                                      timestamp) 
            if delay_status:
                print_info(process_info, "softlimit reclaim",
                            SOFTLIMIT_RECLAIM_START, time_elapsed)
                match_format = re.match(softlimit_reclaim_end_pattern,
                                        trace_info)
                if match_format:
                    print 'end : nr_soft_reclaimed = ' + match_format.group(1) + ' nr_reclaimed = ' + match_format.group(2) + ' nr_soft_scanned = ' + match_format.group(3) + ' nr_scanned = ' + match_format.group(4)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_begin':
            set_begin_time(process_info, SHRINK_ZONE_BEGIN, timestamp)
            match_format = re.match(shrink_zone_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["nid"] = match_format.group(1)
                info_to_add["zid"] = match_format.group(2)
                info_to_add["is_classzone"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_ZONE_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_shrink_zone_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_ZONE_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "shrink zone",
                           SHRINK_ZONE_BEGIN, time_elapsed)
                match_format = re.match(shrink_zone_end_pattern, trace_info)
                if match_format:
                    print 'end : nr_reclaimed = ' + match_format.group(1) + ' nr_scanned = ' + match_format.group(2) + ' reclaimable = ' + match_format.group(3)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_memcg_begin':
            set_begin_time(process_info, SHRINK_ZONE_MEMCG_BEGIN, timestamp)
            match_format = re.match(shrink_zone_memcg_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["zone_lru_pages"] = match_format.group(1)
                info_to_add["nr_reclaimed"] = match_format.group(2)
                info_to_add["nr_scanned"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_ZONE_MEMCG_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_shrink_zone_memcg_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_ZONE_MEMCG_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "shrink zone memcg",
                           SHRINK_ZONE_MEMCG_BEGIN, time_elapsed)
                match_format = re.match(shrink_zone_memcg_end_pattern,
                                        trace_info)
                if match_format:
                    print 'end : lru_pages = ' + match_format.group(1) + ' nr_reclaimed = ' + match_format.group(2) + ' nr_scanned = ' + match_format.group(3)
                
        elif tracepoint_name == 'mm_vmscan_shrink_list_begin':
            set_begin_time(process_info, SHRINK_LIST_BEGIN, timestamp)
            match_format = re.match(shrink_list_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["lru"] = match_format.group(1)
                info_to_add["nr_to_scan"] = match_format.group(2)
                info_to_add["nr_lru"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_LIST_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_shrink_list_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_LIST_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "shrink list", 
                           SHRINK_LIST_BEGIN, time_elapsed)
                match_format = re.match(shrink_list_end_pattern, trace_info)
                if match_format:
                    print 'end : nr_reclaimed = ' + match_format.group(1) + ' nr_to_reclaim = ' + match_format.group(2) + ' scan_adjusted = ' + match_format.group(3)

        elif tracepoint_name == 'mm_vmscan_shrink_slab_caches_begin':
            set_begin_time(process_info, SHRINK_SLAB_CACHES_BEGIN, timestamp)
            match_format = re.match(shrink_slab_caches_begin_pattern,
                                    trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["nr_scanned"] = match_format.group(1)
                info_to_add["nr_eligible"] = match_format.group(2)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_SLAB_CACHES_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_vmscan_shrink_slab_caches_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_SLAB_CACHES_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "shrink slab caches",
                           SHRINK_SLAB_CACHES_BEGIN, time_elapsed)
                match_format = re.match(shrink_slab_caches_end_pattern,
                                        trace_info)
                if match_format:
                    print 'end : freed = ' + match_format.group(1)
        
        elif tracepoint_name == 'mm_vmscan_shrink_slab_start':
            set_begin_time(process_info, SHRINK_SLAB_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_slab_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_SLAB_BEGIN,
                                                      timestamp)
            if delay_status:
                print process_info + ' shrink slab latency ' + str(time_elapsed)

        elif tracepoint_name == 'mm_compaction_try_to_compact_pages_begin':
            set_begin_time(process_info, COMPACTION_BEGIN, timestamp)
            match_format = re.match(compact_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["order"] = match_format.group(1)
                info_to_add["gfp_mask"] = match_format.group(2)
                info_to_add["mode"] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[COMPACTION_BEGIN] = info_to_add

        elif tracepoint_name == 'mm_compaction_try_to_compact_pages_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      COMPACTION_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "compaction", COMPACTION_BEGIN,
                           time_elapsed)
                match_format = re.match(compact_end_pattern, trace_info)
                if match_format:
                    print 'end : rc = ' + match_format.group(1) + ' contended = ' + match_format.group(2)

        elif tracepoint_name == 'mm_compaction_zone_begin':
            set_begin_time(process_info, COMPACTION_ZONE_BEGIN, timestamp)
            match_format = re.match(compact_zone_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add["nid"] = match_format.group(1)
                info_to_add["zid"] = match_format.group(2)
                info_to_add["zone_start"] = match_format.group(3)
                info_to_add["migrate_pfn"] = match_format.group(4)
                info_to_add["free_pfn"] = match_format.group(5)
                info_to_add["zone_end"] = match_format.group(6)
                info_to_add["mode"] = match_format.group(7)

        elif tracepoint_name == 'mm_compaction_zone_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                      COMPACTION_ZONE_BEGIN,
                                                      timestamp)
            if delay_status:
                print_info(process_info, "zone compaction",
                           COMPACTION_ZONE_BEGIN, time_elapsed)
                match_format = re.match(compact_zone_end_pattern, trace_info)
                if match_format:
                    print 'end : mode = ' + match_format.group(5) + ' status = ' + match_format.group(6)
