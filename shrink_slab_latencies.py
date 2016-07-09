#!/usr/bin/env python
# Python 2.7
# This script shows latencies in direct reclaim and slab shrinkers.
# The input is from trace_pipe.
# Usage: ./shrink_slab_latencies.py -s PATH/TO/TRACE_PIPE -t THRESHOLD_IN_MS.
# Total time spent in each shrinker is shown when CTRL+C is presed.

import signal
import argparse
import re
import sys
from collections import defaultdict

# Constants for events
DIRECT_RECLAIM_BEGIN     = 0
SHRINK_SLAB_BEGIN        = 1

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--source', action='store',
                    default='/sys/kernel/debug/tracing/trace_pipe',
                    dest='source_path', help='source file')
parser.add_argument('-t', '--threshold', action='store', default=0.0,
                    dest='threshold', type=float)
args = parser.parse_args()

source_path = args.source_path
threshold = args.threshold

#) Regex for tracepoints
tracepoint_pattern = re.compile(r'\s*([\w-]+)\s+(\[\d+\])\s+(.*)\s+(\d+\.\d+):'
                                '\s+(\w+):\s+(.*)')

# Regexes for direct reclaim
direct_reclaim_begin_pattern = re.compile(r'\s*order=(\d*) may_writepage=([01])'
                                          ' gfp_flags=(.*)')
direct_reclaim_end_pattern = re.compile(r'\s*nr_reclaimed=(\d*)')

# Regexes for shrinking slabs
shrink_slab_begin_pattern = re.compile(r'\s*name:\s*(\w*) (.*) (\w*): nid: (\d*)'
                                       ' objects to shrink (\d*) gfp_flags'
                                       ' (.*) pgs_scanned (\d*) lru_pgs (\d*)'
                                       ' cache items (\d*) delta (\d*)'
                                       ' total_scan (\d*)')
shrink_slab_end_pattern = re.compile(r'\s*name:\s*(\w*) (.*) (\w*): nid: (\d*)'
                                     ' unused scan count (\d*) new scan count'
                                     ' (\d*) total_scan (\d*) last shrinker'
                                     ' return val (\d*)')

# The dictionary holding trace information for all the processes read
all_information = {}

# This dictionary holds all the shrinker latencies
shrinker_latencies = defaultdict(float)


# Print shrinker latencies when CTRL+C is pressed
def print_shrinker_latencies(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)
    total_time = 0.0
    print '\n'
    for key, value in shrinker_latencies.iteritems():
        print '%s : %s ms' %(key, value)
        total_time += value
    total_time = total_time
    print '\ntotal time spent in shrinkers = %.3f ms' %(total_time)
    sys.exit(1)


original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, print_shrinker_latencies)


# Converts raw string time to milliseconds
def convert_time(raw_time):
    time_components = raw_time.split('.')
    return float(time_components[0])*1000 + float(time_components[1])/1000


# Ensures there is a key in the dictionary for a given process
def add_process_key_if_needed(process):
    if process in all_information:
        return
    all_information[process] = {}
    all_information[process]['timestamps'] = {}
    all_information[process]['info'] = {}

# Records the start time of an event
def set_begin_time(process_info, EVENT, timestamp):
    add_process_key_if_needed(process_info)
    per_process_data = all_information.get(process_info, None)
    per_process_time = per_process_data.get('timestamps', None)
    per_process_time[EVENT] = timestamp


# Calculate time elsapsed from the start to the end
def find_latency(process_info, BEGIN_EVENT, timestamp):
    per_process_data = all_information.get(process_info, None)
    if per_process_data:
        per_process_time = per_process_data.get('timestamps', None)
        if per_process_time:
            begin_timestamp = per_process_time.get(BEGIN_EVENT, None)
            if begin_timestamp:
                time_elapsed = timestamp - begin_timestamp
                time_elapsed = round(time_elapsed, 3)
                if time_elapsed > threshold:
                    return(True, time_elapsed)
                else:
                    return(False, time_elapsed)
    return (False, 0.0)


# Prints latency and begin info
def print_info(process_info, message, EVENT, time):
    print '\n%s : %s : time = %s ms' %(process_info, message, str(time))
    begin_info = get_info_dict_for_event(process_info, EVENT)
    if begin_info:
        print 'start :',
        for key, value in begin_info.iteritems():
            print '%s = %s' %(key, value),
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
        return process_data.get('info', None)
    return None

def follow(thefile):
    while True:
        line = thefile.readline()
        if not line:
            continue
        yield line

trace_file = open(source_path)
output_lines = follow(trace_file)

for line in output_lines:
    matches = re.match(tracepoint_pattern, line)
    if matches:
        process_info = matches.group(1)
        timestamp = convert_time(matches.group(4))
        tracepoint_name = matches.group(5)
        trace_info = matches.group(6)

        
        def direct_reclaim_b():
            set_begin_time(process_info, DIRECT_RECLAIM_BEGIN, timestamp)
            match_format = re.match(direct_reclaim_begin_pattern, trace_info)
            if match_format:
                info_to_add = {}
                info_to_add['order'] = match_format.group(1)
                info_to_add['gfp_flags'] = match_format.group(3)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[DIRECT_RECLAIM_BEGIN] = info_to_add


        def direct_reclaim_e():
           delay_status, time_elapsed = find_latency(process_info,
                                                     DIRECT_RECLAIM_BEGIN,
                                                     timestamp)

           if delay_status:
               print_info(process_info, 'direct reclaim',
                          DIRECT_RECLAIM_BEGIN, time_elapsed)
               match_format = re.match(direct_reclaim_end_pattern, trace_info)
               
               if match_format:
                   print 'end : nr_reclaimed = %s' %(match_format.group(1))


        def shrink_slab_b():
            set_begin_time(process_info, SHRINK_SLAB_BEGIN, timestamp)
            match_format = re.match(shrink_slab_begin_pattern, trace_info)
            
            if match_format:
                info_to_add = {}
                info_to_add['name'] = match_format.group(1)
                info_to_add['nid'] = match_format.group(4)
                info_to_add['pgs_scanned'] = match_format.group(7)
                info_dict = get_info_dict_for_process(process_info)
                info_dict[SHRINK_SLAB_BEGIN] = info_to_add


        def shrink_slab_e():
            delay_status, time_elapsed = find_latency(process_info,
                                                      SHRINK_SLAB_BEGIN,
                                                      timestamp)
            match_format = re.match(shrink_slab_end_pattern, trace_info)
            
            if match_format:
                name = match_format.group(1)
                shrinker_latencies[name] += time_elapsed
            
                if delay_status:
                    print_info(process_info, 'shrink slab', SHRINK_SLAB_BEGIN,
                               time_elapsed)
                    print 'total time spent in %s = %.3f' %(name,
                            shrinker_latencies[name]) 
                    print 'end : name = %s new scan count = %s' %(
                            match_format.group(1), match_format.group(6))


        trace_match = {'mm_vmscan_direct_reclaim_begin' : direct_reclaim_b,
                       'mm_vmscan_direct_reclaim_end'   : direct_reclaim_e,
                       'mm_shrink_slab_start'           : shrink_slab_b,
                       'mm_shrink_slab_end'             : shrink_slab_e}

        if tracepoint_name in trace_match:
            trace_match[tracepoint_name]()
        else:
            pass

 
