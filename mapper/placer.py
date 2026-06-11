
import logging
import os
import copy
#import argparse
#from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
#from contexts.mapper_context import mapper_context

class placer:

    def __init__ (self, cgra_context=None, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
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
        self.cgra_ctxt = None
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
            ret_val = True
        return ret_val
    
    def assert_routing_opcode (self, node_opcode: str) -> bool:
        ret_val = False
        for rop in self.cgra_ctxt.pe_cfg['OPdef']:
            if (node_opcode == rop['name'] and rop['type'] == 'route'):
                ret_val = True
                break
        return ret_val

    def find_candidate_pe (self, pe_list: list, pe_info: dict, target_opcode_cost: list, route_opcode: bool, shadow_pe_list: list) -> tuple:
        fn_name = placer.find_candidate_pe.__name__
        target_pe_ID = None
        target_pe_type = None
        target_pe_opGroup = None
        discard_locs = []
        cost_satisfied = lambda p_info, t_cost: True if (p_info[1][0] >= t_cost[0] and p_info[1][1] >= t_cost[1]) else False
        if (route_opcode):
            for p, info in enumerate(pe_info):
                if (cost_satisfied(info, target_opcode_cost)):
                    target_pe_ID = p
                    break
        else:
            for i, cand_pe in enumerate(pe_list):
                cand_pe_ID = cand_pe[0]
                cand_pe_opGroup = cand_pe[1]
                cand_pe_type = pe_info[cand_pe_ID][0][0]
                # Check if candidate PE can accomodate the target opcode cost
                if (cost_satisfied(pe_info[cand_pe_ID], target_opcode_cost)):
                    target_pe_ID = cand_pe_ID
                    target_pe_type = cand_pe_type
                    target_pe_opGroup = cand_pe_opGroup
                    break
                else:
                    # Mark PE for removal from candidate list
                    discard_locs.append(i)
            # Discard PEs marked for removal
            for pid in discard_locs:
                linked = pe_list[pid][2]
                if (linked):
                    # Delete pe from shadow block too
                    del shadow_pe_list[pid]
                del pe_list[pid]
        return (target_pe_ID, target_pe_type, target_pe_opGroup)
    
    def update_pe_cost (self, trt_pe_ID: int, trt_opcode_cost: list, blk_pe_info: list) -> None:
        # Reflect the target_opcode_cost in blk_pe_info
        blk_pe_info[trt_pe_ID][1][0] -= trt_opcode_cost[0]
        blk_pe_info[trt_pe_ID][1][1] -= trt_opcode_cost[1]

    def remove_target_pe (self, trt_pe_ID: int, trt_pe_type: str, trt_pe_opGroup: str, blk_avail_pe: dict, shadow_blk_avail_pe: dict) -> None:
        fn_name = placer.remove_target_pe.__name__
        # Remove PEs from all opGroups using target_pe_ID/opGroup in blk_avail_pe
        #self.logger.debug(f'{fn_name} ||| New blk_pe_info after mutation @ [{trt_pe_ID}]: {blk_pe_info}')
        # Get opGroup Keys to search for in blk_avail_pe
        op_keys = self.cgra_ctxt.pe_cfg[trt_pe_type]['opGroup'][trt_pe_opGroup]
        #self.logger.debug(f'{fn_name} ||| target_pe_type = {trt_pe_type}')
        #self.logger.debug(f'{fn_name} ||| Searching blk_avail_pe for keys = {op_keys}')
        # Remove target from blk_avail_pe
        #for k in op_keys:
        for k in op_keys:
            for i, pd in enumerate(blk_avail_pe[k]):
                if (pd[0] == trt_pe_ID and pd[1] == trt_pe_opGroup):
                    linked = pd[2]
                    if (linked == 1):
                        del shadow_blk_avail_pe[k][i]
                    del blk_avail_pe[k][i]
    
    # Run placer on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt=None, mapper_ctxt=None) -> bool:
        fn_name = placer.run.__name__
        # Make a copy of avail_pe and pe_info from cgra_ctxt
        avail_pe = copy.deepcopy(self.cgra_ctxt.avail_pe)
        pe_info = copy.deepcopy(self.cgra_ctxt.pe_info)
        # Get dot nodes
        dnodes = dot_ctxt.dot_nodes
        total_nodes = len(dnodes)
        nodes_placed = 0
        self.logger.info(f'{fn_name} ||| Starting Placer run: Total nodes = {total_nodes}')
        placed = False
        for n in dnodes:
            # Get node's name, opID, opcode, rank and compute cgra_block
            n_name = n.get_name()
            n_opID = n.get('opID')
            n_opcode = n.get('opcode')
            n_rank = int(n.get('rank'))
            n_blk = n_rank % self.cgra_ctxt.cgra_blocks
            n_shadow_blk = mapper_ctxt.get_shadow_block(n_blk)
            # Find a free PE from avail_pe
            blk_avail_pe = avail_pe[n_blk]
            blk_pe_info = pe_info[n_blk]
            blk_candidate_list = blk_avail_pe.get(n_opcode, None)
            shadow_blk_avail_pe = avail_pe[n_shadow_blk]
            shadow_blk_candidate_list = shadow_blk_avail_pe.get(n_opcode, None)
            # Check if this is a routing operation
            route_opcode = self.assert_routing_opcode(n_opcode)
            if (blk_candidate_list is None and not route_opcode):
                self.logger.error(f'{fn_name} ||| PE_opcode[{n_opcode}] of node[{n_name}] not supported !')
                break
            elif (blk_candidate_list is not None and len(blk_candidate_list) == 0 and not route_opcode):
                self.logger.error(f'{fn_name} ||| No candidate PE available for PE_opcode[{n_opcode}] of node[{n_name}] !')
                break
            self.logger.debug(f'{fn_name} ||| node = {n_name}, opID = {n_opID}, opcode = {n_opcode}, opCost = {self.cgra_ctxt.opcode_cost[n_opcode]}, block = {n_blk}')
            self.logger.debug(f'{fn_name} ||| blk_pe_info[{n_blk}] before mutation: {blk_pe_info}')
            self.logger.debug(f'{fn_name} ||| blk_avail_pe[{n_blk}] before mutation: {blk_avail_pe}')
            # Peek at candidate PE's pe_ID, opGroup, and required-cost of opcode
            target_opcode_cost = self.cgra_ctxt.opcode_cost[n_opcode]
            target_pe_ID, target_pe_type, target_pe_opGroup = self.find_candidate_pe(blk_candidate_list, blk_pe_info, target_opcode_cost, route_opcode, shadow_blk_candidate_list)
            if (target_pe_ID is None):
                self.logger.error(f'{fn_name} ||| No target PE found for PE_opcode[{n_opcode}] of node[{n_name}], due to lack of PE ports !')
                break
            # Place node in target PE by creating an entry in mapper_context's pe_meta
            # NOTE: Mapper context stores all relevant data using global_peID
            global_target_pe_ID = mapper_ctxt.get_globalPE_id(target_pe_ID, n_blk)
            mapper_ctxt.add_node2pe(n_name, global_target_pe_ID)
            mapper_ctxt.add_pe_meta_opcode(global_target_pe_ID, n_opcode, n_opID)
            self.logger.debug(f'{fn_name} ||| Successfully placed node[{n_name}], opID[{n_opID}], opcode[{n_opcode}] @ target PE[{global_target_pe_ID}]')
            # Update PE costs and Remove target pe from list(s) of candidate pe(s)
            self.update_pe_cost(target_pe_ID, target_opcode_cost, blk_pe_info)
            if (not route_opcode):
                self.remove_target_pe(target_pe_ID, target_pe_type, target_pe_opGroup, blk_avail_pe, shadow_blk_avail_pe)
                self.logger.debug(f'{fn_name} ||| New blk_avail_pe[{n_blk}] after mutation: {blk_avail_pe} \n New shadow_blk_pe[{n_shadow_blk}] after mutation: {shadow_blk_avail_pe}')
            self.logger.debug(f'{fn_name} ||| New blk_pe_info[{n_blk}] after mutation @ [{target_pe_ID}]: {blk_pe_info}')
            self.logger.debug(f'{fn_name} ||| node[{n_name}], opID[{n_opID}] with opcode[{n_opcode}]; placed @ blk[{n_blk}], peID[{target_pe_ID}], global_peID = {global_target_pe_ID}')
            # Update tracker
            nodes_placed += 1
        placed = True if (nodes_placed == total_nodes) else False
        pass_fail_flag = 'PASSED' if (placed) else 'FAILED'
        self.logger.info(f'{fn_name} ||| End of Placer run: Total nodes = {len(dnodes)} | Nodes placed = {nodes_placed} | Placement: {pass_fail_flag}')
        return placed
    
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
    plcr.load_cgra_context(cgra_ctxt)

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
    plcr.run(dot_ctxt, mapper_ctxt)
    # Print mapper context
    mapper_ctxt.print_data()

if __name__ == "__main__":
    _test()
