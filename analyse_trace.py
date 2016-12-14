def filter(trace_file):
	# Open jravicha.tr
	with open(trace_file, 'r') as f :
		# Get the raw lines
		raw_lines = f.read().split('\n')
	traces = []
	
	# Iterate through every raw line and store only information we are interested in
	for line in raw_lines :
    		fields = line.split(' ')
		
		# Only send/ receive/drop event types
    		if fields[0] not in ['s', 'r', 'D'] :
      			continue
		# Only from MAC layer
    		if not (fields[3] == 'MAC') :
      			continue
		# Only of cbr traffic type
    		if not (fields[7] == 'cbr') :
      			continue
		# Append data of interest to traces
    		traces.append({'event': fields[0], 'node': fields[2], 'packet': int(fields[6])})

	# Get the total number of packets sent
	total_sent = len(set(t['packet'] for t in traces))
	
	# Number of packets received by sink
	packets_received = len(set(t['packet'] for t in traces if t['node'] == '_0_' and t['event'] == 'r'))
	
	# Print results
	print("total sent: %d, no of packets received by sink: %d, Percentage: %.2f%%" % (total_sent, packets_received, float(packets_received)/total_sent*100))
  	return

filter("jravicha.tr")

# Reference - http://jhshi.me/2013/12/15/simulate-random-mac-protocol-in-ns2-part-iv/index.html
