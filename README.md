# FASTLane
A Rich-Interconnectivity Based CGRA

## Setup
(1) Navigate to project root './FASTLane'. <br>
(2) Create venv. <br> 
(3) Install dependencies: pydot and GraphViz for DOT file parsing and modification. <br>
(4) Place application DFGs in './FASTLane/dots/srcs/' (NOTE: FASTMap currently supports only DFG nodes with fan-out/in <= 2). <br>
(5) Run 'python3 -m dots_manager.manager -f <name_of_target_DFG_dot_file>' to generate DFG suitable to be mapped on FASTLane architecture.
The modified DFG is placed in './FASTLane/dots/results/' with the same target name + the suffix '_output' appended. <br>
(6) Modify CGRA and PE configs in './FASTLane/configs/' to support operations required in target DFG. <br>
(7) Run 'python3 -m mapper.mapper -f <target_DFG_name_output>' to map the DFG onto FASTLane using FASTMap. <br>
(8) View logs in './FASTLane/logs/'. <br>