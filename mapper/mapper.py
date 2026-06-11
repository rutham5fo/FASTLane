
import logging
import os
import time
import argparse
from contexts.cgra_context import cgra_context
from contexts.dot_context import dot_context
from contexts.mapper_context import mapper_context
from mapper.placer import placer
from mapper.router import router

class mapper:

    def __init__ (self, cgra_config_fpath: str='', pe_config_fpath: str='', cgra_name: str='', logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
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
        self.mapper_ctxt = None
        self.plcr = None
        self.rtr = None
        # Setup vars
        if (not cgra_config_fpath or not pe_config_fpath or not cgra_name):
            err_msg = f'{fn_name} ||| Please provide valid CGRA name and config files for CGRA and PE definition !'
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        else:
            try:
                self.cgra_ctxt = cgra_context(cgra_config_fpath, pe_config_fpath, cgra_name, log_level=logging.DEBUG)
            except Exception as ex:
                self.logger.error(f'{fn_name} ||| Execption: {ex}')
                raise
            self.mapper_ctxt = mapper_context(self.cgra_ctxt.cgra_blocks, self.cgra_ctxt.cgra_block_size, self.cgra_ctxt.cgra_radix, logger_name=self.logger_name)
            self.plcr = placer(self.cgra_ctxt, log_level=logging.DEBUG)
            self.rtr = router(self.cgra_ctxt, log_level=logging.DEBUG)
    
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
    
    # Run placer on given dot file according to cgra_context built from config files
    def run (self, dot_ctxt: dot_context=None) -> bool:
        fn_name = placer.run.__name__
        mapped = False
        # Set start time
        _mpr_start = time.perf_counter_ns()
        # Run placer
        if (self.plcr.run(dot_ctxt, self.mapper_ctxt)):
            # Run router
            mapped = self.rtr.run(dot_ctxt, self.mapper_ctxt)
            self.mapper_ctxt.print_data()
        # Measure run_time
        _mpr_end = time.perf_counter_ns()
        if (mapped):
            self.logger.info(f'{fn_name} ||| Mapping: SUCCESS')
        else:
            self.logger.error(f'{fn_name} ||| Mapping: FAILED')
        self.logger.info(f'{fn_name} ||| Mapper Run-time (s) = {(_mpr_end-_mpr_start)/1000000000}')
        return mapped

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

    # Create Mapper
    mpr = mapper(cgra_cfg_fpath, pe_cfg_fpath, 'CGRA', log_level=logging.DEBUG)
    
    mpr.run(dot_ctxt)

if __name__ == "__main__":
    _test()
