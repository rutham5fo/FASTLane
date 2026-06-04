
import yaml
import logging
import os

class cgra_context:

    def __init__ (self, cgra_config_fpath: str='', pe_config_fpath: str='', logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
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
        # Maintain a dict, per block, for each opcode, holding a list of valid PEs that we can map to
        self.avail_pe = []
        # Maintain a dict for all opcode costs (including routing opcodes)
        self.opcode_cost = []
        # Maintain a list to track the availability of in/out ports in a PE, per block
        # The PE_ID is the location of PE along the list. This is by virtue of CGRA construction.
        # CGRA construction/PE ordering is set in cgra_config.yaml
        self.pe_info = []                       # [[(pe_type), [input, output]], ...]
        if (cgra_config_fpath and pe_config_fpath):
            self.gen_cgra_context(cgra_config_fpath, pe_config_fpath)
    
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

    def gen_cgra_context (self, cgra_cfg_fpath: str="", pe_cfg_fpath: str="") -> None:
        fn_name = cgra_context.gen_cgra_context.__name__
        # Parse cgra_config and pe_config files
        with open(cgra_cfg_fpath) as yf:
            self.cgra_cfg = yaml.safe_load(yf)
            self.logger.debug(f'{fn_name} ||| Loading cgra_config file: \n {self.cgra_cfg}')
        with open(pe_cfg_fpath) as yf:
            self.pe_cfg = yaml.safe_load(yf)
            self.logger.debug(f'{fn_name} ||| Loading pe_config file: \n {self.pe_cfg}')
        # Build mapper_context
        self.cgra_radix = int(self.cgra_cfg['CGRA']['radix'])
        self.cgra_blocks = int(self.cgra_cfg['CGRA']['blocks'])
        self.cgra_block_size = int(self.cgra_cfg['CGRA']['block_size'])
        self.cgra_size = self.cgra_block_size * self.cgra_blocks
        self.logger.debug(f'{fn_name} ||| cgra: radix = {self.cgra_radix}, blocks = {self.cgra_blocks}, block_size = {self.cgra_block_size}, total_size = {self.cgra_size}')
        # Populate context from config files
        for blk in range(self.cgra_blocks):
            blk_composition = self.cgra_cfg['CGRA']['composition'][blk]
            blk_avail_pe = {}
            blk_opcode_cost = {}
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
                        for op in op_list:
                            #self.logger.debug(f'{fn_name} ||| OP = {op}')
                            op_name = op['name']
                            op_in_cost = op['cost']['in']
                            op_out_cost = op['cost']['out']
                            blk_avail_pe[op_name] = blk_avail_pe.get(op_name, []) + [(pid, opG)]
                            if (blk_opcode_cost.get(op_name, None) is None): blk_opcode_cost[op_name] = (op_in_cost, op_out_cost)
                    blk_pe_info.append([(pe_type,), [self.cgra_radix, self.cgra_radix]])    # PE_type is a tuple to ensure immutability
            # Append common routing opcodes to opcode_cost dict
            for rop in self.pe_cfg['Route']:
                rop_name = rop['name']
                rop_in_cost = rop['cost']['in']
                rop_out_cost = rop['cost']['out']
                blk_opcode_cost[rop_name] = (rop_in_cost, rop_out_cost)
            self.avail_pe.append(blk_avail_pe)
            self.opcode_cost.append(blk_opcode_cost)
            self.pe_info.append(blk_pe_info)
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
