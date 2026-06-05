# FASTLane
A Rich-Interconnectivity Based CGRA

## Setup
(1) Navigate to project root './FASTLane'
(2) Create venv
(3) Install dependencies: pydot and GraphViz for DOT file parsing and modification
(4) Place application DFGs in './FASTLane/dots/srcs/' (NOTE: FASTMap currently supports only DFG nodes with fan-out/in <= 2).
(5) Run 'python3 -m dots_manager.manager -f <name_of_target_DFG_dot_file>' to generate DFG suitable to be mapped on FASTLane architecture. \
&nbsp;The modified DFG is placed in './FASTLane/dots/results/' with the same target name + the suffix '_output' appended.
(6) Modify CGRA and PE configs in './FASTLane/configs/' to support operations required in target DFG.
(7) Run 'python3 -m mapper.mapper -f <target_DFG_name_output>' to map the DFG onto FASTLane using FASTMap.
(8) View logs in './FASTLane/logs/'.