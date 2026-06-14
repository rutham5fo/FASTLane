
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
    
    def assert_routing_opcode (self, node_opcode: str) -> bool:
        ret_val = False
        for rop in self.cgra_ctxt.pe_cfg['Routing']:
            if (node_opcode == rop['name']):
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
    
    def update_pe_routing_resource (self, block, trt_pe_ID: int, trt_pe_routing_cost: list, blk_pe_info: list) -> None:
        fn_name = placer.update_pe_routing_resource.__name__
        self.logger.debug(f'{fn_name} ||| blk_pe_info[{block}] before mutation: {blk_pe_info}')
        # Reflect the target_opcode_cost in blk_pe_info
        blk_pe_info[trt_pe_ID][1][0][0] -= trt_pe_routing_cost[0][0]
        blk_pe_info[trt_pe_ID][1][0][1] -= trt_pe_routing_cost[0][1]
        blk_pe_info[trt_pe_ID][1][1][0] -= trt_pe_routing_cost[1][0]
        blk_pe_info[trt_pe_ID][1][1][1] -= trt_pe_routing_cost[1][1]
        self.logger.debug(f'{fn_name} ||| blk_pe_info[{block}] after mutation: {blk_pe_info}')

    def is_pe_routable (self, block, target_pe_ID: int, in_edges: list, out_edges: list, blk_pe_info: list) -> tuple[int|None, list[list[int, int]]]:
        fn_name = placer.is_pe_routable.__name__
        trt_pe_ID = None
        trt_pe_routing_cost = None
        t_pe_routing_cost = [[0, 0], [0, 0]]                # [[data_in, data_out], [pred_in, pred_out]]
        # Find if the target PE satisfies the in/out routing conditions from pe_info
        trt_pe_routing_resources = blk_pe_info[target_pe_ID][1]
        # Find input cost
        for ie in in_edges:
            if (ie.get('data') is not None):
                t_pe_routing_cost[0][0] += 1
            if (ie.get('predicate') is not None):
                t_pe_routing_cost[1][0] += 1
        # Find output cost
        for oe in out_edges:
            if (oe.get('data') is not None):
                t_pe_routing_cost[0][1] += 1
            if (oe.get('predicate') is not None):
                t_pe_routing_cost[1][1] += 1
        # Check if routable
        if (trt_pe_routing_resources[0][0] >= t_pe_routing_cost[0][0] and trt_pe_routing_resources[0][1] >= t_pe_routing_cost[0][1] \
            and trt_pe_routing_resources[1][0] >= t_pe_routing_cost[1][0] and trt_pe_routing_resources[1][1] >= t_pe_routing_cost[1][1]):
            trt_pe_routing_cost = t_pe_routing_cost
            trt_pe_ID = target_pe_ID
        else:
            self.logger.debug(f'{fn_name} ||| Target PE[{target_pe_ID}] in block[{block}] lacks routing resources | Required cost = {t_pe_routing_cost}; Available = {trt_pe_routing_resources}')
        return (trt_pe_ID, trt_pe_routing_cost)
    
    def remove_target_pe (self, block, trt_pe_ID: int, trt_pe_type: str, trt_pe_opGroup: str, blk_avail_pe: dict, shadow_blk_avail_pe: dict) -> None:
        fn_name = placer.remove_target_pe.__name__
        self.logger.debug(f'{fn_name} ||| blk_avail_pe[{block}] before mutation: {blk_avail_pe}')
        # Remove PEs from all opGroups using target_pe_ID/opGroup in blk_avail_pe
        #self.logger.debug(f'{fn_name} ||| New blk_pe_info after mutation @ [{trt_pe_ID}]: {blk_pe_info}')
        # Get opGroup Keys to search for in blk_avail_pe
        op_keys = self.cgra_ctxt.pe_cfg[trt_pe_type]['opGroup'][trt_pe_opGroup]
        #self.logger.debug(f'{fn_name} ||| target_pe_type = {trt_pe_type}')
        #self.logger.debug(f'{fn_name} ||| Searching blk_avail_pe for keys = {op_keys}')
        # Remove target from blk_avail_pe
        for k in op_keys:
            for i, pd in enumerate(blk_avail_pe[k]):
                if (pd[0] == trt_pe_ID and pd[1] == trt_pe_opGroup):
                    linked = pd[2]
                    if (linked == 1):
                        del shadow_blk_avail_pe[k][i]
                    del blk_avail_pe[k][i]
        self.logger.debug(f'{fn_name} ||| blk_avail_pe[{block}] after mutation: {blk_avail_pe}')

    def find_candidate_pe (self, node, parents, children, edges, avail_pe: dict, pe_info: list) -> tuple[int, int]:
        fn_name = placer.find_candidate_pe.__name__
        trt_pe_ID = None
        trt_pe_type = None
        trt_pe_opGroup = None
        trt_pe_context = None
        trt_pe_routing_cost = None
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
        # Get node attributes to search for
        search_attr = self.cgra_ctxt.pe_cfg['Attributes']
        # First find how many input and output data-edges the node utilizes
        fin_edges, fout_edges = self.get_op_edges(n_name, parents, children, edges)
        # Check if opcode is of routing type
        routing = self.assert_routing_opcode(n_opcode)
        # Get corresponding list of candidate PEs from avail_pe
        cand_pe_list = blk_pe_info if (routing) else avail_pe[n_opcode]
        # List to keep track of used opGroups
        used_opGroups = []
        if (len(cand_pe_list) == 0):
            self.logger.error(f'{fn_name} ||| No candidate PE available to map opcode[{n_opcode}] from node[{n_name}]')
        else:
            for cpid, cand_pe in enumerate(cand_pe_list):
                lp_abort = False
                cand_pe_id = cpid if (routing) else cand_pe[0]
                cand_pe_type = None if (routing) else cand_pe[1]
                cand_pe_context = None if (routing) else cand_pe[2]
                cand_pe_routing_cost = None
                # Check if candidate PE supports the target opcode
                #if (self.is_opcode_supported(n_opcode, cand_pe_type, cand_pe_opGroup) and t_opType != 'route'):
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
                            if (t_opGroup == cand_pe_opGroup or t_opGroup is None):
                                self.logger.error(f'{fn_name} ||| Cannot map two opcodes[{n_opcode}, {t_opcode}] into the same opGroup[{t_opGroup}] of the same candidate[{cand_pe_id}]')
                                used_opGroups = None
                                lp_abort = True
                                break
                            used_opGroups.append(t_opGroup)
                if (lp_abort):
                    break
                # Check if there is sufficient in/out data_paths from target_PE
                cand_pe_id, cand_pe_routing_cost = self.is_pe_routable(n_blk, cand_pe_id, fin_edges, fout_edges, blk_pe_info)
                if (cand_pe_id is None):
                    continue
                self.logger.debug(f'{fn_name} ||| Found candidate PE[{cand_pe_id}], that supports opcode[{n_opcode}] from node[{n_name}] | target_pe_id = {trt_pe_ID}')
                trt_pe_ID = cand_pe_id
                trt_pe_type = cand_pe_type
                trt_pe_opGroup = used_opGroups
                trt_pe_context = cand_pe_context
                trt_pe_routing_cost = cand_pe_routing_cost
                break
        if (trt_pe_ID is not None):
            if (trt_pe_opGroup is not None):
                for opG in trt_pe_opGroup:
                    # If a valid candidate is available, remove it from avail_pe list
                    self.remove_target_pe(n_blk, trt_pe_ID, trt_pe_type, opG, blk_avail_pe, shadow_blk_avail_pe)
            # Update PE routing resources
            self.update_pe_routing_resource(n_blk, trt_pe_ID, trt_pe_routing_cost, blk_pe_info)
        else:
            self.logger.error(f'{fn_name} ||| Failed to place node[{n_name}] with opcode[{n_opcode}] as suitable candidate not found')
        return (trt_pe_ID, trt_pe_context)
    
    # Run placer on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt=None) -> bool:
        fn_name = placer.run.__name__
        # Make a copy of avail_pe and pe_info from cgra_ctxt
        avail_pe = copy.deepcopy(self.cgra_ctxt.avail_pe)
        pe_info = copy.deepcopy(self.cgra_ctxt.pe_info)
        # Get dot nodes
        dnodes = dot_ctxt.dot_nodes
        dedges = dot_ctxt.dot_edges
        total_nodes = len(dnodes)
        nodes_placed = 0
        self.logger.info(f'{fn_name} ||| Starting Placer run: Total nodes = {total_nodes}')
        placed = False
        for n in dnodes:
            n_name = n.get_name()
            n_children = dot_ctxt.get_children(n.get_name())
            n_parents = dot_ctxt.get_parents(n.get_name())
            n_opcode = n.get('opcode')
            n_opID = n.get('opID')
            n_rank = int(n.get('rank'))
            # The virtual blocks (cgra_ctxt.cgra_blocks) cover the whole triangle wave.
            # Hence its ok to get a nodes block using rank and virtual blocks.
            n_blk = n_rank % self.cgra_ctxt.cgra_blocks
            target_pe_ID = None
            self.logger.debug(f'{fn_name} ||| node = {n_name}, opID = {n_opID}, opcode = {n_opcode}, block = {n_blk}')
            # Get candidate PE
            target_pe_ID, _ = self.find_candidate_pe(n, n_parents, n_children, dedges, avail_pe, pe_info)
            if (target_pe_ID is None):
                self.logger.error(f'{fn_name} ||| No target PE found for PE_opcode[{n_opcode}] of node[{n_name}], due to lack of PE ports !')
                break
            # Place node in target PE by creating an entry in mapper_context's pe_meta
            # NOTE: Mapper context stores all relevant data using global_peID
            global_target_pe_ID = self.mapper_ctxt.get_globalPE_id(target_pe_ID, n_blk)
            self.mapper_ctxt.add_node2pe(n_name, global_target_pe_ID)
            self.mapper_ctxt.add_pe_meta_opcode(global_target_pe_ID, n_opcode, n_opID)
            self.logger.debug(f'{fn_name} ||| Successfully placed node[{n_name}], opID[{n_opID}], opcode[{n_opcode}] @ target PE[{global_target_pe_ID}]')
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
