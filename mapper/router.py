
import logging
import os
#import argparse
#from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
#from contexts.mapper_context import mapper_context
#from mapper.placer import placer
from mapper.benes import benes

class router:

    def __init__ (self, mapper_context=None, cgra_context=None, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
        fn_name = router.__init__.__name__
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
        self.cgra_ctxt = None
        self.mapper_ctxt = None
        self.benes = None
        self.max_find_port_recursion = 0
        self.max_resolve_conflict_recursion = 1000
        if (cgra_context is not None and mapper_context is not None):
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
    
    def load_context (self, mapper_context=None, cgra_context=None) -> bool:
        ret_val = False
        if (mapper_context is not None and cgra_context is not None):
            self.mapper_ctxt = mapper_context
            self.cgra_ctxt = cgra_context
            self.max_find_port_recursion = self.cgra_ctxt.cgra_radix**2
            # Create Benes
            self.benes = benes(self.cgra_ctxt.cgra_block_size, log_level=logging.DEBUG)
            ret_val = True
        return ret_val
    
    def add_tracker (self, block_path_tracker: list[int], block_source_tracker: list[int], port_loc: int, new_node_pe, new_child_pe) -> bool:
        fn_name = router.add_tracker.__name__
        ret_val = False
        if (port_loc < len(block_path_tracker)):
            block_path_tracker[port_loc].append(new_child_pe)
            block_source_tracker[port_loc].append(new_node_pe)
            ret_val = True
        else:
            self.logger.error(f'{fn_name} ||| Failed to add src[{new_node_pe}], dest[{new_child_pe}] to trackers !')
        return ret_val

    def del_tracker (self, block_path_tracker: list[int], block_source_tracker: list[int], port_loc: int, source_pe: int) -> bool:
        fn_name = router.del_tracker.__name__
        ret_val = False
        tracker_loc = None
        for loc in range(len(block_source_tracker[port_loc])):
            if (block_source_tracker[port_loc][loc] == source_pe):
                tracker_loc = loc
                break
        if (tracker_loc is not None and port_loc < len(block_path_tracker)):
            del block_path_tracker[port_loc][tracker_loc]
            del block_source_tracker[port_loc][tracker_loc]
            ret_val = True
        else:
            #self.logger.error(f'{fn_name} ||| tracker_loc = {tracker_loc} | Failed to delete src[{source_pe}] in port[{port_loc}] from trackers ! \n blk_path_tracker = {block_path_tracker[port_loc]} \n blk_src_tracker = {block_source_tracker[port_loc]}')
            pass
        return ret_val

    def find_conflicting_pe (self, blk_path_tracker: list[int], blk_src_tracker: list[int], port_loc: int, source_pe: int, child_pe: int) -> tuple[int, int]:
        fn_name = router.find_conflicting_pe.__name__
        conflict_pe = None
        blk_tracker_loc = None
        # Find conflicting PE
        rel_blk_path_tracker = [int(id%self.cgra_ctxt.cgra_block_size) for id in blk_path_tracker[port_loc]]
        rel_ch_pe = int(child_pe%self.cgra_ctxt.cgra_block_size)
        for tloc, dest in enumerate(rel_blk_path_tracker):
            if (dest == rel_ch_pe and blk_src_tracker[port_loc][tloc] != source_pe):
                conflict_pe = blk_src_tracker[port_loc][tloc]
                blk_tracker_loc = tloc
                self.logger.debug(f'{fn_name} ||| port[{port_loc}] Conflict detected | ch_pe = {child_pe}, rel_ch_pe = {rel_ch_pe} \n blk_path_tracker = {blk_path_tracker} \n rel_blk_path_tracker = {rel_blk_path_tracker} \n blk_src_tracker = {blk_src_tracker}')
                break
        return conflict_pe, blk_tracker_loc

    def resolve_conflict (self, path_type: int, conflict_pe: int, conflict_stack: list[int], recursion_cnt: int=0) -> bool:
        fn_name = router.resolve_conflict.__name__
        resolved = False
        # Sanity check
        if (recursion_cnt > self.max_resolve_conflict_recursion or conflict_pe in conflict_stack):
            self.logger.error(f'{fn_name} ||| Resolution failed, aborting ! | recursiont_count = {recursion_cnt}, max_recursion = {self.max_resolve_conflict_recursion} | conflict_pe = {conflict_pe}, conflict_stack = {conflict_stack}')
            return resolved
        # Add current pe to stack
        conflict_stack.append(conflict_pe)
        conflict_list = []
        # Get block of interest from conflict_pe and port
        n_out_opID = self.mapper_ctxt.pe_meta[conflict_pe]['data_out_opID'] if (path_type == 0) else self.mapper_ctxt.pe_meta[conflict_pe]['pred_out_opID']
        n_out_blockID = self.mapper_ctxt.pe_meta[conflict_pe]['data_out_blockID'] if (path_type == 0) else self.mapper_ctxt.pe_meta[conflict_pe]['pred_out_blockID']
        n_port_children = self.mapper_ctxt.pe_meta[conflict_pe]['data_port_children'] if (path_type == 0) else self.mapper_ctxt.pe_meta[conflict_pe]['pred_port_children']
        # Rotate metadata
        self.logger.debug(f'{fn_name} ||| Rotating ports of PE[{conflict_pe}] | n_out_opID = {n_out_opID}, n_out_blockID = {n_out_blockID}, n_port_children = {n_port_children}')
        port_cnt = len(n_out_opID)
        t_out_opID, t_out_blockID, t_port_children = n_out_opID[0], n_out_blockID[0], n_port_children[0]
        for i in range(port_cnt):
            # Delete current child_pe from tracker
            ch_pe = n_port_children[i][1]
            if (ch_pe is not None):
                cblk_path_tracker = self.mapper_ctxt.data_path_tracker[n_out_blockID[i]] if (path_type == 0) else self.mapper_ctxt.pred_path_tracker[n_out_blockID[i]]
                cblk_src_tracker = self.mapper_ctxt.data_source_tracker[n_out_blockID[i]] if (path_type == 0) else self.mapper_ctxt.pred_source_tracker[n_out_blockID[i]]
                self.logger.debug(f'{fn_name} ||| Before removal of ch_pe[{ch_pe}] from port[{i}]: \n blk_path_tracker = {cblk_path_tracker} \n blk_src_tracker = {cblk_src_tracker}')
                self.del_tracker(cblk_path_tracker, cblk_src_tracker, i, conflict_pe)
            # Get new values
            if (i != port_cnt - 1):
                n_out_opID[i], n_out_blockID[i], n_port_children[i] = n_out_opID[i+1], n_out_blockID[i+1], n_port_children[i+1]
            else:
                n_out_opID[i], n_out_blockID[i], n_port_children[i] = t_out_opID, t_out_blockID, t_port_children
            ch_pe = n_port_children[i][1]
            #self.logger.debug(f'{fn_name} ||| new_ch_pe = {ch_pe}')
            if (ch_pe is not None):
                cblk_path_tracker = self.mapper_ctxt.data_path_tracker[n_out_blockID[i]] if (path_type == 0) else self.mapper_ctxt.pred_path_tracker[n_out_blockID[i]]
                cblk_src_tracker = self.mapper_ctxt.data_source_tracker[n_out_blockID[i]] if (path_type == 0) else self.mapper_ctxt.pred_source_tracker[n_out_blockID[i]]
                # Find conflicting path and populate conflict_list
                t_conflict_pe, _ = self.find_conflicting_pe(cblk_path_tracker, cblk_src_tracker, i, conflict_pe, ch_pe)
                if (t_conflict_pe is not None):
                    conflict_list.append(t_conflict_pe)
                # Add new child_pe to tracker
                self.add_tracker(cblk_path_tracker, cblk_src_tracker, i, conflict_pe, ch_pe)
                self.logger.debug(f'{fn_name} ||| After addition of ch_pe[{ch_pe}] from port[{i+1 if (i != port_cnt-1) else 0}]: \n blk_path_tracker = {cblk_path_tracker} \n blk_src_tracker = {cblk_src_tracker}')
        self.logger.debug(f'{fn_name} ||| PE[{conflict_pe}] conflict_list = {conflict_list}')
        # Recursively solve conflicts
        recursion_cnt += 1
        for i in range(len(conflict_list)):
            resolved = self.resolve_conflict(path_type, conflict_list[i], conflict_stack, recursion_cnt)
            if (not resolved):
                break
        if (len(conflict_list) == 0 or resolved):
            self.logger.debug(f'{fn_name} ||| Conflict resolved for PE[{conflict_pe}]')
            resolved = True
        return resolved

    def find_valid_port (self, path_type: int, block: int, n_pe: int, ch_pe: int, child_id: int, n_opID: int, n_out_opID: list, n_out_blockID: list, 
                         ch_in_opID: list, blk_path_tracker: list, blk_src_tracker: list, attempted_ports: list, port_children: list, recursion_cnt: int) -> bool:
        fn_name = router.find_valid_port.__name__
        # Find a port that does not contain the destination PE in its path-set
        routed = False
        possible_ports = []
        if (recursion_cnt > self.max_find_port_recursion):
            return routed
        for i in range(len(n_out_opID)):
            self.logger.debug(f'{fn_name} ||| Iteration[{recursion_cnt}] | n_pe = {n_pe}, n_opID = {n_opID}, child_id = {child_id}, ch_pe = {ch_pe} | n_out_opID = {n_out_opID}, n_out_blockID = {n_out_blockID}, ch_in_opID = {ch_in_opID} | blk_path_tracker = {blk_path_tracker}')
            if (ch_pe is None):
                self.logger.error(f'{fn_name} ||| Function call with non-existent child PE !')
                return
            # Get the relative pe_ids of all ids in blk_path_tracker
            # This avoids shadow_pe_ids aliasing with physical ids.
            # Ex: data_src_tracker = [[1, 2, 3, 5, 6, 0], [4]] ; data_path_tracker = [[8, 9, 10, 11, 13, 25], [10]]
            #     dest=25 is a shadow_pe, it will alias as 1 if left in the current path, resulting in two 1s in the same path.
            rel_blk_path_tracker = [int(id%self.cgra_ctxt.cgra_block_size) for id in blk_path_tracker[i]]
            rel_ch_pe = int(ch_pe%self.cgra_ctxt.cgra_block_size)
            ch_exists_inPath = rel_ch_pe in rel_blk_path_tracker
            port_attempted = i in attempted_ports[child_id]
            self.logger.debug(f'{fn_name} ||| port_sel[{i}] | rel_ch_pe = {rel_ch_pe}, rel_blk_path_tracker = {rel_blk_path_tracker}, ports_attempted = {attempted_ports} | ch_exists_inPath = {ch_exists_inPath}, port_attempted = {port_attempted}')
            if (not ch_exists_inPath and not port_attempted):
                # If port is free, consume it
                if (n_out_opID[i] is None):
                    # Attach opID to this port in parent and child
                    n_out_opID[i] = n_opID
                    ch_in_opID[i] = n_opID
                    n_out_blockID[i] = block
                    # Add this child PE to the list of port children
                    port_children[i] = (child_id, ch_pe)
                    # Add path in block's path&source-trackers
                    self.add_tracker(blk_path_tracker, blk_src_tracker, i, n_pe, ch_pe)
                    # Add to attempted ports
                    attempted_ports[child_id].append(i)
                    routed = True
                    break
                # Else, mark it as a possible port to place in and continue to find
                # a better solution, i.e., a port that is None/free.
                else:
                    possible_ports.append(i)
        # If there are possible routes, but routing was not successful.
        # Place this edge in one of the possible routes, replacing the
        # existing edge", and recursively call the above function till
        # all routes are successfully placed.
        if (not routed and len(possible_ports) > 0):
            # Pick a possible port that has not been attempted before
            prt = [pp for pp in possible_ports if (not pp in attempted_ports[child_id])][0]
            aux_n_opID = n_out_opID[prt]
            aux_n_blockID = n_out_blockID[prt]
            aux_child_id = port_children[prt][0]
            aux_ch_pe = port_children[prt][1]
            # Place current edge in this possible_port, displacing the existing edge
            n_out_opID[prt] = n_opID
            n_out_blockID[prt] = block
            ch_in_opID[prt] = n_opID
            # Update tracking info
            self.logger.debug(f'{fn_name} ||| prt = {prt}, aux_n_opID = {aux_n_opID}, aux_n_blockID = {aux_n_blockID}, aux_child_id = {aux_child_id}, aux_ch_pe = {aux_ch_pe} | blk_path_tracker[{prt}] = {blk_path_tracker[prt]}')
            port_children[prt] = (child_id, ch_pe)
            self.del_tracker(blk_path_tracker, blk_src_tracker, prt, n_pe)
            self.add_tracker(blk_path_tracker, blk_src_tracker, prt, n_pe, ch_pe)
            attempted_ports[child_id].append(prt)
            self.logger.debug(f'{fn_name} ||| prt = {prt}, aux_n_opID = {aux_n_opID}, aux_n_blockID = {aux_n_blockID}, aux_child_id = {aux_child_id}, aux_ch_pe = {aux_ch_pe} | blk_path_tracker[{prt}] = {blk_path_tracker[prt]}')
            # Recursive call with aux_n_opID and aux_ch_pe to place displaced edge
            recursion_cnt += 1
            routed = self.find_valid_port(path_type, aux_n_blockID, n_pe, aux_ch_pe, aux_child_id, aux_n_opID, n_out_opID, n_out_blockID, 
                                          ch_in_opID, blk_path_tracker, blk_src_tracker, attempted_ports, port_children, recursion_cnt)
        if (not routed):
            # Place in any unassigned port and try to resolve conflict
            ploc = None
            for loc, prt in enumerate(n_out_opID):
                if (prt is None):
                    ploc = loc
                    break
            if (ploc is None):
                self.logger.error(f'{fn_name} ||| Cannot attempt to resolve conflicts if there are not un-assigned ports !')
            else:
                conflict_pe = None
                conflict_stack = [n_pe]
                blk_tracker_loc = None
                # Place current edge in this possible_port
                n_out_opID[ploc] = n_opID
                n_out_blockID[ploc] = block
                ch_in_opID[ploc] = n_opID
                # Find conflicting PE
                conflict_pe, blk_tracker_loc = self.find_conflicting_pe(blk_path_tracker, blk_src_tracker, ploc, n_pe, ch_pe)
                if (conflict_pe is not None):
                    # Update tracking info
                    port_children[ploc] = (child_id, ch_pe)
                    self.logger.debug(f'{fn_name} ||| prt = {ploc}, n_opID = {n_opID}, n_block = {block}, child_id = {child_id}, ch_pe = {ch_pe} | n_out_opID = {n_out_opID}, n_out_blockID = {n_out_blockID} | conflicting_pe = {conflict_pe} @ {blk_tracker_loc} \n blk_path_tracker = {blk_path_tracker}, blk_src_tracker = {blk_src_tracker}')
                    #self.del_tracker(blk_path_tracker, blk_src_tracker, ploc, n_pe)
                    self.add_tracker(blk_path_tracker, blk_src_tracker, ploc, n_pe, ch_pe)
                    # Call resolver
                    self.logger.debug(f'{fn_name} ||| Attempting to resolve conflict start @ PE[{conflict_pe}] \n blk_path_tracker = {blk_path_tracker} \n blk_src_tracker = {blk_src_tracker}')
                    routed = self.resolve_conflict(path_type, conflict_pe, conflict_stack)
                else:
                    self.logger.error(f'{fn_name} ||| Wierd, there is a conflict, nevertheless there isnt one !')
        return routed
    
    def route_node_path (self, dedges, n_name, n_opID, n_pe, n_shadow_pe, n_children, n_blk, n_shadow_blk, data_path_tracker, data_source_tracker, pred_path_tracker, pred_source_tracker) -> bool:
        fn_name = router.route_node_path.__name__
        # Reaching this point means there is atleast one free out_port in parent node
        routed = True
        num_children = len(n_children)
        attempted_ports = [[] for _ in range(num_children)]
        for cid, ch in enumerate(n_children):
            ch_rank = int(ch.get('rank'))
            ch_name = ch.get_name()
            ch_opID = ch.get('opID')
            ch_blk = ch_rank % self.cgra_ctxt.cgra_blocks
            ch_pe = self.mapper_ctxt.node2pe[ch_name]
            routed = False
            recursion_cnt = 0

            # !!! NOTE: Untested Feature BEGIN !!!
            # Find if edge being routed is a data/predicate edge
            path_edge = [e for e in dedges if (e.get_source() == n_name and e.get_destination() == ch_name)][0]
            path_type = None
            if (path_edge.get('data') is not None):
                path_type = 0
            elif (path_edge.get('predicate') is not None):
                path_type = 1

            ch_in_opID = self.mapper_ctxt.pe_meta[ch_pe]['data_in_opID'] if (path_type == 0) else self.mapper_ctxt.pe_meta[ch_pe]['pred_in_opID']
            # NOTE: The DFG manager takes care of making sure all nodes are adjacent in 
            #         the architecture. Hence, if child node is behind parent node, its
            #         a reverse edge (shadow_path), else its a forwards edge.
            #         Except for the two corner cases 0 and phy_blocks-1 which have no reverse paths.
            if (path_type is not None):
                forward_edge = self.mapper_ctxt.assert_forward_edge(n_blk, ch_blk)
                self.logger.debug(f'{fn_name} ||| path_type = {path_type}, ch_blk = {ch_blk}, n_blk = {n_blk}, n_pe = {n_pe}, forward_edge = {forward_edge}')
                n_out_opID = None
                n_out_blockID = None
                n_blk_sel = n_blk if (forward_edge) else n_shadow_blk
                n_pe_sel = n_pe if (forward_edge) else n_shadow_pe
                # Select appropriate attributes
                if (self.mapper_ctxt.pe_meta.get(n_pe_sel, None) is None):
                    # Add an empty template metadata for routing purposes
                    # This can happen when overloading is disabled or
                    # There are no opcodes placed on the shadow_pe
                    self.mapper_ctxt.create_pe_meta(n_pe_sel)
                n_out_opID = self.mapper_ctxt.pe_meta[n_pe_sel]['data_out_opID'] if (path_type == 0) else self.mapper_ctxt.pe_meta[n_pe_sel]['pred_out_opID']
                n_out_blockID = self.mapper_ctxt.pe_meta[n_pe_sel]['data_out_blockID'] if (path_type == 0) else self.mapper_ctxt.pe_meta[n_pe_sel]['pred_out_blockID']
                port_children = self.mapper_ctxt.pe_meta[n_pe_sel]['data_port_children'] if (path_type == 0) else self.mapper_ctxt.pe_meta[n_pe_sel]['pred_port_children']
                blk_path_tracker = data_path_tracker[n_blk_sel] if (path_type == 0) else pred_path_tracker[n_blk_sel]
                blk_src_tracker = data_source_tracker[n_blk_sel] if (path_type == 0) else pred_source_tracker[n_blk_sel]
                # Source node sanity check
                if (n_out_opID is None or not None in n_out_opID):
                    self.logger.error(f'{fn_name} ||| No un-mapped ports available for node[{n_name}] with opID[{n_opID}], placed in PE[{n_pe}] | n_out_opID = {n_out_opID} !')
                    break
                # !!! NOTE: Untested Feature END !!!

                # Route n_pe->ch_pe edge
                self.logger.debug(f'{fn_name} ||| Routing Edge from src_PE[{n_pe}] -> dest_PE[{ch_pe}], in block[{n_blk if (forward_edge) else n_shadow_blk}]\'s path')
                # Find a port that does not contain the destination PE in its path-set
                routed = self.find_valid_port(path_type, n_blk_sel, n_pe_sel, ch_pe, cid, n_opID, n_out_opID, n_out_blockID, 
                                              ch_in_opID, blk_path_tracker, blk_src_tracker, attempted_ports, port_children, recursion_cnt)
                self.logger.debug(f'{fn_name} ||| Routed = {routed} | Result: src_PE[{n_pe}], Routing_PE = {n_pe_sel}, src_Node[{n_name}], out_opID = {n_out_opID}, out_blockID = {n_out_blockID}; dest_PE[{ch_pe}], dest_Node[{ch_name}], ch_in_opID = {ch_in_opID} \n blk_src_tracker = {blk_src_tracker} \n blk_path_tracker = {blk_path_tracker}')
                if (not routed):
                    self.logger.error(f'{fn_name} ||| There is no valid route from (node[{n_name}], opID[{n_opID}], PE[{n_pe}]) to' \
                                      f'(node[{ch_name}], opID[{ch_opID}], PE[{ch_pe}])')
                    break
                else:
                    # Make sure all destinations are unique within the blk_path_tracker list
                    for port in range(len(blk_path_tracker)):
                        rel_path_tracker = [int(dest%self.cgra_ctxt.cgra_block_size) for dest in blk_path_tracker[port]]
                        for path in rel_path_tracker:
                            path_cnt = 0
                            for comp in rel_path_tracker:
                                if (path == comp):
                                    path_cnt += 1
                            if (path_cnt >= 2):
                                routed = False
                                self.logger.error(f'{fn_name} ||| Found repeated destination[{path}] in block[{n_blk_sel}] blk_path_tracker[{port}] = {blk_path_tracker[port]} | rel_path_tracker[{port}] = {rel_path_tracker}')
                                break
                        if (not routed):
                            break
                    if (not routed):
                        break
        return routed

    # Run router on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt=None) -> bool:
        fn_name = router.run.__name__
        # Setup path-tracker
        self.mapper_ctxt.reset_trackers()
        data_path_tracker = self.mapper_ctxt.data_path_tracker
        data_source_tracker = self.mapper_ctxt.data_source_tracker
        pred_path_tracker = self.mapper_ctxt.pred_path_tracker
        pred_source_tracker = self.mapper_ctxt.pred_source_tracker
        # Get dot nodes and edges
        dnodes = dot_ctxt.dot_nodes
        dedges = dot_ctxt.dot_edges
        routed = False
        for n in dnodes:
            n_rank = int(n.get('rank'))
            n_name = n.get_name()
            n_opID = n.get('opID')
            n_children = dot_ctxt.get_children(n_name)
            n_blk = n_rank % self.cgra_ctxt.cgra_blocks
            n_pe = self.mapper_ctxt.node2pe[n_name]
            # Find shadow equivalents
            n_shadow_blk = self.mapper_ctxt.get_shadow_block(n_blk)
            t_ln_pe = self.mapper_ctxt.get_localPE_id(n_pe)
            n_shadow_pe = self.mapper_ctxt.get_globalPE_id(t_ln_pe, n_shadow_blk)
            self.logger.debug(f'{fn_name} ||| Routing (node[{n_name}], opID[{n_opID}]) placed @ PE[{n_pe}] in block[{n_blk}]')
            # For a given node, its opID(s) must be mapped to the PE outputs
            # housing the opcode(s). According to the availability of paths
            # towards its children. Start by choosing a free output.
            # Find destination PE using child's opID. Check if destination 
            # exists in path_tracker. If it doesnt, map opID to the chosen port
            # and insert destination PE into path-tracker. Else, move on the the 
            # next port and repeat the process till a suitable port is found.
            
            # Generic Sanity checks
            num_children = len(n_children)
            if (num_children > self.cgra_ctxt.cgra_radix):
                self.logger.error(f'{fn_name} ||| Fanout of node[{n_name}] with opID[{n_opID}], greater than available ports !')
                break
            # Route node paths
            routed = self.route_node_path(dedges, n_name, n_opID, n_pe, n_shadow_pe, n_children, n_blk, n_shadow_blk, data_path_tracker, data_source_tracker, pred_path_tracker, pred_source_tracker)
            if (not routed):
                break
        self.logger.info(f'{fn_name} ||| Routing Phase-1: Complete')
        # Collapse shadow PEs meta into physical region
        self.mapper_ctxt.condense_pe_meta()
        # Make src-dest pairs with local_PE_ids for Benes router
        self.logger.debug(f'{fn_name} ||| Tracker info: \n data_src_tracker = {data_source_tracker} \n data_path_tracker = {data_path_tracker} \n pred_src_tracker = {pred_source_tracker} \n pred_path_tracker = {pred_path_tracker}')
        self.mapper_ctxt.make_route_pairs(data_source_tracker, data_path_tracker, predicate=False)
        self.mapper_ctxt.make_route_pairs(pred_source_tracker, pred_path_tracker, predicate=True)
        self.mapper_ctxt.print_data()
        # Start Benes router
        if (routed):
            for blk in range(self.cgra_ctxt.cgra_blocks):
                path_cnt = self.cgra_ctxt.cgra_radix + 1                # +1 for predicate path
                for path in range(path_cnt):
                    # Get corresponding path's permutation
                    perm = self.mapper_ctxt.pred_route_pairs[blk][0] if (path == self.cgra_ctxt.cgra_radix) else self.mapper_ctxt.data_route_pairs[blk][path]
                    self.benes.reset_benes()
                    path_scbs = self.benes.run(perm)
                    if (path_scbs is not None):
                        self.logger.info(f'{fn_name} ||| Routing Phase-2, Block[{blk}], Path[{path}]: Complete')
                        if (path == self.cgra_ctxt.cgra_radix):
                            self.mapper_ctxt.pred_path_scbs[blk][0] = path_scbs
                        else:
                            self.mapper_ctxt.data_path_scbs[blk][path] = path_scbs
                    else:
                        self.logger.error(f'{fn_name} ||| Routing Phase-2: FAILED \n Benes routing failed for block[{blk}], path[{path}], permutation = {perm}')
                        routed = False
                        return routed
        pass_fail_flag = 'PASSED' if (routed) else 'FAILED'
        self.logger.info(f'{fn_name} ||| Routing: {pass_fail_flag}')
        return routed

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
    mapper_ctxt = mapper_context(cgra_ctxt.cgra_radix, cgra_ctxt.cgra_block_size, cgra_ctxt.cgra_radix, log_level=logging.DEBUG)
    # Create and load placer
    plcr = placer(log_level=logging.DEBUG)
    plcr.load_cgra_context(cgra_ctxt)
    # Create and load router
    rtr = router(log_level=logging.DEBUG)
    rtr.load_cgra_context(cgra_ctxt)
    # Create Benes
    ben = benes(cgra_ctxt.cgra_block_size, log_level=logging.DEBUG)

    # Perform standard CGRA sanity checks
    cgra_size = cgra_ctxt.cgra_size
    cgra_pe_cnt = 0
    for blk_deet in cgra_ctxt.cgra_cfg['CGRA']['composition']:
        for k in blk_deet.keys():
            cgra_pe_cnt += blk_deet[k]
    if (cgra_pe_cnt != cgra_size):
        print (f'{fn_name} ||| CGRA config: CGRA_size and composition mismatch !')
        return -1
    # Start placer
    plcr_pass = plcr.run(dot_ctxt, mapper_ctxt)
    if (plcr_pass):
        mapper_ctxt.print_data()
        # Start router
        rtr_pass = rtr.run(dot_ctxt, mapper_ctxt)
        if (rtr_pass):
            mapper_ctxt.print_data()

if __name__ == "__main__":
    _test()
