# This script reads trace output and shows latencies

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
tracepoint_pattern = re.compile(r'\s*([\w-]*)\s*(\[\d*\])\s*(.*)\s+(\d+\.\d+):\s*(\w*):\s*(.*)')

# Regexes for slowpath trace information
slowpath_begin_pattern = re.compile(r'gfp_mask:(\w*) order=(\d*)')
slowpath_end_pattern = re.compile(r'page=(\w*) pfn=(\d*)')

# Regexes for direct reclaim trace information
direct_reclaim_begin_pattern = re.compile(r'order=(\d*) may_writepage=[01] gfp_flags=(\w*)')
direct_reclaim_end_pattern = re.compile(r'nr_reclaimed=(\d*)')
shrink_zones_begin_pattern = re.compile(r'priority=(\d*) may_thrash=[01] may_writepage=[01]')
shrink_zones_end_pattern = re.compile(r'total_scanned=(\d*) nr_scanned=(\d*) nr_reclaimed=(\d*) nr_to_reclaim=(\d*) compaction_ready=[01]')
softlimit_reclaim_begin_pattern = re.compile(r'nid=(\d*) zid=(\d*) gfp_mask=(\w*)')
softlimit_reclaim_end_pattern = re.compile(r'nr_soft_reclaimed=(\d*) nr_reclaimed=(\d*) nr_soft_scanned=(\d*) nr_scanned=(\d*)')
shrink_zone_begin_patern = re.compile(r'nid=(\d*) zid=(\d*) is_classzone=(\w*)')
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

# Records the start time of a given event
def set_begin_time(process_info, EVENT, timestamp):
    add_process_key_if_needed(process_info)
    per_process_dict = all_information.get(process_info, None)
    per_process_dict[EVENT] = timestamp

# Calculates time elapsed from the start of the event to the end
def find_latency(process_info, BEGIN_EVENT, timestamp):
    per_process_dict = all_information.get(process_info, None)
    if per_process_dict:
        begin_timestamp = per_process_dict.get(BEGIN_EVENT, None)
        if begin_timestamp:
            time_elapsed = timestamp - begin_timestamp
            if time_elapsed > threshold:
                return (True, time_elapsed)
    return (False, 0.0)

def follow(thefile):
    while True:
        line = thefile.readline()
        if not line:
            continue
        yield line

logfile = open(source_path)
loglines = follow(logfile)

for line in loglines:
    matches = re.match(tracepoint_pattern, line)
    if matches:
        process_info = matches.group(1)
        timestamp = convert_time(matches.group(4))
        tracepoint_name = matches.group(5)
        
        if tracepoint_name == 'mm_slowpath_begin':
            set_begin_time(process_info, SLOWPATH_BEGIN, timestamp)

        elif tracepoint_name == 'mm_slowpath_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SLOWPATH_BEGIN, timestamp)
            if delay_status:
                print process_info + ' slowpath latency: ' + str(time_elapsed) 

        elif tracepoint_name == 'mm_vmscan_direct_reclaim_begin':
            set_begin_time(process_info, DIRECT_RECLAIM_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_direct_reclaim_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                DIRECT_RECLAIM_BEGIN, timestamp)
            if delay_status:
                print process_info + ' direct reclaim latency: ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_shrink_zones_begin':
            set_begin_time(process_info, SHRINK_ZONES_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_zones_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_ZONES_BEGIN, timestamp)
            if delay_status:
                print process_info + ' shrink zones latency: ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_softlimit_reclaim_start':
            set_begin_time(process_info, SOFTLIMIT_RECLAIM_START, timestamp)

    
        elif tracepoint_name == 'mm_vmscan_softlimit_reclaim_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SOFTLIMIT_RECLAIM_START,
                                                timestamp) 
            if delay_status:
                print process_info + ' softlimit reclaim latency: ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_begin':
            set_begin_time(process_info, SHRINK_ZONE_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_ZONE_BEGIN, timestamp)
            if delay_status:
                print process_info + ' shrink zone latency: ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_memcg_begin':
            set_begin_time(process_info, SHRINK_ZONE_MEMCG_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_zone_memcg_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_ZONE_MEMCG_BEGIN,
                                                timestamp)
            if delay_status:
                print process_info + ' shrink zone memcg latency ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_shrink_list_begin':
            set_begin_time(process_info, SHRINK_LIST_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_list_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_LIST_BEGIN, timestamp)
            if delay_status:
                print process_info + ' shrink list latency ' + str(time_elapsed)

        elif tracepoint_name == 'mm_vmscan_shrink_slab_caches_begin':
            set_begin_time(process_info, SHRINK_SLAB_CACHES_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_slab_caches_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_SLAB_CACHES_BEGIN,
                                                timestamp)
            if delay_status:
                print process_info + ' shrink slab caches latency ' + str(time_elapsed)
        
        elif tracepoint_name == 'mm_vmscan_shrink_slab_start':
            set_begin_time(process_info, SHRINK_SLAB_BEGIN, timestamp)

        elif tracepoint_name == 'mm_vmscan_shrink_slab_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                SHRINK_SLAB_BEGIN, timestamp)
            if delay_status:
                print process_info + ' shrink slab latency ' + str(time_elapsed)

        elif tracepoint_name == 'mm_compaction_try_to_compact_pages_begin':
            set_begin_time(process_info, COMPACTION_BEGIN, timestamp)

        elif tracepoint_name == 'mm_compaction_try_to_compact_pages_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                COMPACTION_BEGIN, timestamp)
            if delay_status:
                print process_info + ' compaction latency ' + str(time_elapsed)

        elif tracepoint_name == 'mm_compaction_zone_begin':
            set_begin_time(process_info, COMPACTION_ZONE_BEGIN, timestamp)

        elif tracepoint_name == 'mm_compaction_zone_end':
            delay_status, time_elapsed = find_latency(process_info,
                                                COMPACTION_ZONE_BEGIN,
                                                timestamp)
            if delay_status:
                print process_info + ' zone compaction latency ' + str(time_elapsed)
