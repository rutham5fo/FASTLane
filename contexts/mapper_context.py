
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
    
    def add_node2pe (self, node_name: str=None, global_peID: int=None) -> bool:
        fn_name = mapper_context.add_node2pe.__name__
        ret_val = False
        if (node_name is not None and global_peID is not None):
            self.node2pe[node_name] = global_peID
            ret_val = True
        return ret_val
    
    def create_pe_meta (self, global_peID: int) -> None:
        fn_name = mapper_context.create_pe_meta.__name__
        # PE Metadata template
        self.pe_meta[global_peID] = {}
        self.pe_meta[global_peID]['opcode'] = []
        self.pe_meta[global_peID]['in_opID'] = [None for _ in range(self.cgra_radix)]
        self.pe_meta[global_peID]['out_opID'] = [None for _ in range(self.cgra_radix)]

    def add_pe_meta_opcode (self, global_peID: int=None, opcode: str='') -> bool:
        fn_name = mapper_context.add_pe_meta_opcode.__name__
        ret_val = False
        if (global_peID is not None):
            if (self.pe_meta.get(global_peID, None) is None):
                self.create_pe_meta(global_peID)
            # Add opcode to pe's Metadata
            self.pe_meta[global_peID]['opcode'] += [opcode]
            ret_val = True
        return ret_val
    
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
                                local_route_pair = (int(route_pair[0]%self.cgra_block_size), int(route_pair[1]%self.cgra_block_size))
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
