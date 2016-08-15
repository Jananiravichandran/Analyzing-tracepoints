#!/usr/bin/env python  
# The script gives latencies in the direct reclaim and compaction code 
# greater than the threshold set and also shows how long each shrinker took.
# The input is from trace_pipe of the tracing directory.
# Setup of trace is done by running setup_alloc_trace.sh.

import argparse
import re
import sys
import signal

from collections import defaultdict

# Constants for tracepoints

DIRECT_RECLAIM_BEGIN        = 1
DIRECT_RECLAIM_END          = 2
SHRINK_SLAB_START           = 3
SHRINK_INACTIVE_LIST        = 5
TRY_TO_COMPACT              = 6
COMPACTION_BEGIN            = 7
COMPACTION_END              = 8
# Parse command line arguments

parser = argparse.ArgumentParser(description='Parser for latency analyzer')

parser.add_argument('-s', '--source', action='store',
                    default='/sys/kernel/debug/tracing/trace_pipe',
                    dest='source_path',
                    help='Specify source file to read trace output')
parser.add_argument('-o', '--output', action='store',
                    default='~/alloc-trace.data',
                    dest='output_file',
                    help='Specify file to write to')
parser.add_argument('-t', '--threshold', action='store', default=0.0,
                    dest='threshold', type=float)
args = parser.parse_args()

source_path = args.source_path
threshold = args.threshold
output_file = args.output_file

# Regex for lines
line_pattern = re.compile(r'(\d+\.\d+)\s+\|\s+\d*\)*\s+([\w-]+)\s+\|\s+.*\s+(\d*\.*\d*)\s+[us]{0,2}\s+\|\s+(.*)')

# Regex for tracepoints
tracepoint_pattern = re.compile(r'\/\*\s*([\w]*):\s*(.*)\s*\*\/')
shrinker_pattern = re.compile(r'\s*([\w]*)\+(.*)\s*')

function_end_pattern = re.compile(r'.*\/\*\s*([\w]*)\s*\*\/')

# The dictionary which holds tracepoint information for all processes

all_information = defaultdict(dict)

shrinker_latencies = defaultdict(float)

def print_shrinker_latencies(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)
    for key, value in shrinker_latencies.iteritems():
        print '%s : %f ms' %(key, value*1000)
    sys.exit(0)

original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, print_shrinker_latencies)

def set_begin_info(process, EVENT, timestamp, info):
    per_process_dict = all_information[process]
    begin_info = {}
    begin_info["data"] = info
    begin_info["time"] = timestamp
    per_process_dict[EVENT] = begin_info

def set_trace_info(process, EVENT, info):
    per_process_dict = all_information[process]
    per_process_dict[EVENT] = info

def find_latency(process, BEGIN_EVENT, timestamp):
    per_process_dict = all_information.get(process, None)
    if per_process_dict:
        begin_info = per_process_dict.get(BEGIN_EVENT, None)
        if begin_info:
            begin_data = begin_info.get("data", None)
            begin_time = begin_info.get("time", None)
            if begin_time:
                time_elapsed = float(timestamp) - float(begin_time)
                if time_elapsed > threshold:
                    return (True, begin_data, time_elapsed)
                return (False, begin_data, time_elapsed)
    return (False, None, 0.0)


def print_line(line_info):
    print line_info


def print_tracepoint(process, EVENT, info):
    if info:
        print info
    else:
        per_process_dict = all_information.get(process, None)
        TP_info = per_process_dict.get(EVENT, None)
        if TP_info:
            print TP_info
        per_process_dict.pop(EVENT, None)

def follow(the_file):
    while True:
        line = the_file.readline()
        if not line:
            continue
        yield line
try:
    logfile = open(source_path)
except IOError:
    print "Cannot open source file"
    exit(1)

loglines = follow(logfile)

for line in loglines:
    line_match = re.match(line_pattern, line)
    if line_match:
        timestamp = line_match.group(1)
        process_info = line_match.group(2)
        function_match = re.match(function_end_pattern, line_match.group(4))
        tracepoint_match = re.match(tracepoint_pattern, line_match.group(4))
        if tracepoint_match:
            TP_whole = line_match.group(4)
            TP_name = tracepoint_match.group(1)
            TP_info = tracepoint_match.group(2)


            def call_set_trace_info(EVENT):
                set_trace_info(process_info, EVENT, line)


            def direct_reclaim_b():
                call_set_trace_info(DIRECT_RECLAIM_BEGIN)


            def direct_reclaim_e():
                call_set_trace_info(DIRECT_RECLAIM_END)


            def shrink_inactive_list():
                call_set_trace_info(SHRINK_INACTIVE_LIST)


            def shrink_slab_b():
                set_begin_info(process_info, SHRINK_SLAB_START, timestamp,
                                line)


            def shrink_slab_e():
                delay_status, begin_data, time_elapsed = find_latency(
                                                            process_info,
                                                            SHRINK_SLAB_START,
                                                            timestamp)
                shrinker_match = re.match(shrinker_pattern, TP_info)
                if shrinker_match:
                    shrinker_name = shrinker_match.group(1)
                    shrinker_latencies[shrinker_name] += time_elapsed

                if delay_status:
                    print_tracepoint(process_info,
                                     SHRINK_SLAB_START,
                                     begin_data)
                    print_tracepoint(process_info,
                                     None,
                                     line)


            def try_to_compact():
                call_set_trace_info(TRY_TO_COMPACT)


            def compact_b():
                call_set_trace_info(COMPACTION_BEGIN)


            def compact_e():
                call_set_trace_info(COMPACTION_END)


            trace_match = {'mm_vmscan_direct_reclaim_begin' : direct_reclaim_b,
                           'mm_vmscan_direct_reclaim_end'   : direct_reclaim_e,
                           'mm_shrink_slab_start'           : shrink_slab_b,
                           'mm_shrink_slab_end'             : shrink_slab_e,
                           'mm_vmscan_lru_shrink_inactive'  :
                                                          shrink_inactive_list,
                           'mm_compaction_try_to_compact_pages':
                                                          try_to_compact,
                           'mm_compaction_begin'            : compact_b,
                           'mm_compaction_end'              : compact_e}

            if TP_name in trace_match:
                trace_match[TP_name]()
            else:
                pass
        else:
            function_match = re.match(function_end_pattern,
                                      line_match.group(4))
            if function_match:
                function_name = function_match.group(1)


                def alloc_pages():
                    print_line(line)
                    all_information.pop(process_info, None)


                def try_to_free_pages():
                    print_tracepoint(process_info, DIRECT_RECLAIM_BEGIN, None)
                    print_tracepoint(process_info, DIRECT_RECLAIM_END, None)
                    print_line(line)
                def shrink_inactive_list():
                    print_tracepoint(process_info, SHRINK_INACTIVE_LIST, None)
                    print_line(line)


                def try_to_compact():
                    print_tracepoint(process_info, TRY_TO_COMPACT, None)
                    print_line(line)


                def compact_zone():
                    print_tracepoint(process_info, COMPACTION_BEGIN, None)
                    print_tracepoint(process_info, COMPACTION_END, None)
                    print_line(line)


                f_match = {'__alloc_pages_nodemask' : alloc_pages,
                           'try_to_free_pages'      : try_to_free_pages,
                           'shrink_inactive_list'   : shrink_inactive_list,
                           'try_to_compact'         : try_to_compact,
                           'compact_zone'           : compact_zone}
                if function_name in f_match:
                    f_match[function_name]()
                else:
                    print_line(line)
