# Specs given in the project document
set val(node_num)       101 
set val(duration)       100
set val(packetsize)     128
set val(repeatTx_)      10
set val(cbrInterval_)   0.02
set val(dim)           50
set val(trace_file)     jravicha.tr
set val(node_size)      5

# Parameters for setting up the simulation
set val(chan)           Channel/WirelessChannel    ;
set val(prop)           Propagation/TwoRayGround   ;
set val(netif)          Phy/WirelessPhy            ;
set val(mac)		Mac/MyMac;
set val(ifq)            Queue/DropTail/PriQueue    ;
set val(ll)             LL                         ;
set val(ant)            Antenna/OmniAntenna        ;
set val(ifqlen)         50                         ;
set val(nn)             $val(node_num)             ;
set val(rp)             DumbAgent                  ; 

# Create simulator object and set trace file
set ns                      [new Simulator]
set tracefd                 [open $val(trace_file) w]
$ns trace-all               $tracefd

# Use the given dimensions for topography
set topo                    [new Topography]
$topo load_flatgrid         $val(dim) $val(dim)

# Create GOD
create-god $val(nn)

# Set variables
Mac/MyMac set repeatTx_ $val(repeatTx_)
Mac/MyMac set cbrInterval_ $val(cbrInterval_)

# Node configuration
$ns node-config \
        -adhocRouting $val(rp) \
        -llType $val(ll) \
        -macType $val(mac) \
        -ifqType $val(ifq) \
        -ifqLen $val(ifqlen) \
        -antType $val(ant) \
        -propType $val(prop) \
        -phyType $val(netif) \
        -channelType $val(chan) \
        -topoInstance $topo \
        -agentTrace ON \
        -routerTrace ON \
        -macTrace ON \
        -movementTrace OFF 

# Create the sink node. Position it at the center.
set sink_node [$ns node]
$sink_node random-motion 0
$sink_node set X_ [expr $val(dim)/2]
$sink_node set Y_ [expr $val(dim)/2]
$ns initial_node_pos $sink_node $val(node_size)

# Attach a loss monitor to it for verification
set sink [new Agent/LossMonitor]
$ns attach-agent $sink_node $sink

# Random number generator with seed 10
set rng [new RNG]
$rng seed 10

# RNG for position
set xrand [new RandomVariable/Uniform]
$xrand use-rng $rng
$xrand set min_ [expr -$val(dim)/2]
$xrand set max_ [expr $val(dim)/2]

# RNG for time
set trand [new RandomVariable/Uniform]
$trand use-rng $rng
$trand set min_ 0
$trand set max_ $val(cbrInterval_)

# Create all other nodes
for {set i 0} {$i < $val(nn)-1 } {incr i} {
    set src_node($i) [$ns node] 
    $src_node($i) random-motion 0
    set x [expr $val(dim)/2 + [$xrand value]]
    set y [expr $val(dim)/2 + [$xrand value]]
    $src_node($i) set X_ $x
    $src_node($i) set Y_ $y
    $ns initial_node_pos $src_node($i) $val(node_size)

    set udp($i) [new Agent/UDP]
    $udp($i) set class_ $i
    $ns attach-agent $src_node($i) $udp($i)
    $ns connect $udp($i) $sink

    set cbr($i) [new Application/Traffic/CBR]
    $cbr($i) set packet_size_ $val(packetsize)
    $cbr($i) set interval_ $val(cbrInterval_)
    $cbr($i) attach-agent $udp($i)
    set start [$trand value]
    $ns at $start "$cbr($i) start"
 
    $ns at $val(duration) "$cbr($i) stop"
}


for {set i 0} {$i < $val(nn)-1 } {incr i} {
    $ns at $val(duration) "$src_node($i) reset";
}

$ns at $val(duration) "end"

# Function to call when simulation ends
proc end {} {
    global ns tracefd val sink
    $ns flush-trace
    close $tracefd
    puts "END OF SIMULATION. CHECK TRACE FILE FOR RESULTS"
    $ns halt
}

puts "START SIMULATION"
$ns run

# http://jhshi.me/2013/12/13/simulate-random-mac-protocol-in-ns2-part-i/index.html - This link was referred for this project (both ns and tcl parts) for learning purposes.
