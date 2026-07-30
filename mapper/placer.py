
import logging
import os
import copy
#import argparse
#from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
#from contexts.mapper_context import mapper_context

class placer:

    def __init__ (self, mapper_context=None, cgra_context=None, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
        fn_name = placer.__init__.__name__
        # Setup logger
        self.logger_name = None
        self.logger = None
        if (logger_name):
            self.logger_name = logger_name
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger_name = self.__class__.__name__
            self.logger = self.log_setup(self.logger_name, log_level, log_dir)
        # State vars
        self.mapper_ctxt = None
        self.cgra_ctxt = None
        if (mapper_context is not None and cgra_context is not None):
            self.load_context(mapper_context, cgra_context)
    
    def log_setup (self, logger_name, log_level, log_dir) -> logging:
        cwd = os.getcwd()
        log_fname = logger_name + '.log'
        log_path = os.path.join(cwd, log_dir, log_fname)
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)               # The level should be lowest level set in handlers
        log_format = logging.Formatter(fmt='%(asctime)s.%(msecs)03d - [%(levelname)s] ||| %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        # Stream Handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_format)
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)
        # File Handler
        file_handler = logging.FileHandler(log_path, mode='w')
        file_handler.setFormatter(log_format)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
        return logger
    
    # Keep this for standalone placer test
    def load_context (self, mapper_context=None, cgra_context=None) -> bool:
        ret_val = False
        if (mapper_context is not None and cgra_context is not None):
            self.mapper_ctxt = mapper_context
            self.cgra_ctxt = cgra_context
            ret_val = True
        return ret_val
    
    def assert_block_supports_opcode (self, node_opcode: str, block_avail_pe: dict) -> bool:
        fn_name = placer.assert_block_supports_opcode.__name__
        ret_val = False
        supported_opcodes = list(block_avail_pe.keys()) + self.cgra_ctxt.pe_cfg['Routing']
        #self.logger.debug(f'{fn_name} ||| Block supports opcodes = {supported_opcodes}')
        if (node_opcode in supported_opcodes):
            ret_val = True
        return ret_val
    
    def assert_routing_opcode (self, node_opcode: str) -> bool:
        ret_val = False
        for rop in self.cgra_ctxt.pe_cfg['Routing']:
            if (node_opcode == rop):
                ret_val = True
                break
        return ret_val
    
    def get_opGroup (self, opcode: str, peType: str) -> str | None:
        fn_name = placer.get_opGroup.__name__
        ret_group = None
        if (peType is not None):
            opGroups = self.cgra_ctxt.pe_cfg[peType]['opGroup']
            for k in opGroups.keys():
                opc_list = opGroups[k]
                for opc in opc_list:
                    if (opc == opcode):
                        ret_group = k
                        break
                if (ret_group is not None):
                    break
        return ret_group

    def get_op_edges (self, node_name: str, parents, children, edges) -> tuple[list, list]:
        fn_name = placer.get_op_edges.__name__
        # First find how many input and output data-edges the node utilizes
        n_fanin = len(parents)
        n_fanout = len(children)
        if (n_fanin > self.cgra_ctxt.cgra_radix or n_fanout > self.cgra_ctxt.cgra_radix):
            err_msg = f'{fn_name} ||| Node[{node_name}] fanin/fanout greater than CGRA radix; Unsupported DFG provided !'
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        # Get corresponding edges
        fin_edges = [[e for e in edges if (e.get_source() == p.get_name() and e.get_destination() == node_name)][0] for p in parents]
        fout_edges = [[e for e in edges if (e.get_source() == node_name and e.get_destination() == c.get_name())][0] for c in children]
        return (fin_edges, fout_edges)
    
    def update_pe_routing_resource (self, block, shadow_block, trt_pe_ID: int, trt_pe_routing_cost: list, trt_shadow_pe_routing_cost: list, blk_pe_info: list, shadow_blk_pe_info: list) -> None:
        fn_name = placer.update_pe_routing_resource.__name__
        self.logger.debug(f'{fn_name} ||| PE routing_cost = {trt_pe_routing_cost} | blk_pe_info[{block}] before mutation: {blk_pe_info}')
        self.logger.debug(f'{fn_name} ||| shadow_PE routing_cost = {trt_shadow_pe_routing_cost} | shadow_blk_pe_info[{shadow_block}] before mutation: {shadow_blk_pe_info}')
        # Reflect the target_opcode_cost in blk_pe_info
        blk_pe_info[trt_pe_ID][1][0][0] -= trt_pe_routing_cost[0][0]
        blk_pe_info[trt_pe_ID][1][0][1] -= trt_pe_routing_cost[0][1]
        blk_pe_info[trt_pe_ID][1][1][0] -= trt_pe_routing_cost[1][0]
        blk_pe_info[trt_pe_ID][1][1][1] -= trt_pe_routing_cost[1][1]
        # Reflect the target_opcode_cost in shadow_blk_pe_info
        shadow_blk_pe_info[trt_pe_ID][1][0][0] -= trt_shadow_pe_routing_cost[0][0]
        shadow_blk_pe_info[trt_pe_ID][1][0][1] -= trt_shadow_pe_routing_cost[0][1]
        shadow_blk_pe_info[trt_pe_ID][1][1][0] -= trt_shadow_pe_routing_cost[1][0]
        shadow_blk_pe_info[trt_pe_ID][1][1][1] -= trt_shadow_pe_routing_cost[1][1]
        self.logger.debug(f'{fn_name} ||| blk_pe_info[{block}] after mutation: {blk_pe_info}')
        self.logger.debug(f'{fn_name} ||| shadow_blk_pe_info[{shadow_block}] after mutation: {shadow_blk_pe_info}')

    def is_pe_routable (self, node_name, block, target_pe_ID: int, in_edges: list, out_edges: list, parents: list, children: list, blk_pe_info: list, shadow_blk_pe_info: list) -> tuple[int|None, list[list[int, int]], list[list[int, int]]]:
        fn_name = placer.is_pe_routable.__name__
        trt_pe_ID = None
        trt_pe_routing_cost = None
        trt_shadow_pe_routing_cost = None
        t_pe_routing_cost = [[0, 0], [0, 0]]                # [[data_in, data_out], [pred_in, pred_out]]
        t_shadow_pe_routing_cost = [[0, 0], [0, 0]]
        # Find if the target PE satisfies the in/out routing conditions from pe_info
        trt_pe_routing_resources = blk_pe_info[target_pe_ID][1]
        trt_shadow_pe_routing_resources = shadow_blk_pe_info[target_pe_ID][1]
        # Sanity check
        len_ie = len(in_edges)
        len_oe = len(out_edges)
        len_p = len(parents)
        len_c = len(children)
        if (len_ie != len_p or len_oe != len_c):
            self.logger.error(f'{fn_name} ||| Disparity between number of edges and parents/children !')
            return (trt_pe_ID, trt_pe_routing_cost, trt_shadow_pe_routing_cost)
        # Find input cost
        for i in range(len_ie):
            # We assume the ordering of edges corresponds to its respective block in the blocks list.
            ie = in_edges[i]
            # Sanity check to make sure DFG edge has guide attributes
            if (ie.get('data') is None and ie.get('predicate') is None):
                err_msg = f'{fn_name} ||| DFG node[{node_name}] has neither data nor predicate guide attributes on its input edge'
                self.logger.error(err_msg)
                raise ValueError(err_msg)
            # For input edges, we look from the perspective of parent nodes
            p_blk = int(parents[i].get('rank')) % self.cgra_ctxt.cgra_blocks
            is_forward_edge = self.mapper_ctxt.assert_forward_edge(p_blk, block)
            p_region = self.mapper_ctxt.get_node_region(p_blk)
            n_region = self.mapper_ctxt.get_node_region(block)
            # A forward edge will travel through same region as parent_block,
            # and vice-versa for a reverse edge.
            # Case 1: its a forward edge and target block and parent block are in the same region
            # Case 4: backward edge, target block and parent block are in opposite regions
            if ((is_forward_edge and p_region == n_region) or (not is_forward_edge and p_region != n_region)):
                if (ie.get('data') is not None):
                    t_pe_routing_cost[0][0] += 1
                if (ie.get('predicate') is not None):
                    t_pe_routing_cost[1][0] += 1
            # Case 2: forward edge, target block and parent block are in opposite regions
            # Case 3: backward edge, target block and parent block are in same region
            elif ((is_forward_edge and p_region != n_region) or (not is_forward_edge and p_region == n_region)):
                if (ie.get('data') is not None):
                    t_shadow_pe_routing_cost[0][0] += 1
                if (ie.get('predicate') is not None):
                    t_shadow_pe_routing_cost[1][0] += 1
            else:
                err_msg = f'{fn_name} ||| Something went wrong ! | is_forward_edge = {is_forward_edge}, n_region = {n_region}, p_region = {p_region}'
                self.logger.error(err_msg)
                raise ValueError(err_msg)
        # Find output cost
        for i in range(len_oe):
            oe = out_edges[i]
            # Sanity check to make sure DFG edge has guide attributes
            if (oe.get('data') is None and oe.get('predicate') is None):
                err_msg = f'{fn_name} ||| DFG node[{node_name}] has neither data nor predicate guide attributes on its output edge'
                self.logger.error(err_msg)
                raise ValueError(err_msg)
            # For output edges, we look from the perspective of target node
            # Hence there are only 2 cases, both dependent on the edge direction
            c_blk = int(children[i].get('rank')) % self.cgra_ctxt.cgra_blocks
            is_forward_edge = self.mapper_ctxt.assert_forward_edge(block, c_blk)
            if (is_forward_edge):
                if (oe.get('data') is not None):
                    t_pe_routing_cost[0][1] += 1
                if (oe.get('predicate') is not None):
                    t_pe_routing_cost[1][1] += 1
            else:
                if (oe.get('data') is not None):
                    t_shadow_pe_routing_cost[0][1] += 1
                if (oe.get('predicate') is not None):
                    t_shadow_pe_routing_cost[1][1] += 1
        self.logger.debug(f'{fn_name} ||| required_routing_cost = {t_pe_routing_cost} | required_shadow_routing_cost = {t_shadow_pe_routing_cost}')
        # Check if routable
        if (trt_pe_routing_resources[0][0] >= t_pe_routing_cost[0][0] and trt_pe_routing_resources[0][1] >= t_pe_routing_cost[0][1] \
            and trt_pe_routing_resources[1][0] >= t_pe_routing_cost[1][0] and trt_pe_routing_resources[1][1] >= t_pe_routing_cost[1][1] \
            and trt_shadow_pe_routing_resources[0][0] >= t_shadow_pe_routing_cost[0][0] and trt_shadow_pe_routing_resources[0][1] >= t_shadow_pe_routing_cost[0][1] \
            and trt_shadow_pe_routing_resources[1][0] >= t_shadow_pe_routing_cost[1][0] and trt_shadow_pe_routing_resources[1][1] >= t_shadow_pe_routing_cost[1][1]):
            trt_pe_routing_cost = t_pe_routing_cost
            trt_shadow_pe_routing_cost = t_shadow_pe_routing_cost
            trt_pe_ID = target_pe_ID
        else:
            self.logger.debug(f'{fn_name} ||| Target PE[{target_pe_ID}] in block[{block}] lacks routing resources \n Required PE cost = {t_pe_routing_cost}, shadow PE cost = {t_shadow_pe_routing_cost}; Available PE resources = {trt_pe_routing_resources}, shadow PE resources = {trt_shadow_pe_routing_resources}')
        return (trt_pe_ID, trt_pe_routing_cost, trt_shadow_pe_routing_cost)
    
    def remove_target_pe (self, block, trt_pe_ID: int, trt_pe_type: str, trt_pe_opGroup: str, blk_avail_pe: dict, shadow_blk_avail_pe: dict) -> None:
        fn_name = placer.remove_target_pe.__name__
        #self.logger.debug(f'{fn_name} ||| trt_pe_ID = {trt_pe_ID}, trt_pe_type = {trt_pe_type}, trt_pe_opGroup = {trt_pe_opGroup}')
        self.logger.debug(f'{fn_name} ||| blk_avail_pe[{block}] before mutation: {blk_avail_pe}')
        # Remove PEs from all opGroups using target_pe_ID/pe_type in blk_avail_pe
        # Get opGroup Keys to search for in blk_avail_pe
        op_keys = self.cgra_ctxt.pe_cfg[trt_pe_type]['opGroup'][trt_pe_opGroup]
        #self.logger.debug(f'{fn_name} ||| Searching blk_avail_pe for keys = {op_keys}')
        # Remove target from blk_avail_pe
        for k in op_keys:
            for i, pd in enumerate(blk_avail_pe[k]):
                #self.logger.debug(f'{fn_name} ||| {k}[{i}] = {pd}')
                if (pd[0] == trt_pe_ID and pd[1] == trt_pe_type):
                    linked = pd[-1]
                    if (linked == 1):
                        del shadow_blk_avail_pe[k][i]
                    #self.logger.debug(f'{fn_name} ||| Removing PE[{trt_pe_ID}] from op[{k}]')
                    del blk_avail_pe[k][i]
        self.logger.debug(f'{fn_name} ||| blk_avail_pe[{block}] after mutation: {blk_avail_pe}')

    def find_candidate_pe (self, node, parents, children, edges, avail_pe: dict, pe_info: list) -> tuple[int, int]:
        fn_name = placer.find_candidate_pe.__name__
        trt_pe_ID = None
        trt_pe_type = None
        trt_pe_opGroup = None
        trt_pe_context = None
        trt_pe_routing_cost = None
        trt_shadow_pe_routing_cost = None
        unroutable = False
        # Get node's name, opID, opcode, rank and compute cgra_block
        n_name = node.get_name()
        n_attr = node.get_attributes()
        n_opcode = n_attr['opcode']
        n_rank = int(n_attr['rank'])
        n_blk = n_rank % self.cgra_ctxt.cgra_blocks
        n_shadow_blk = self.mapper_ctxt.get_shadow_block(n_blk)
        # Find a candidate PE using node's attribute list
        blk_avail_pe = avail_pe[n_blk]
        blk_pe_info = pe_info[n_blk]
        shadow_blk_avail_pe = avail_pe[n_shadow_blk]
        shadow_blk_pe_info = pe_info[n_shadow_blk]
        # Get node attributes to search for
        search_attr = self.cgra_ctxt.pe_cfg['Attributes']
        # First find how many input and output data-edges the node utilizes.
        fin_edges, fout_edges = self.get_op_edges(n_name, parents, children, edges)
        # Check if opcode is supported
        if (self.assert_block_supports_opcode(n_opcode, blk_avail_pe)):
            # Check if opcode is of routing type
            routing = self.assert_routing_opcode(n_opcode)
            # Get corresponding list of candidate PEs from avail_pe
            cand_pe_list = blk_pe_info if (routing) else blk_avail_pe[n_opcode]
            if (len(cand_pe_list) == 0):
                self.logger.error(f'{fn_name} ||| No candidate PE available to map opcode[{n_opcode}] from node[{n_name}]')
            else:
                for cpid, cand_pe in enumerate(cand_pe_list):
                    unroutable = False
                    # List to keep track of used opGroups
                    used_opGroups = []
                    lp_abort = False
                    cand_pe_id = cpid if (routing) else cand_pe[0]
                    cand_pe_type = None if (routing) else cand_pe[1]
                    cand_pe_context = None if (routing) else cand_pe[2]
                    cand_pe_routing_cost = None
                    cand_shadow_pe_routing_cost = None
                    # Check if candidate PE supports the target opcode
                    cand_pe_opGroup = self.get_opGroup(n_opcode, cand_pe_type)
                    if (cand_pe_opGroup is not None):
                        used_opGroups.append(cand_pe_opGroup)
                        # Find if candidate PE can accomodate supplimentary node attributes
                        for attr in search_attr:
                            # Check if the attribute we are searching for exists in node
                            if (attr['name'] in list(n_attr.keys())):
                                # Get related opcode from node attribute description
                                t_opcode = attr['translate']
                                # Check if supplimentary opcode falls within same opGroup in candidate PE
                                t_opGroup = self.get_opGroup(t_opcode, cand_pe_type)
                                self.logger.debug(f'{fn_name} ||| attr[{attr['name']}] = opcode[{t_opcode}] | t_opGroup = {t_opGroup}; used_opGroups = {used_opGroups}')
                                if (t_opGroup in used_opGroups or t_opGroup is None):
                                    self.logger.error(f'{fn_name} ||| Cannot map two opcodes into the same opGroup[{t_opGroup}] of candidate[{cand_pe_id}]')
                                    used_opGroups = None
                                    lp_abort = True
                                    break
                                self.logger.debug(f'{fn_name} ||| node[{n_name}] -> attr[{attr['name']}] = opcode[{t_opcode}]; Satisfied')
                                used_opGroups.append(t_opGroup)
                    if (lp_abort):
                        break
                    # Check if there is sufficient in/out data_paths from target_PE
                    # An edge need not always consume resources from the target-node's block,
                    # depending on the rank of parent/child, an edge may consume from 
                    # the target-node's current or shadow-block.
                    cand_pe_id, cand_pe_routing_cost, cand_shadow_pe_routing_cost = self.is_pe_routable(n_name, n_blk, cand_pe_id, fin_edges, fout_edges, parents, children, blk_pe_info, shadow_blk_pe_info)
                    if (cand_pe_id is None):
                        unroutable = True
                        continue
                    trt_pe_ID = cand_pe_id
                    trt_pe_type = cand_pe_type
                    trt_pe_opGroup = used_opGroups
                    trt_pe_context = cand_pe_context
                    trt_pe_routing_cost = cand_pe_routing_cost
                    trt_shadow_pe_routing_cost = cand_shadow_pe_routing_cost
                    self.logger.debug(f'{fn_name} ||| Found candidate PE[{cand_pe_id}] in block[{n_blk}], that supports opcode[{n_opcode}] from node[{n_name}] | target_pe_id = {trt_pe_ID} | PE routing_cost = {trt_pe_routing_cost}, shadow_PE routing_cost = {trt_shadow_pe_routing_cost}')
                    break
            if (trt_pe_ID is not None):
                if (trt_pe_opGroup is not None):
                    self.logger.debug(f'{fn_name} ||| target_pe_opGroup list = {trt_pe_opGroup}')
                    for opG in trt_pe_opGroup:
                        # If a valid candidate is available, remove it from avail_pe list
                        self.remove_target_pe(n_blk, trt_pe_ID, trt_pe_type, opG, blk_avail_pe, shadow_blk_avail_pe)
                # Update PE routing resources
                self.update_pe_routing_resource(n_blk, n_shadow_blk, trt_pe_ID, trt_pe_routing_cost, trt_shadow_pe_routing_cost, blk_pe_info, shadow_blk_pe_info)
            else:
                self.logger.error(f'{fn_name} ||| Failed to place node[{n_name}] with opcode[{n_opcode}] as suitable candidate not found | unroutable = {unroutable}')
        else:
            self.logger.error(f'{fn_name} ||| Opcode[{n_opcode}] not supported by block[{n_blk}]')
        return (trt_pe_ID, trt_pe_context, unroutable)
    
    # Run placer on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt=None) -> bool:
        fn_name = placer.run.__name__
        # Make a copy of avail_pe and pe_info from cgra_ctxt
        avail_pe = copy.deepcopy(self.cgra_ctxt.avail_pe)
        pe_info = copy.deepcopy(self.cgra_ctxt.pe_info)
        # Get dot nodes
        dnodes = dot_ctxt.dot_nodes
        dnodes_collection = copy.deepcopy(dot_ctxt.dot_rank_collection)
        max_nrank = dot_ctxt.dot_max_rank
        max_brank = self.cgra_ctxt.cgra_blocks + max_nrank
        #ranks = list(dnodes_collection.keys())
        #ranks.sort()
        dedges = dot_ctxt.dot_edges
        total_nodes = len(dnodes)
        nodes_placed = 0
        self.logger.info(f'{fn_name} ||| Starting Placer run: Total nodes = {total_nodes}')
        placed = False
        retry = False
        reflect_nodes = []
        # Place nodes by rank
        cur_n_rank = 0
        while (cur_n_rank <= max_brank):
        #for r in ranks:
            n_carry_over = []
            next_n_rank = cur_n_rank+1
            rnodes = copy.deepcopy(dnodes_collection[cur_n_rank])
            self.logger.debug(f'{fn_name} ||| Placing nodes in rank[{cur_n_rank}] = {[rn.get_name() for rn in rnodes]}')
            for n in rnodes:
                n_name = n.get_name()
                n_children = dot_ctxt.get_children(n.get_name())
                n_parents = dot_ctxt.get_parents(n.get_name())
                n_opcode = n.get('opcode')
                n_opID = n.get('opID')
                p_opID = [p.get('opID') for p in n_parents]
                n_rank = int(n.get('rank'))
                routing = self.assert_routing_opcode(n_opcode)
                # The virtual blocks (cgra_ctxt.cgra_blocks) cover the whole triangle wave.
                # Hence its ok to get a nodes block using rank and virtual blocks.
                n_blk = n_rank % self.cgra_ctxt.cgra_blocks
                target_pe_ID = None
                unroutable = False
                self.logger.debug(f'{fn_name} ||| node = {n_name}, opID = {n_opID}, opcode = {n_opcode}, block = {n_blk}')
                # Quick sanity check
                if (n_rank != cur_n_rank):
                    self.logger.error(f'{fn_name} ||| Collective rank[{cur_n_rank}] does not match node\'s[{n_rank}], aborting placement !')
                    break
                # Get candidate PE
                target_pe_ID, _, unroutable = self.find_candidate_pe(n, n_parents, n_children, dedges, avail_pe, pe_info)
                if (target_pe_ID is None):
                    self.logger.error(f'{fn_name} ||| No target PE found for PE_opcode[{n_opcode}] of node[{n_name}] in block[{n_blk}] !')
                    if (unroutable and routing):
                        # Routing nodes are a result of legalization. Hence they cannot
                        # be moved. For ex: An extension/bridge, when moved will only 
                        # create more bridges. Therefor, if placement fails for a 
                        # routing node, this cannot be fixed and the DFG has to be discarded.
                        self.logger.error(f'{fn_name} ||| Cannot move this node[{n_name}] to rank[{next_n_rank}]')
                        retry = False
                        break
                    else:
                        # TODO: A node to move is selected depending on the cost of movement.
                        #       The cost is determined by the routing cost of the a node.
                        #       Ex: Let node A have 1-in and 2-out, while B has 1-in and 1-out.
                        #           Moving A will generate atleast 3 bridge nodes, whereas
                        #           moving B will generate atleast 2 bridges. Thus, we select 
                        #           the node with least moving cost and move it to the
                        #           subsequent rank in hopes of finding a free PE there.
                        #       This is the point where SA may be included to a global minimum.
                        # But for now, simply move the node that cant be placed onto the next rank.
                        n.set('rank', str(next_n_rank))
                        self.logger.warning(f'{fn_name} ||| Moving node[{n_name}] to rank[{n.get('rank')}] and continuing')
                        #dnodes_collection[next_n_rank].append(n)
                        n_carry_over.append(n)
                        # Find and delete node in current rank
                        nid = [id for id, dn in enumerate(dnodes_collection[cur_n_rank]) if (dn.get_name() == n_name)][0]
                        del dnodes_collection[cur_n_rank][nid]
                        # Keep track of nodes to modify in DFG
                        reflected = False
                        for rid in range(len(reflect_nodes)):
                            if (n.get_name() == reflect_nodes[rid].get_name()):
                                reflect_nodes[rid] = n
                                reflected = True
                                break
                        if (not reflected):
                            reflect_nodes.append(n)
                        retry = True
                else:
                    # Place node in target PE by creating an entry in mapper_context's pe_meta
                    # NOTE: Mapper context stores all relevant data using global_peID
                    global_target_pe_ID = self.mapper_ctxt.get_globalPE_id(target_pe_ID, n_blk)
                    self.mapper_ctxt.add_node2pe(n_name, global_target_pe_ID)
                    self.mapper_ctxt.add_pe_meta_opcode(global_target_pe_ID, n_name, n_opcode, n_opID, p_opID)
                    self.logger.debug(f'{fn_name} ||| Successfully placed node[{n_name}], opID[{n_opID}], opcode[{n_opcode}] @ target PE[{global_target_pe_ID}] in block[{n_blk}]')
                    # Find and delete node in current rank
                    nid = [id for id, dn in enumerate(dnodes_collection[cur_n_rank]) if (dn.get_name() == n_name)][0]
                    del dnodes_collection[cur_n_rank][nid]
                    # Update tracker
                    nodes_placed += 1
            # Insert carry over to the begining of next rank's collection
            if (dnodes_collection.get(next_n_rank, None) is not None):
                self.logger.debug(f'{fn_name} ||| Before Carry: Next dnodes_collection[{next_n_rank}] = {[rn.get_name() for rn in dnodes_collection[next_n_rank]]}')
                dnodes_collection[next_n_rank][0:0] = n_carry_over
            else:
                dnodes_collection[next_n_rank] = n_carry_over
                if (cur_n_rank == max_brank and len(n_carry_over) > 0):
                    self.logger.error(f'{fn_name} ||| Exhausted moves, still have carry_over !')
                    retry = False
            self.logger.debug(f'{fn_name} ||| Post Carry: Next dnodes_collection[{next_n_rank}] = {[rn.get_name() for rn in dnodes_collection[next_n_rank]]}')
            self.logger.debug(f'{fn_name} ||| Nodes to reflect = {[rn.get_name() for rn in reflect_nodes]}')
            self.logger.debug(f'{fn_name} ||| reflected ranks = {[rn.get('rank') for rn in reflect_nodes]}')
            # Exit if the DFG can no longer be routed or All nodes have been placed
            if ((unroutable and routing) or nodes_placed == total_nodes):
                break
            cur_n_rank = next_n_rank
        if (retry):
            dot_ctxt.dot_reflect = reflect_nodes
        placed = True if (nodes_placed == total_nodes) else False
        pass_fail_flag = 'PASSED' if (placed) else 'FAILED'
        self.logger.info(f'{fn_name} ||| End of Placer run: Total nodes = {len(dnodes)} | Nodes placed = {nodes_placed} | Placement: {pass_fail_flag}')
        return placed, retry
    
