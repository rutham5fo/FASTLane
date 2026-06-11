
import logging
import os
#import argparse
#from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
#from contexts.mapper_context import mapper_context
#from mapper.placer import placer
from mapper.benes import benes

class router:

    def __init__ (self, cgra_context=None, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
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
        self.benes = None
        self.max_find_port_recursion = 0
        if (cgra_context is not None):
            self.load_cgra_context(cgra_context)
    
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
    
    def load_cgra_context (self, cgra_context=None) -> bool:
        ret_val = False
        if (cgra_context is not None):
            self.cgra_ctxt = cgra_context
            self.max_find_port_recursion = self.cgra_ctxt.cgra_radix**2
            # Create Benes
            self.benes = benes(self.cgra_ctxt.cgra_block_size, log_level=logging.DEBUG)
            ret_val = True
        return ret_val
    
    def find_valid_port (self, n_pe: int, ch_pe: int, child_id: int, n_opID: int, n_out_opID: list, ch_in_opID: list, blk_path_tracker: list, 
                         blk_src_tracker: list, attempted_ports: list, port_children: list, recursion_cnt: int) -> tuple:
        fn_name = router.find_valid_port.__name__
        # Find a port that does not contain the destination PE in its path-set
        routed = False
        possible_ports = []
        if (recursion_cnt > self.max_find_port_recursion):
            return
        for i in range(len(n_out_opID)):
            self.logger.debug(f'{fn_name} ||| FVP iteration[{recursion_cnt}] | n_pe = {n_pe}, n_opID = {n_opID}, child_id = {child_id}, ch_pe = {ch_pe} | n_out_opID = {n_out_opID}, ch_in_opID = {ch_in_opID}')
            if (ch_pe is None):
                self.logger.error(f'{fn_name} ||| Function call with non-existent child PE !')
                return
            ch_exists_inPath = ch_pe in blk_path_tracker[i]
            port_attempted = i in attempted_ports[child_id]
            if (not ch_exists_inPath and not port_attempted):
                # If port is free, consume it
                if (n_out_opID[i] is None):
                    # Attach opID to this port in parent and child
                    n_out_opID[i] = n_opID
                    ch_in_opID[i] = n_opID
                    # Add this child PE to the list of port children
                    port_children[i] = (child_id, ch_pe)
                    # Add path in block's path&source-trackers
                    blk_path_tracker[i].append(ch_pe)
                    blk_src_tracker[i].append(n_pe)
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
            aux_child_id = port_children[prt][0]
            aux_ch_pe = port_children[prt][1]
            # Place current edge in this possible_port, displacing the existing edge
            n_out_opID[prt] = n_opID
            ch_in_opID[prt] = n_opID
            # Update tracking info
            port_children[prt] = (child_id, ch_pe)
            blk_tracker_loc = [loc for loc in range(len(blk_path_tracker[prt])) if blk_path_tracker[prt][loc] == aux_ch_pe][0]
            del blk_path_tracker[prt][blk_tracker_loc]
            del blk_src_tracker[prt][blk_tracker_loc]
            blk_path_tracker[prt].append(ch_pe)
            blk_src_tracker[prt].append(n_pe)
            attempted_ports[child_id].append(prt)
            # Recursive call with aux_n_opID and aux_ch_pe to place displaced edge
            recursion_cnt += 1
            routed = self.find_valid_port(n_pe, aux_ch_pe, aux_child_id, aux_n_opID, n_out_opID, ch_in_opID, blk_path_tracker, 
                                          blk_src_tracker, attempted_ports, port_children, recursion_cnt)
        return routed
    
    # Run router on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt=None, mapper_ctxt=None) -> bool:
        fn_name = router.run.__name__
        # Setup path-tracker
        # A path is a Benes connection set from Block A to opposing Block B
        # Each output port from a node sits on a different path.
        # Path_tracker holds the destination PE of an edge, while source_tracker holds the corresponding source
        path_tracker = [[[] for _ in range(self.cgra_ctxt.cgra_radix)] for _ in range(self.cgra_ctxt.cgra_blocks)]
        source_tracker = [[[] for _ in range(self.cgra_ctxt.cgra_radix)] for _ in range(self.cgra_ctxt.cgra_blocks)]
        # Get dot nodes
        dnodes = dot_ctxt.dot_nodes
        routed = False
        for n in dnodes:
            exit_l0 = False
            n_rank = int(n.get('rank'))
            n_name = n.get_name()
            n_opID = n.get('opID')
            _, n_children = dot_ctxt.get_children(n_name)
            n_blk = n_rank % self.cgra_ctxt.cgra_blocks
            n_pe = mapper_ctxt.node2pe[n_name]
            # Find shadow equivalents
            n_shadow_blk = mapper_ctxt.get_shadow_block(n_blk)
            t_ln_pe = mapper_ctxt.get_localPE_id(n_pe)
            n_shadow_pe = mapper_ctxt.get_globalPE_id(t_ln_pe, n_shadow_blk)
            # The blk_sel values for src/path-trackers depend on which direction
            # the edge is traveling in. All forward paths will be in the same 
            # region as current block. But, all reverse edges will be in the shadow region.
            n_out_opID = mapper_ctxt.pe_meta[n_pe]['out_opID']
            blk_path_tracker = path_tracker[n_blk]
            blk_src_tracker = source_tracker[n_blk]
            self.logger.debug(f'{fn_name} ||| Routing (node[{n_name}], opID[{n_opID}]) placed @ PE[{n_pe}]')
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
            
            # Reaching this point means there is atleast one free out_port in parent node
            attempted_ports = [[] for _ in range(num_children)]
            for cid, ch in enumerate(n_children):
                ch_rank = int(ch.get('rank'))
                ch_name = ch.get_name()
                ch_opID = ch.get('opID')
                ch_blk = ch_rank % self.cgra_ctxt.cgra_blocks
                ch_pe = mapper_ctxt.node2pe[ch_name]
                ch_in_opID = mapper_ctxt.pe_meta[ch_pe]['in_opID']
                port_children = [(None, None) for _ in range(self.cgra_ctxt.cgra_radix)]   # [(child_node_id, child_PE_id)]
                routed = False
                recursion_cnt = 0

                # !!! NOTE: Untested Feature BEGIN !!!
                # The blk_sel values for src/path-trackers depend on which direction
                # the edge is traveling in. All forward paths will be in the same 
                # region as current block. But, all reverse edges will be in the shadow region.
                # Except the special cases checked for below, which always go through current region.
                if (ch_blk > n_blk or n_blk == 0 or n_blk == self.cgra_ctxt.cgra_phy_blocks-1 or (ch_blk == 0 and n_blk == self.cgra_ctxt.cgra_blocks-1)):
                    # Go through current region's source resources
                    n_out_opID = mapper_ctxt.pe_meta[n_pe]['out_opID']
                    blk_path_tracker = path_tracker[n_blk]
                    blk_src_tracker = source_tracker[n_blk]
                else:
                    # Go through shadow region's source resources
                    n_out_opID = mapper_ctxt.pe_meta[n_shadow_pe]['out_opID']
                    blk_path_tracker = path_tracker[n_shadow_blk]
                    blk_src_tracker = source_tracker[n_shadow_blk]
                # Source node sanity check
                if (not None in n_out_opID):
                    self.logger.error(f'{fn_name} ||| No un-mapped ports available for node[{n_name}] with opID[{n_opID}], placed in PE[{n_pe}] !')
                    exit_l0 = True
                    break
                # !!! NOTE: Untested Feature END !!!

                # Route n_pe->ch_pe edge
                self.logger.debug(f'{fn_name} ||| Routing Edge from src_PE[{n_pe}] -> dest_PE[{ch_pe}]')
                # Find a port that does not contain the destination PE in its path-set
                routed = self.find_valid_port(n_pe, ch_pe, cid, n_opID, n_out_opID, ch_in_opID, blk_path_tracker, blk_src_tracker, 
                                                             attempted_ports, port_children, recursion_cnt)
                self.logger.debug(f'{fn_name} ||| Routed = {routed} | Result: src_PE[{n_pe}], src_Node[{n_name}], out_opID = {n_out_opID}; dest_PE[{ch_pe}], dest_Node[{ch_name}], ch_in_opID = {ch_in_opID}')
                if (not routed):
                    self.logger.error(f'{fn_name} ||| There is no valid route from (node[{n_name}], opID[{n_opID}], PE[{n_pe}]) to' \
                                      f'(node[{ch_name}], opID[{ch_opID}], PE[{ch_pe}])')
                    break
            if (exit_l0):
                break
        self.logger.info(f'{fn_name} ||| Routing Phase-1: Complete')
        # Collapse shadow PEs meta into physical region
        mapper_ctxt.condense_pe_meta()
        # Make src-dest pairs with local_PE_ids for Benes router
        mapper_ctxt.make_route_pairs(source_tracker, path_tracker)
        # Start Benes router
        if (routed):
            for blk in range(self.cgra_ctxt.cgra_blocks):
                for path in range(self.cgra_ctxt.cgra_radix):
                    # Get corresponding path's permutation
                    perm = mapper_ctxt.route_pairs[blk][path]
                    self.benes.reset_benes()
                    path_scbs = self.benes.run(perm)
                    if (path_scbs is not None):
                        self.logger.info(f'{fn_name} ||| Routing Phase-2, Block[{blk}], Path[{path}]: Complete')
                        mapper_ctxt.path_scbs[blk][path] = path_scbs
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
