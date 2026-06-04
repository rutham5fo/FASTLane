
#-------------------------------------------------------------------------
# For better understanding of the algorithm, check this paper out:
# "Design and implementation of fast and hardware-efficient parallel
# processing elements to set full and partial permutations in Beneš networks." 
# by Labson Koloko, Takahiro Matsumoto, and Hitoshi Obara
#-------------------------------------------------------------------------

import logging
import os
import argparse
import math
import copy
#from contexts.cgra_context import cgra_context
#from contexts.dot_context import dot_context
#from contexts.mapper_context import mapper_context
#from mapper.placer import placer
#from mapper.router import router

class benes:

    def __init__ (self, benes_size: int=16, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs') -> None:
        fn_name = benes.__init__.__name__
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
        self.benes_size = benes_size
        self.switches = int(self.benes_size/2)
        self.stages = int(2 * math.log2(self.benes_size) - 1)
        self.prep_stages = int(math.log2(self.benes_size) - 1)
        self.forward_stages = int(math.log2(self.benes_size))
        self.scb = [[0 for _ in range(self.switches)] for _ in range(self.stages)]
        self.switch_lock = [[0 for _ in range(self.switches)] for _ in range(self.stages)]
        self.switch_IOmap = self.build_switch_IOmap()
    
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
    
    # Reset all the switch-control-bits
    def reset_benes (self) -> None:
        fn_name = benes.reset_benes.__name__
        self.scb = [[0 for _ in range(self.switches)] for _ in range(self.stages)]
        self.switch_lock = [[0 for _ in range(self.switches)] for _ in range(self.stages)]
    
    def build_switch_IOmap (self) -> list:
        fn_name = benes.build_switch_IOmap.__name__
        switch_IOmap = []
        for j in range(self.prep_stages):
            stage_split = int(self.benes_size/2**(j+1))
            subnet_split = 2*stage_split
            even_conn_guide = 0
            odd_conn_guide = stage_split
            #self.logger.debug(f'{fn_name} ||| stage[{j}] | stage_split = {stage_split}, subnet_split = {subnet_split}')
            switch_IOmap.append([])
            for i in range(self.benes_size):
                subnet_sel = int(i/subnet_split)
                even_conn_loc = even_conn_guide+subnet_sel*subnet_split
                odd_conn_loc = odd_conn_guide+subnet_sel*subnet_split
                #self.logger.debug(f'{fn_name} ||| switch_out[{i}]: even_conn_guide = {even_conn_guide}, odd_conn_guide = {odd_conn_guide}, subnet_sel = {subnet_sel}, even_conn_loc = {even_conn_loc}, odd_conn_loc = {odd_conn_loc}')
                # Baseline network connections
                if (i%2 == 0):
                    switch_IOmap[j].append(even_conn_loc)
                    even_conn_guide = even_conn_guide+1 if (even_conn_guide < stage_split-1) else 0
                else:
                    switch_IOmap[j].append(odd_conn_loc)
                    odd_conn_guide = odd_conn_guide+1 if (odd_conn_guide < 2*stage_split-1) else stage_split
        self.logger.debug(f'{fn_name} ||| Switch_IOmap = {switch_IOmap}')
        return switch_IOmap

    def balance_perm (self, perm: list) -> list:
        fn_name = benes.balance_perm.__name__
        b_perm = [None for _ in range(self.benes_size)]
        f_dest = [d for d in range(self.benes_size)]
        # Get free destinations while arranging existing pairs
        for pair in perm:
            b_perm[pair[0]] = pair[1]
            f_dest.remove(pair[1])
        if (len(f_dest) > 0):
            self.logger.debug(f'{fn_name} ||| almost-balanced_perm = {b_perm}; free_dest = {f_dest}')
        # Populate balanced permutation
        for elem in range(self.benes_size):
            if (b_perm[elem] is None):
                b_perm[elem] = f_dest.pop()
        self.logger.debug(f'{fn_name} ||| balanced_perm = {b_perm}')
        return b_perm
    
    # Given a list of source permutation, stage, and switch_setting
    # Propogate the sources towards the stage's destination permutation
    def propogate (self, stage: int, perm: list) -> list:
        fn_name = benes.propogate.__name__
        out_perm = [None for _ in range(self.benes_size)]
        self.logger.debug(f'{fn_name} ||| stage = {stage}, input perm = {perm}')
        # Pass input permutation through switches
        for i, ip in enumerate(perm):
            # Pass input permutation through switches
            sw_loc = int(i/2)
            sw_scb = self.scb[stage][sw_loc]
            sw_perm_loc = i if (sw_scb == 0) else i+1-(2*int(i%2))          # i->[[sw]->sw_perm_loc->output_perm_loc] -> Input i to next stage
            out_loc = None
            # The normalized switch perm loc determines which subnet we are handling.
            # Since deeper stages have multiple subnets that require swapping across the stage_split
            #self.logger.debug(f'{fn_name} ||| iter[{i}] | sw_loc = {sw_loc}, sw_scb = {sw_scb}, sw_perm_loc = {sw_perm_loc} | cur_dest = {ip}')
            # Propogate switch_permutation to next stage
            if (stage == self.stages-1):
                out_loc = sw_perm_loc
            elif (stage < self.prep_stages):
                # Baseline network connections
                # set output location according to switch_IOmap
                #self.logger.debug(f'{fn_name} ||| map_stage = {stage}; Selected sw_IOmap = [{self.switch_IOmap[stage]}]')
                out_loc = self.switch_IOmap[stage][sw_perm_loc]
            else:
                # Reverse/reflected Baseline network connections
                # output location is obtained by looking in from the output side
                map_stage = 2*self.prep_stages - stage - 1
                #self.logger.debug(f'{fn_name} ||| map_stage = {map_stage}; Selected sw_IOmap = [{self.switch_IOmap[map_stage]}]')
                out_loc = [l for l, map in enumerate(self.switch_IOmap[map_stage]) if (map == sw_perm_loc)][0]
            #self.logger.debug(f'{fn_name} ||| Propagating switch_output[{sw_perm_loc}] val = {ip} --> stage_input[{out_loc}]')
            out_perm[out_loc] = ip
        if (out_perm.count(None) > 0):
            self.logger.error(f'{fn_name} ||| Something went wrong during propogation; out_perm = {out_perm}')
        return out_perm
    
    def int2bin (self, val: int, pad: int=0) -> str:
        fn_name = benes.int2bin.__name__
        bin_str = str(bin(val))[2:].zfill(pad)
        return bin_str

    def bin2int (self, val: str) -> int:
        fn_name = benes.bin2int.__name__
        #self.logger.debug(f'{fn_name} ||| converting bin = {val}')
        res = int(val, 2)
        return res

    def forward_pass (self, stage, perm: list) -> None:
        fn_name = benes.forward_pass.__name__
        # Perform DTR on half the inputs since the rest will follow
        bit_sel = stage-self.prep_stages
        for i in range(self.switches):
            p_sel = 2*i
            #self.logger.debug(f'{fn_name} ||| stage[{stage}], switch[{i}], input[{p_sel}] = {perm[p_sel]}')
            bin_str = self.int2bin(perm[p_sel], self.forward_stages)
            #scb = int(bin_str[-(bit_sel+1)])    # From LSB
            scb = int(bin_str[bit_sel])    # From MSB
            #self.logger.debug(f'{fn_name} ||| binary_rep = {bin_str}, bit_sel = {bit_sel}, str_scb = {bin_str[bit_sel]} | scb = {scb}')
            self.scb[stage][i] = scb
            self.switch_lock[stage][i] = 1
    
    def prep_pass (self, stage: int, switch_map: list, src: int, dest: int, perm: list) -> list:
        fn_name = benes.prep_pass.__name__
        stage_split = int(self.benes_size/2**(stage+1))
        scb_flip = int(src%2)
        switch_loc = int(math.floor(src/2))
        if (self.switch_lock[stage][switch_map[switch_loc]] == 0):
            # Since we start by routing the switch-chain through subnet_0 (lower),
            # finding the dest_buddy of cur_switch will lead to a source in the next
            # switch. This source must route through subnet_1, and the buddy of that 
            # source (in the next switch) must once again route through subnet_0.
            # Hence following the switch-chain using the double-buddy switch will 
            # always land on a source that must route through subnet_0.
            self.scb[stage][switch_map[switch_loc]] = scb_flip
            self.switch_lock[stage][switch_map[switch_loc]] = 1
        else:
            self.logger.error(f'{fn_name} ||| Re-visiting a locked switch. This should not be possible when traversing a chain in one direction !')
            return perm
        # Find next switch in chain
        # Each switch is considered to have an even and odd pair of ports
        # Source side buddies are always even-odd pairs
        b_src = src+1 if (src%2 == 0) else src-1                        # source buddy of current switch
        # But destination side buddies, depending on the benes physical
        # structure, might be even odd pairs or all even/odd pairs (same parity).
        # In this case, the buddy is also the same parity, spread by stage_split.
        b_dest = dest+1 if (dest%2 == 0) else dest-1
        #self.logger.debug(f'{fn_name} ||| src = {src}, b_src = {b_src}, dest = {dest}, b_dest = {b_dest}')
        # Remove current switch from perm list
        pop = lambda x, y, z, b_z: y if (x != z and x != b_z) else None
        perm = [pop(i, d, src, b_src) for i, d in enumerate(perm)]
        self.logger.debug(f'{fn_name} ||| Next permutation = {perm}')
        if (b_dest in perm):
            r_src = [s for s, p in enumerate(perm) if (p == b_dest)][0]     # reflected source of destination buddy
            rb_src = r_src+1 if (r_src%2 == 0) else r_src-1                 # reflected source buddy
            rb_dest = perm[rb_src]                                          # destination of rb_src
            self.logger.debug(f'{fn_name} ||| rb_src = {rb_src}, rb_dest = {rb_dest}')
            # Recursive call with next switch in chain
            perm = self.prep_pass(stage, switch_map, rb_src, rb_dest, perm)
        else:
            # This means, the buddy leads back to the chain leader.
            # Hence we close the loop here and exit
            self.logger.debug(f'{fn_name} ||| Chain complete')
        return perm

    def normalize_perm (self, stage: int, perm: list) -> list:
        fn_name = benes.normalize_perm.__name__
        # Normalize the permutation by removing the LSBs
        n_perm = []
        if (stage > 0):
            for p in perm:
                bin_val = self.int2bin(p, self.forward_stages)
                n_bval = bin_val[:-stage]
                #self.logger.debug(f'{fn_name} ||| stage[{stage}] | perm_val = {p}, bin_val = {bin_val}, n_bval = {n_bval}')
                n_ival = self.bin2int(n_bval)
                n_perm.append(n_ival)
        else:
            n_perm = perm
        self.logger.debug(f'{fn_name} ||| Permutation post normalization = {n_perm}')
        # Duplicates post normalization indicate faulty scb generation in the previous stage
        # Since, all destinations in the permutation must be unique at any given stage's input (post normalization)
        len_n_perm = len(n_perm)
        for i in range(len_n_perm):
            p_val = n_perm[i]
            for j in range(len_n_perm):
                d_val = n_perm[j]
                if (p_val == d_val and i != j):
                    self.logger.error(f'{fn_name} ||| Found duplicate for dest[{perm[i]}] post normalization | perm = {perm} !')
                    break
        return n_perm

    def validate_route (self, perm: list) -> bool:
        fn_name = benes.validate_route.__name__
        ret_val = True
        for i, p in enumerate(perm):
            if (p != i):
                self.logger.error(f'{fn_name} ||| Invalid route for destination[{p}]')
                ret_val = False
        return ret_val

    # Run benes routing algorithm from sources to destination
    def run (self, permutation: list) -> list | None:
        fn_name = benes.run.__name__
        ret_val = None
        # Copy permutation (src, dest) pair list
        perm = copy.deepcopy(permutation)
        # Balance the permutation by assigning random destinations
        # to un-assigned sources and rearranging the permutation 
        # according to the port list, i.e., all srcs must be in ascending order.
        self.logger.debug(f'{fn_name} ||| Attempting to route Benes permutation = {perm}')
        perm = self.balance_perm(perm)
        for j in range(self.stages):
            if (j < self.prep_stages):
                perm_split = 2**j
                split_len = int(self.benes_size/perm_split)
                sw_split = int(split_len/2)
                sub_perms = [perm[ps*split_len:split_len*(ps+1)] for ps in range(perm_split)]
                self.logger.debug(f'{fn_name} ||| Stage[{j}] || perm_split = {perm_split}, split_len = {split_len},' \
                                  f' sw_split = {sw_split}, sub_perms = {sub_perms}')
                for subset, s_perm in enumerate(sub_perms):
                    # Normalize the destination according to current stage
                    pending_perm = self.normalize_perm(j, s_perm)
                    # Get the set of switch_locs for this subset of perms
                    sw_beg = subset*sw_split
                    sw_end = sw_split*(subset+1)
                    sw_map = [sw for sw in range(sw_beg, sw_end)]
                    exit_cond = False
                    while (not exit_cond):
                        src = [i for i, fe in enumerate(pending_perm) if (fe is not None)][0]
                        dest = pending_perm[src]
                        self.logger.debug(f'{fn_name} ||| pending_perm = {pending_perm} | src = {src}, dest = {dest}')
                        pending_perm = self.prep_pass(j, sw_map, src, dest, pending_perm)
                        # Check if pending_perm list is complete
                        exit_cond = True if (pending_perm.count(None) == len(pending_perm)) else False
            else:
                # Perform destination-tag-routing (DTR)
                self.forward_pass(j, perm)
            # Propogate current permutation through switches based on scb's set above
            # and compute the new permutation for the next stage.
            perm = self.propogate(j, perm)
            self.logger.debug(f'{fn_name} ||| Stage[{j}] | Output permutation = {perm}')
        # Validate if all sources were successfully routed
        if (self.validate_route(perm)):
            self.logger.debug(f'{fn_name} ||| Benes Routing: PASSED')
            ret_val = self.scb
        else:
            self.logger.debug(f'{fn_name} ||| Benes Routing: FAILED')
        return ret_val

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
            # Start Benes
            for blk in range(cgra_ctxt.cgra_blocks):
                for path in range(cgra_ctxt.cgra_radix):
                    # Get corresponding path's permutation
                    perm = mapper_ctxt.route_pairs[blk][path]
                    ben.reset_benes()
                    path_scbs = ben.run(perm)
                    if (path_scbs is not None):
                        mapper_ctxt.path_scbs[blk][path] = path_scbs
                    else:
                        print (f'{fn_name} ||| Benes routing failed for block[{blk}], path[{path}], permutation = {perm}')
                        break
    mapper_ctxt.print_data()

if __name__ == "__main__":
    _test()
