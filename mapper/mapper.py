
import logging
import os
import time
import argparse
from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
from contexts.mapper_context import mapper_context
from dots_manager.manager import dot_manager
from mapper.placer import placer
from mapper.router import router

class mapper:

    def __init__ (self, dot_fpath: str='', cgra_config_fpath: str='', pe_config_fpath: str='', cgra_name: str='', logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs', log_fname: str='', combine_logs: bool=False) -> None:
        fn_name = placer.__init__.__name__
        # Setup logger
        self.logger_name = self.__class__.__name__
        self.ctxt_logger_name = self.logger_name if (combine_logs) else ''
        self.logger = None
        if (logger_name):
            self.logger_name = logger_name
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger = self.log_setup(self.logger_name, log_level, log_dir, log_fname)
        # State vars
        self.dot_blocks = None
        self.dot_ctxt = None
        self.cgra_ctxt = None
        self.mapper_ctxt = None
        self.plcr = None
        self.rtr = None
        # Setup vars
        if (not dot_fpath or not cgra_config_fpath or not pe_config_fpath or not cgra_name):
            err_msg = f'{fn_name} ||| Please provide valid DFG file, CGRA name, config files for CGRA, and PE definition !'
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        else:
            try:
                self.dot_man = dot_manager(self.cgra_ctxt, logger_name=self.ctxt_logger_name, log_level=logging.DEBUG)
            except Exception as ex:
                self.logger.error(f'{fn_name} ||| Execption: {ex}')
                raise
            try:
                self.cgra_ctxt = cgra_context(cgra_config_fpath, pe_config_fpath, cgra_name, logger_name=self.ctxt_logger_name, log_level=logging.DEBUG)
            except Exception as ex:
                self.logger.error(f'{fn_name} ||| Execption: {ex}')
                raise
            self.dot_blocks = int(dot_fpath[dot_fpath.rfind('_B')+2:dot_fpath.rfind('_u')])
            self.dot_man.gen_dot_context(dot_fpath)
            self.dot_ctxt = self.dot_man.dot_ctxt
            self.mapper_ctxt = mapper_context(self.cgra_ctxt.cgra_blocks, self.cgra_ctxt.cgra_block_size, self.cgra_ctxt.cgra_radix, logger_name=self.logger_name)
            self.plcr = placer(self.mapper_ctxt, self.cgra_ctxt, logger_name=self.ctxt_logger_name, log_level=logging.DEBUG)
            self.rtr = router(self.mapper_ctxt, self.cgra_ctxt, logger_name=self.ctxt_logger_name, log_level=logging.DEBUG)
    
    def log_setup (self, logger_name, log_level, log_dir, log_fname) -> logging:
        fn_name = mapper.log_setup.__name__
        cwd = os.getcwd()
        log_fname = log_fname + '.log' if (log_fname) else logger_name + '.log'
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
    def run (self) -> bool:
        fn_name = placer.run.__name__
        mapped = False
        placed = False
        retry_placement = False
        # Sanity check
        if (self.dot_ctxt is None or self.dot_blocks < 0 or self.dot_blocks != self.cgra_ctxt.cgra_phy_blocks):
            self.logger.error(f'{fn_name} ||| DFG blocks[{self.dot_blocks}] and CGRA blocks[{self.cgra_ctxt.cgra_phy_blocks}] dont match (or) DOT Context unavailable !')
        else:
            # Set start time
            _mpr_start = time.perf_counter_ns()
            while (True):
                # Run placer
                placed, retry_placement = self.plcr.run(self.dot_ctxt)
                if (retry_placement):
                    # Legalize the modified DFG and re-run through placer
                    self.dot_man.reflect_modification(self.dot_blocks)
                    self.logger.info(f'{fn_name} ||| Retrying Placement !')
                else:
                    break
            if (placed):
                # Run router
                mapped = self.rtr.run(self.dot_ctxt)
                self.mapper_ctxt.print_data()
            # Measure run_time
            _mpr_end = time.perf_counter_ns()
            if (mapped):
                self.logger.info(f'{fn_name} ||| Mapping: SUCCESS')
            else:
                self.logger.info(f'{fn_name} ||| Mapping: FAILED')
            self.logger.info(f'{fn_name} ||| Mapper Run-time (s) = {(_mpr_end-_mpr_start)/1000000000}')
        return mapped
    
    def validate (self) -> bool:
        fn_name = mapper.validate.__name__
        valid = True
        dedges = self.dot_ctxt.dot_edges
        pe_meta = self.mapper_ctxt.pe_meta
        for e in dedges:
            n_src = e.get_source()
            n_dest = e.get_destination()
            src_opID = None
            dest_opID = None
            self.logger.debug(f'{fn_name} ||| Validating Edge: {n_src} --> {n_dest}')
            # Find source PE in mapper context
            for k, meta in list(pe_meta.items()):
                for data in meta['op']:
                    if (data['name'] == n_src):
                        src_opID = data['out_ID']
                        self.logger.debug(f'{fn_name} ||| Found source @ PE[{k}] | op_name = {data['name']}, opID = {src_opID}')
                        break
                if (src_opID is not None):
                    break
            if (src_opID is None):
                self.logger.error(f'{fn_name} ||| Could not find source PE !')
                valid = False
                break
            # Find matching destination PE
            for k, meta in list(pe_meta.items()):
                data = meta['data_in_opID']
                pred = meta['pred_in_opID']
                if (src_opID in data or src_opID in pred):
                    for op in meta['op']:
                        if (src_opID in op['in_ID']):
                            dest_opID = op['out_ID']
                            dest_name = op['name']
                            self.logger.debug(f'{fn_name} ||| Found Destination @ PE[{k}] | op_name = {dest_name}, opID = {dest_opID}')
                            break
                if (dest_opID is not None):
                    break
            if (dest_opID is None):
                self.logger.error(f'{fn_name} ||| Could not find destination PE')
                valid = False
                break
        if (not valid):
            self.logger.info(f'{fn_name} ||| Validation: FAILED')
        else:
            self.logger.info(f'{fn_name} ||| Validation: SUCCESS')
        return valid
    
def _test ():
    fn_name = _test.__name__
    cwd = os.getcwd()

    # CMD parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', action='store', default="", dest='dot_file', help='DOT file to parse')
    parser.add_argument('--log-name', action='store', default='', dest='log_name', help='Logfile name')
    parser.add_argument('--log-level', action='store', default='debug', dest='log_level', help='Logging level [notset, debug, info, warn, error, fatal]')
    parser.add_argument('--log-dir', action='store', default='logs', dest='log_dir', help='Logfile directory')
    parser.add_argument('--combine-logs', action='store_true', dest='log_combine', help='Combines all sub-module logs into mapper\'s')
    args = parser.parse_args()

    # State vars
    log_levels = {'notset': logging.NOTSET, 'debug': logging.DEBUG, 'info': logging.INFO, 'warn': logging.WARN, 'error': logging.ERROR, 'fatal': logging.CRITICAL}
    dot_file_name = args.dot_file
    log_name = args.log_name
    log_level = log_levels[args.log_level]
    log_dir = args.log_dir
    log_combine = args.log_combine

    # Setup and fpaths
    dot_fpath = os.path.join(cwd, 'dots', 'results', dot_file_name)
    cgra_cfg_fpath = os.path.join(cwd, 'configs', 'cgra_config.yaml')
    pe_cfg_fpath = os.path.join(cwd, 'configs', 'pe_config.yaml')

    # Create Mapper
    mpr = mapper(dot_fpath, cgra_cfg_fpath, pe_cfg_fpath, 'CGRA', log_level=log_level, log_dir=log_dir, log_fname=log_name, combine_logs=log_combine)
    # Run mapper
    mpr.run()
    # Verify mapping
    mpr.validate()

if __name__ == "__main__":
    _test()
