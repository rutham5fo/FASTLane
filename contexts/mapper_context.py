
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
        self.cgra_blocks = cgra_blocks
        self.cgra_block_size = cgra_block_size
        self.cgra_radix = cgra_radix
        # Mapper uses global_peID for keys (global_peID = cgra_block_size*block_number+local_peID)
        self.node2pe = {}                                                                           # Populated by placer
        self.pe_meta = {}                                                                           # Populated by placer
        self.route_pairs = [[[] for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]  # Populated by router | [[[(src_pe, dest_pe)]]]
        self.path_scbs = [[None for _ in range(self.cgra_radix)] for _ in range(self.cgra_blocks)]    # Populated by benes

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
    
    def get_shadow_block (self, block: int) -> int:
        fn_name = mapper_context.get_shadow_block.__name__
        shadow_blk = block if (block == 0 or block == self.cgra_blocks/2) else self.cgra_blocks - block
        return shadow_blk
    
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
        t_pe_meta['opcode'] = []                                            # Opcodes attached to the PE are added here as a tuple: (opcode_name, opcode_id)
                                                                            # The opcode_id attached to the name helps in determining intra-PE routing
        t_pe_meta['in_opID'] = [None for _ in range(self.cgra_radix)]       # The in_opID key holds the opIDs attached to the corresponding 
                                                                            # input_paths to PE in ascending order of the input-paths.
        t_pe_meta['out_opID'] = [None for _ in range(self.cgra_radix)]      # Similar to the in_opID, but for output paths.
        return t_pe_meta
    
    def create_pe_meta (self, global_peID: int) -> None:
        fn_name = mapper_context.create_pe_meta.__name__
        # create PE Metadata using template
        self.pe_meta[global_peID] = self.gen_pe_meta_template()

    def add_pe_meta_opcode (self, global_peID: int=None, opcode: str='', opID: int=None) -> bool:
        fn_name = mapper_context.add_pe_meta_opcode.__name__
        ret_val = False
        if (global_peID is not None):
            if (self.pe_meta.get(global_peID, None) is None):
                self.create_pe_meta(global_peID)
            # Add opcode to pe's Metadata
            self.pe_meta[global_peID]['opcode'].append((opcode, opID))
            ret_val = True
        return ret_val
    
    def combine_pe_meta (self, dest_meta: dict, src_meta: dict) -> dict:
        fn_name = mapper_context.combine_pe_meta.__name__
        # Create result placeholder
        res_meta = dict(dest_meta)
        # Copy over all meta data from src to dest
        for opc in src_meta['opcode']:
            res_meta['opcode'].append(opc)
        for i_opID in src_meta['in_opID']:
            # The combining of input_paths follows the strict order of
            # physical block's i_opIDs of len(cgra_radix), followed by
            # shadow block's i_opIDs lf len(cgra_radix).
            res_meta['in_opID'].append(i_opID)
        for o_opID in src_meta['out_opID']:
            # The output_paths follow the same rule of combining
            # as the input paths.
            res_meta['out_opID'].append(o_opID)
        return res_meta

    def condense_pe_meta (self) -> None:
        # TODO: If a shadow node is used but its counter-real node is unused, this method will fail
        fn_name = mapper_context.condense_pe_meta.__name__
        # Var to keep track all the keyes we have copied
        t_src_done = []
        # Make a copy of pe_meta dict
        t_pe_meta = dict(self.pe_meta)
        # Get keys to iterate on
        pe_meta_keys = self.pe_meta.keys()
        self.logger.debug(f'{fn_name} ||| pe_meta before condensing: {t_pe_meta} \n keyes = {pe_meta_keys}')
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
                self.logger.debug(f'{fn_name} ||| iter[{i}] | Condensing src_pe[{n_sgpid}, {src_blk}] into dest_pe[{n_dgpid}, {dest_blk}]')
                t_src_done.append(n_sgpid)
        # Re-assign
        self.pe_meta = t_pe_meta
    
    def make_route_pairs (self, src_tracker: list, dest_tracker: list) -> bool:
        fn_name = mapper_context.make_route_pairs.__name__
        ret_val = True
        self.logger.debug(f'{fn_name} ||| src_tracker = {src_tracker}; dest_tracker = {dest_tracker}')
        if (len(src_tracker) == len(dest_tracker) and len(src_tracker) == self.cgra_blocks):
            for blk_sel in range(self.cgra_blocks):
                src_blk = src_tracker[blk_sel]
                dest_blk = dest_tracker[blk_sel]
                if (len(src_blk) == len(dest_blk) and len(src_blk) == self.cgra_radix and ret_val):
                    for port_sel in range(self.cgra_radix):
                        src_port = src_blk[port_sel]
                        dest_port = dest_blk[port_sel]
                        if (len(src_port) == len(dest_port)):
                            for route_pair in list(zip(src_port, dest_port)):
                                # Normalize global_PE_id back to local, block level PE_ids
                                src_lpid = self.get_localPE_id(route_pair[0])
                                dest_lpid = self.get_localPE_id(route_pair[1])
                                local_route_pair = (src_lpid, dest_lpid)
                                self.route_pairs[blk_sel][port_sel].append(local_route_pair)
                        else:
                            ret_val = False
                            break
                else:
                    ret_val = False
                    break
        return ret_val

    def print_data (self) -> None:
        fn_name = mapper_context.print_data.__name__
        self.logger.debug(f'{fn_name} ||| node2pe_list: \n {self.node2pe}')
        self.logger.debug(f'{fn_name} ||| pe_metadata: \n {self.pe_meta}')
        self.logger.debug(f'{fn_name} ||| route_pairs: \n {self.route_pairs}')
        self.logger.debug(f'{fn_name} ||| path_scbs: \n {self.path_scbs}')
