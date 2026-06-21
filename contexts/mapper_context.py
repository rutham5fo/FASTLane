
import logging
import os

class mapper_context:

    def __init__ (self, cgra_blocks: int, cgra_block_size: int, cgra_radix: int, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
        fn_name = mapper_context.__init__.__name__
        # Setup logger
        self.logger_name = None
        self.logger = None
        if (logger_name):
            self.logger_name = logger_name
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger_name = self.__class__.__name__
            self.logger = self.log_setup(self.logger_name, log_level, log_dir)
        # PE metadata
        self.cgra_blocks = cgra_blocks                  # Virtual blocks -> 2 * (cgra_ctxt.cgra_phy_blocks - 1)
        self.cgra_block_size = cgra_block_size
        self.cgra_radix = cgra_radix
        # Mapper uses global_peID for keys (global_peID = cgra_block_size*block_number+local_peID)
        self.node2pe = {}                                                                           # Populated by placer
        self.pe_meta = {}                                                                           # Populated by placer
        self.data_route_pairs = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]  # Populated by router | [[[(src_pe, dest_pe)]]]
        self.pred_route_pairs = [[[] for _ in range(1)] for _ in range(self.cgra_blocks)]
        self.data_path_scbs = [[None for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]    # Populated by benes
        self.pred_path_scbs = [[None for _ in range(1)] for _ in range(self.cgra_blocks)]
        # A path is a Benes connection set from Block A to opposing Block B
        # Each output port from a node sits on a different path.
        # Path_tracker holds the destination PE of an edge, while source_tracker holds the corresponding source
        self.data_path_tracker = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]
        self.data_source_tracker = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]
        self.pred_path_tracker = [[[] for _ in range(1)] for _ in range(self.cgra_blocks)]
        self.pred_source_tracker = [[[] for _ in range(1)] for _ in range(self.cgra_blocks)]

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
    
    def reset_trackers (self) -> None:
        fn_name = mapper_context.reset_trackers.__name__
        self.data_path_tracker = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]
        self.data_source_tracker = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]
        self.pred_path_tracker = [[[] for _ in range(1)] for _ in range(self.cgra_blocks)]
        self.pred_source_tracker = [[[] for _ in range(1)] for _ in range(self.cgra_blocks)]
    
    def reset_port_meta (self, gpid) -> None:
        fn_name = mapper_context.reset_port_meta.__name__
        for prt in range(self.cgra_radix):
            self.pe_meta[gpid]['data_port_meta'][prt][1] = []
        self.pe_meta[gpid]['pred_port_meta'][0][1] = []

    def get_globalPE_id (self, pid: int, block: int) -> int:
        fn_name = mapper_context.get_globalPE_id.__name__
        # The absolute PE_id cannot be greater than self.cgra_blocks/2 since thats the number of physical blocks
        # The PEs in the shadow blocks are simply the second TDM channel of physical blocks.
        # But the global PE id can be greater than self.cgra_blocks/2 to accomodate the shadow region
        gpid = self.cgra_block_size * block + pid
        return gpid
    
    def get_localPE_id (self, gpid: int) -> int:
        fn_name = mapper_context.get_localPE_id.__name__
        lpid = int(gpid%self.cgra_block_size)
        return lpid
    
    def get_block (self, gpid: int) -> int:
        fn_name = mapper_context.get_block.__name__
        block = int(gpid/self.cgra_block_size)
        return block
    
    def get_node_region (self, block: int) -> int:
        fn_name = mapper_context.get_node_region.__name__
        phy_cgra_blocks = int(self.cgra_blocks/2)+1
        n_region = -1 if (block >= phy_cgra_blocks) else 1
        return n_region
    
    def get_shadow_block (self, block: int) -> int:
        fn_name = mapper_context.get_shadow_block.__name__
        shadow_blk = 0 if (block == 0) else self.cgra_blocks - block
        return shadow_blk
    
    def get_shadow_pe (self, global_pe_id: int) -> int:
        fn_name = mapper_context.get_shadow_pe.__name__
        block = self.get_block(global_pe_id)
        shadow_block = self.get_shadow_block(block)
        local_pid = self.get_localPE_id(global_pe_id)
        shadow_gpid = self.get_globalPE_id(local_pid, shadow_block)
        return shadow_gpid
    
    def assert_forward_edge (self, src_block: int, dest_block: int) -> bool:
        fn_name = mapper_context.assert_forward_edge.__name__
        phy_cgra_blocks = int(self.cgra_blocks/2)+1
        abs_src_blk = src_block if (src_block < phy_cgra_blocks) else self.get_shadow_block(src_block)
        abs_dest_blk = dest_block if (dest_block < phy_cgra_blocks) else self.get_shadow_block(dest_block)
        abs_edge_dir = -1 if (abs_dest_blk - abs_src_blk < 0) else 1
        src_node_region = self.get_node_region(src_block)
        rel_edge_dir = abs_edge_dir * src_node_region
        forward_edge = True if (rel_edge_dir > 0) else False
        #self.logger.debug(f'{fn_name} ||| phy_cgra_blocks = {phy_cgra_blocks} | src_blk = {src_block}, dest_blk = {dest_block}, abs_src_blk = {abs_src_blk}, abs_dest_blk = {abs_dest_blk}, abs_edge_dir = {abs_edge_dir} \n src_node_region = {src_node_region}, rel_edge_dir = {rel_edge_dir}, forward_edge = {forward_edge}')
        return forward_edge

    def add_node2pe (self, node_name: str=None, global_peID: int=None) -> bool:
        fn_name = mapper_context.add_node2pe.__name__
        ret_val = False
        if (node_name is not None and global_peID is not None):
            self.node2pe[node_name] = global_peID
            ret_val = True
        return ret_val
    
    # All about PE meta data template
    def gen_pe_meta_template (self) -> dict:
        fn_name = mapper_context.gen_pe_meta_template.__name__
        t_pe_meta = {}
        t_pe_meta['op'] = []                                            # Opcodes attached to the PE are added here as a tuple: (opcode_name, opcode_id)
                                                                            # The opcode_id attached to the name helps in determining intra-PE routing
        t_pe_meta['data_in_opID'] = [None for _ in range(self.cgra_radix)]       # The in_opID key holds the opIDs attached to the corresponding 
                                                                            # input_paths to PE in ascending order of the input-paths.
        t_pe_meta['data_out_opID'] = [None for _ in range(self.cgra_radix)]      # Similar to the in_opID, but for output paths.
        t_pe_meta['pred_in_opID'] = [None for _ in range(1)]
        t_pe_meta['pred_out_opID'] = [None for _ in range(1)]
        t_pe_meta['data_out_blockID'] = [None for _ in range(self.cgra_radix)]
        t_pe_meta['pred_out_blockID'] = [None for _ in range(1)]
        t_pe_meta['data_port_meta'] = [[None, []] for _ in range(self.cgra_radix)]    # [[child_PE_id, attempted_ports], ...]
        t_pe_meta['pred_port_meta'] = [[None, []] for _ in range(1)]
        return t_pe_meta
    
    def create_pe_meta (self, global_peID: int) -> None:
        fn_name = mapper_context.create_pe_meta.__name__
        # create PE Metadata using template
        self.pe_meta[global_peID] = self.gen_pe_meta_template()

    def add_pe_meta_opcode (self, global_peID: int=None, name: str='', opcode: str='', opID: int=None, parent_opID: list[int]=None) -> bool:
        fn_name = mapper_context.add_pe_meta_opcode.__name__
        ret_val = False
        if (global_peID is not None):
            if (self.pe_meta.get(global_peID, None) is None):
                self.create_pe_meta(global_peID)
            # Add opcode to pe's Metadata
            #self.pe_meta[global_peID]['opcode'].append((parent_opID, opcode, opID))
            op_dict = {
                'name'      : name,
                'code'      : opcode,
                'in_ID'     : parent_opID,
                'out_ID'    : opID
            }
            self.pe_meta[global_peID]['op'].append(op_dict)
            ret_val = True
        return ret_val
    
    def combine_pe_meta (self, dest_meta: dict, src_meta: dict) -> dict:
        fn_name = mapper_context.combine_pe_meta.__name__
        # Create result placeholder
        res_meta = dict(dest_meta)
        # Copy over all meta data from src to dest
        for opc in src_meta['op']:
            res_meta['op'].append(opc)
        for i_opID, o_opID in list(zip(src_meta['data_in_opID'], src_meta['data_out_opID'])):
            # The combining of paths follows the strict order of
            # physical block's io_opIDs of len(cgra_radix), followed by
            # shadow block's io_opIDs lf len(cgra_radix).
            res_meta['data_in_opID'].append(i_opID)
            res_meta['data_out_opID'].append(o_opID)
        for i_opID, o_opID in list(zip(src_meta['pred_in_opID'], src_meta['pred_out_opID'])):
            res_meta['pred_in_opID'].append(i_opID)
            res_meta['pred_out_opID'].append(o_opID)
        for o_blkID in src_meta['data_out_blockID']:
            res_meta['data_out_blockID'].append(o_blkID)
        for o_blkID in src_meta['pred_out_blockID']:
            res_meta['pred_out_blockID'].append(o_blkID)
        for pchild in src_meta['data_port_meta']:
            res_meta['data_port_meta'].append(pchild)
        for pchild in src_meta['pred_port_meta']:
            res_meta['pred_port_meta'].append(pchild)
        return res_meta

    def condense_pe_meta (self) -> None:
        fn_name = mapper_context.condense_pe_meta.__name__
        # Var to keep track all the keyes we have copied
        t_src_done = []
        # Make a copy of pe_meta dict
        t_pe_meta = dict(self.pe_meta)
        # Get keys to iterate on
        pe_meta_keys = self.pe_meta.keys()
        #self.logger.debug(f'{fn_name} ||| pe_meta before condensing: {t_pe_meta} \n keyes = {pe_meta_keys}')
        for i, meta_key in enumerate(pe_meta_keys):
            n_gpid = meta_key
            n_lpid = self.get_localPE_id(n_gpid)
            n_blk = self.get_block(n_gpid)
            n_shadow_blk = self.get_shadow_block(n_blk)
            if (n_blk != n_shadow_blk):
                # Absorb into the lower/physical block
                dest_blk = n_blk if (n_blk < n_shadow_blk) else n_shadow_blk
                src_blk = n_shadow_blk if (n_blk < n_shadow_blk) else n_blk
                n_dgpid = self.get_globalPE_id(n_lpid, dest_blk)
                n_sgpid = self.get_globalPE_id(n_lpid, src_blk)
                # Case 0: Ignore PEs that are done
                if (n_sgpid in t_src_done):
                    continue
                # Case 1: Destination PE exists but source does not
                elif (n_dgpid in pe_meta_keys and not n_sgpid in pe_meta_keys):
                    # Fill append empty template to destination
                    t_pe_meta[n_dgpid] = self.combine_pe_meta(self.pe_meta[n_dgpid], self.gen_pe_meta_template())
                    # Nothing to delete
                # Case 2: Destination PE does not exist but source does
                elif (not n_dgpid in pe_meta_keys and n_sgpid in pe_meta_keys):
                    t_pe_meta[n_dgpid] = self.combine_pe_meta(self.gen_pe_meta_template(), self.pe_meta[n_sgpid])
                    # Delete the source (shadow metadata)
                    del t_pe_meta[n_sgpid]
                # Case 3: Destination and source PE exist
                else:
                    t_pe_meta[n_dgpid] = self.combine_pe_meta(self.pe_meta[n_dgpid], self.pe_meta[n_sgpid])
                    # Delete the source (shadow metadata)
                    del t_pe_meta[n_sgpid]
                #self.logger.debug(f'{fn_name} ||| iter[{i}] | Condensing src_pe[{n_sgpid}, {src_blk}] into dest_pe[{n_dgpid}, {dest_blk}]')
                t_src_done.append(n_sgpid)
        # Re-assign
        self.pe_meta = t_pe_meta
    
    def make_route_pairs (self, src_tracker: list, dest_tracker: list, predicate: bool=False) -> bool:
        fn_name = mapper_context.make_route_pairs.__name__
        ret_val = True
        self.logger.debug(f'{fn_name} ||| src_tracker = {src_tracker}; dest_tracker = {dest_tracker}; predicate = {predicate}')
        if (len(src_tracker) == len(dest_tracker) and len(src_tracker) == self.cgra_blocks):
            for blk_sel in range(self.cgra_blocks):
                src_blk = src_tracker[blk_sel]
                dest_blk = dest_tracker[blk_sel]
                if (len(src_blk) == len(dest_blk)):
                    port_cnt = len(src_blk)
                    for port_sel in range(port_cnt):
                        src_port = src_blk[port_sel]
                        dest_port = dest_blk[port_sel]
                        for route_pair in list(zip(src_port, dest_port)):
                            # Normalize global_PE_id back to local, block level PE_ids
                            src_lpid = self.get_localPE_id(route_pair[0])
                            dest_lpid = self.get_localPE_id(route_pair[1])
                            local_route_pair = (src_lpid, dest_lpid)
                            if (predicate):
                                self.pred_route_pairs[blk_sel][port_sel].append(local_route_pair)
                            else:
                                self.data_route_pairs[blk_sel][port_sel].append(local_route_pair)
                else:
                    ret_val = False
                    break
        return ret_val

    def print_node2pe (self) -> None:
        fn_name = mapper_context.print_node2pe.__name__
        self.logger.debug(f'\n')
        self.logger.debug(f'{fn_name} ||| --------------- node2pe_deets --------------- ')
        for n in list(self.node2pe.keys()):
            self.logger.debug(f'{fn_name} ||| node[{n}]: PE[{self.node2pe[n]}]')
    
    def print_pe_metadata (self) -> None:
        fn_name = mapper_context.print_pe_metadata.__name__
        self.logger.debug(f'\n')
        self.logger.debug(f'{fn_name} ||| --------------- pe_meta_deets --------------- ')
        for k in list(self.pe_meta.keys()):
            self.logger.debug(f'{fn_name} ||| PE[{k}] metadata:')
            self.logger.debug(f'{fn_name} ||| op: {self.pe_meta[k]['op']}')
            self.logger.debug(f'{fn_name} ||| data_in_opID: {self.pe_meta[k]['data_in_opID']}')
            self.logger.debug(f'{fn_name} ||| data_out_opID: {self.pe_meta[k]['data_out_opID']}')
            self.logger.debug(f'{fn_name} ||| pred_in_opID: {self.pe_meta[k]['pred_in_opID']}')
            self.logger.debug(f'{fn_name} ||| pred_out_opID: {self.pe_meta[k]['pred_out_opID']}')

    def print_data (self) -> None:
        fn_name = mapper_context.print_data.__name__
        self.print_node2pe()
        self.print_pe_metadata()
        self.logger.debug(f'{fn_name} ||| data_route_pairs: \n {self.data_route_pairs}')
        self.logger.debug(f'{fn_name} ||| pred_route_pairs: \n {self.pred_route_pairs}')
        self.logger.debug(f'{fn_name} ||| data_path_scbs: \n {self.data_path_scbs}')
        self.logger.debug(f'{fn_name} ||| pred_path_scbs: \n {self.pred_path_scbs}')
