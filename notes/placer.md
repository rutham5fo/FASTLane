# placer.py

## Methods

### `load_context(mapper_context=None, cgra_context=None)`
Keeps this for standalone placer test.

### `assert_block_supports_opcode(node_opcode: str, block_avail_pe: dict)`
Checks if a given block supports a specific opcode.

### `assert_routing_opcode(node_opcode: str)`
Checks if a given opcode is of routing type.

### `get_opGroup(opcode: str, peType: str)`
Retrieves the operation group for a given opcode and PE type.

### `get_op_edges(node_name: str, parents, children, edges)`
Finds the number of input and output data-edges the node utilizes.
- **Fanin/Fanout Check**: Checks if node fanin/fanout is greater than CGRA radix, indicating an unsupported DFG.
- **Edge Retrieval**: Gets corresponding input and output edges.

### `update_pe_routing_resource(block, shadow_block, trt_pe_ID: int, trt_pe_routing_cost: list, trt_shadow_pe_routing_cost: list, blk_pe_info: list, shadow_blk_pe_info: list)`
Updates the routing resources for a PE in both the main and shadow blocks.
- **Reflect Costs**: Reflects the target opcode cost in `blk_pe_info` and `shadow_blk_pe_info`.

### `is_pe_routable(node_name, block, target_pe_ID: int, in_edges: list, out_edges: list, parents: list, children: list, blk_pe_info: list, shadow_blk_pe_info: list)`
Determines if a PE is routable for a given node based on available routing resources.
- **Sanity check**: Checks for disparity between the number of edges and parents/children.
- **Input Cost**: Finds the input cost, assuming edge ordering corresponds to its respective block. Includes sanity checks for DFG edge guide attributes (data/predicate).
- **Forward/Backward Edge Logic**: Differentiates between forward and backward edges and their impact on routing cost based on block regions.
- **Output Cost**: Finds the output cost, looking from the perspective of the target node.
- **Routability Check**: Checks if the PE has sufficient routing resources to accommodate the required costs.

### `remove_target_pe(block, trt_pe_ID: int, trt_pe_type: str, trt_pe_opGroup: str, blk_avail_pe: dict, shadow_blk_avail_pe: dict)`
Removes the target PE from the available PE list in both the main and shadow blocks.
- **OpGroup Search**: Gets opGroup Keys to search for in `blk_avail_pe`.
- **Target Removal**: Removes the target PE from `blk_avail_pe` and `shadow_blk_avail_pe` if linked.

### `find_candidate_pe(node, parents, children, edges, avail_pe: dict, pe_info: list)`
Finds a suitable candidate PE for a given node and its attributes.
- **Node Attributes**: Retrieves node's name, opID, opcode, rank, and computes cgra_block and shadow_block.
- **Edge Information**: Finds input and output data-edges utilized by the node.
- **Opcode Support**: Checks if the opcode is supported by the block and if it is of routing type.
- **Candidate PE List**: Retrieves the list of candidate PEs from `avail_pe`.
- **Opcode/Attribute Mapping**: Checks if the candidate PE supports the target opcode and can accommodate supplementary node attributes within distinct opGroups.
- **Routing Resource Check**: Checks if there are sufficient in/out data paths from the target PE, considering current and shadow blocks based on parent/child ranks.
- **PE Removal/Update**: If a valid candidate is found, it is removed from the available PE list, and its routing resources are updated.

### `run(dot_ctxt=None)`
Runs the placer algorithm to map DFG nodes to PEs.
- **Context Copy**: Makes a copy of `avail_pe` and `pe_info` from `cgra_ctxt`.
- **Node Iteration**: Iterates through each node in the DFG.
- **Block Computation**: Computes the node's block using rank and virtual blocks.
- **Candidate PE Search**: Finds a suitable candidate PE for the node.
- **Node Placement**: Places the node in the target PE by creating an entry in `mapper_context`'s `pe_meta` and updating `pe_meta_opcode`.
- **Placement Status**: Tracks placed nodes and reports overall placement success or failure.