
import yaml
import logging
import os

class cgra_context:

    def __init__ (self, cgra_config_fpath: str='', pe_config_fpath: str='', cgra_name: str='', logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
        fn_name = cgra_context.__init__.__name__
        # Setup logger
        self.logger_name = None
        self.logger = None
        if (logger_name):
            self.logger_name = logger_name
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger_name = self.__class__.__name__
            self.logger = self.log_setup(self.logger_name, log_level, log_dir)
        # Parse cgra_config and pe_config files
        self.cgra_cfg = None
        self.pe_cfg = None
        # State Vars
        self.cgra_name = None
        self.cgra_radix = None
        self.cgra_phy_blocks = None
        self.cgra_blocks = None
        self.cgra_block_size = None
        self.cgra_size = None
        self.cgra_attr = {}
        # Maintain a dict, per block, for each opcode, holding a list of valid PEs that we can map to
        self.avail_pe = []                      # [(PE_id, opGroup, linked), ...]
        # Maintain a dict for all opcode costs (including routing opcodes)
        self.opcode_cost = {}
        # Maintain a list to track the availability of in/out ports in a PE, per block
        # The PE_ID is the location of PE along the list. This is by virtue of CGRA construction.
        # CGRA construction/PE ordering is set in cgra_config.yaml
        self.pe_info = []                       # [[(pe_type), [input, output]], ...]
        if (cgra_name and cgra_config_fpath and pe_config_fpath):
            self.cgra_name = cgra_name
            self.get_configs(cgra_config_fpath, pe_config_fpath)
            self.load_state()
            if (self.sanity_check()):
                self.gen_cgra_context()
            else:
                err_msg = f'{fn_name} ||| CGRA context generation failed !'
                raise Exception(err_msg)
    
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
    
    # Get CGRA and PE config files into context
    def get_configs (self, cgra_cfg_fpath: str='', pe_cfg_fpath: str='') -> None:
        fn_name = cgra_context.get_configs.__name__
        # Parse cgra_config and pe_config files
        with open(cgra_cfg_fpath) as yf:
            self.cgra_cfg = yaml.safe_load(yf)
            self.logger.debug(f'{fn_name} ||| Loading cgra_config file: \n {self.cgra_cfg}')
        with open(pe_cfg_fpath) as yf:
            self.pe_cfg = yaml.safe_load(yf)
            self.logger.debug(f'{fn_name} ||| Loading pe_config file: \n {self.pe_cfg}')

    # Load state vars from config files
    def load_state (self) -> None:
        fn_name = cgra_context.load_state.__name__
        self.cgra_radix = int(self.cgra_cfg[self.cgra_name]['radix'])
        self.cgra_overload = int(self.cgra_cfg[self.cgra_name]['overload'])
        self.cgra_phy_blocks = int(self.cgra_cfg[self.cgra_name]['blocks'])
        # The number of blocks is always computed with the assumption of an overload
        # In the absence of an overload, the corresponding shadow-PE must also be removed
        # from PE list after placement! Else procedd as usual.
        # This is done in-order to make keeping track of PE IO count, easier.
        self.cgra_blocks = 2*(self.cgra_phy_blocks-1)
        self.cgra_block_size = int(self.cgra_cfg[self.cgra_name]['block_size'])
        self.cgra_size = self.cgra_block_size * self.cgra_blocks if (self.cgra_overload == 1) else self.cgra_block_size* self.cgra_phy_blocks
        self.logger.info(f'{fn_name} ||| {self.cgra_name}: radix = {self.cgra_radix}, overload = {self.cgra_overload}, phy_blocks = {self.cgra_phy_blocks}, blocks = {self.cgra_blocks}, block_size = {self.cgra_block_size}, total_size = {self.cgra_size}')

    # Perform CGRA sanity check
    def sanity_check (self) -> bool:
        fn_name = cgra_context.sanity_check.__name__
        ret_val = True
        cgra_phy_size = self.cgra_phy_blocks * self.cgra_block_size
        cgra_pe_cnt = 0
        for blk_deet in self.cgra_cfg['CGRA']['composition']:
            for k in blk_deet.keys():
                cgra_pe_cnt += blk_deet[k]
        #self.logger.debug(f'{fn_name} ||| cgra_phy_size = {cgra_phy_size}, cgra_pe_cnt = {cgra_pe_cnt}')
        if (cgra_pe_cnt != cgra_phy_size):
            self.logger.error(f'{fn_name} ||| CGRA config: CGRA_size and composition mismatch !')
            ret_val = False
        if (self.cgra_overload == 1 and self.cgra_blocks == 2):
            self.logger.error(f'{fn_name} ||| Need 3 or more blocks to enable overloading !')
            ret_val = False
        if (self.cgra_blocks < 2):
            self.logger.error(f'{fn_name} ||| Need a minimum of 2 blocks to build FASTLane architecture !')
            ret_val = False
        return ret_val

    def gen_cgra_context (self) -> None:
        fn_name = cgra_context.gen_cgra_context.__name__
        # Populate context from config files
        for blk in range(self.cgra_blocks):
            blk_composition_sel = blk if (blk <= self.cgra_phy_blocks-1) else self.cgra_blocks - blk
            blk_composition = self.cgra_cfg[self.cgra_name]['composition'][blk_composition_sel]
            blk_avail_pe = {}
            blk_pe_info = []
            #self.logger.debug(f'{fn_name} ||| Block[{blk}]:')
            #self.logger.debug(f'{fn_name} ||| Composition = {blk_composition}')
            for pe_type in list(blk_composition.keys()):
                #self.logger.debug(f'{fn_name} ||| PE_type = {pe_type}')
                for pid in range(blk_composition[pe_type]):
                    # Add to avail_pe according to pe_type's opGroups
                    pe_opGroup = self.pe_cfg[pe_type]['opGroup']
                    for opG in list(pe_opGroup.keys()):
                        op_list = pe_opGroup[opG]
                        for op_name in op_list:
                            #self.logger.debug(f'{fn_name} ||| OP = {op_name}')
                            blk_pe_linked = 1 if (blk != 0 and blk != self.cgra_phy_blocks-1 and self.cgra_overload == 0) else 0
                            blk_avail_pe[op_name] = blk_avail_pe.get(op_name, []) + [(pid, opG, blk_pe_linked)]
                    blk_pe_info.append([(pe_type,), [self.cgra_radix, self.cgra_radix]])    # PE_type is a tuple to ensure immutability
            self.avail_pe.append(blk_avail_pe)
            self.pe_info.append(blk_pe_info)
        # Add opCode cost to opcode_cost dict from opCode definition
        for op_def in self.pe_cfg['OPdef']:
            op_name = op_def['name']
            op_in_cost = op_def['cost']['in']
            op_out_cost = op_def['cost']['out']
            self.opcode_cost[op_name] = (op_in_cost, op_out_cost)
        # Print state vars
        self.logger.debug(f'{fn_name} ||| avail_pe = {self.avail_pe}')
        self.logger.debug(f'{fn_name} ||| opcode_cost = {self.opcode_cost}')
        self.logger.debug(f'{fn_name} ||| pe_info = {self.pe_info}')

def _test ():
    fn_name = _test.__name__
    
    cwd = os.getcwd()

    # Create context
    cgra_ctxt = cgra_context(log_level=logging.DEBUG)
    
    # Test context
    cgra_cfg_fpath = os.path.join(cwd, 'configs', 'cgra_config.yaml')
    pe_cfg_fpath = os.path.join(cwd, 'configs', 'pe_config.yaml')
    cgra_ctxt.gen_cgra_context(cgra_cfg_fpath, pe_cfg_fpath)

if __name__ == "__main__":
    _test()