def _test ():
    fn_name = _test.__name__
    cwd = os.getcwd()

    # CMD parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', action='store', default="", dest='dot_file', help='DOT file to parse')
    args = parser.parse_args()

    # Setup and fpaths
    dot_fpath = os.path.join(cwd, 'dots', 'results', args.dot_file)
    cgra_cfg_fpath = os.path.join(cwd, 'configs', 'cgra_config.yaml')
    pe_cfg_fpath = os.path.join(cwd, 'configs', 'pe_config.yaml')
    # Get dot_context
    dot_ctxt = dot_context(log_level=logging.DEBUG)
    dot_ctxt.get_graph(dot_fpath)
    # Generate cgra_context
    cgra_ctxt = cgra_context(log_level=logging.DEBUG)
    cgra_ctxt.gen_cgra_context(cgra_cfg_fpath, pe_cfg_fpath)
    # Create mapper_context
    mapper_ctxt = mapper_context(cgra_ctxt.cgra_blocks, cgra_ctxt.cgra_block_size, cgra_ctxt.cgra_radix, log_level=logging.DEBUG)
    # Create and load placer
    plcr = placer(log_level=logging.DEBUG)
    plcr.load_context(mapper_ctxt, cgra_ctxt)

    # Perform standard CGRA sanity checks
    cgra_size = cgra_ctxt.cgra_size
    cgra_pe_cnt = 0
    for blk_deet in cgra_ctxt.cgra_cfg['CGRA']['composition']:
        for k in blk_deet.keys():
            cgra_pe_cnt += blk_deet[k]
    if (cgra_pe_cnt != cgra_size):
        print (f'{fn_name} ||| CGRA config: CGRA_size and CGRA_block composition mismatch !')
        return -1
    # Start placer
    plcr.run(dot_ctxt)
    # Print mapper context
    mapper_ctxt.print_data()

if __name__ == "__main__":
    _test()