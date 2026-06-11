
"""
Builds the graph from .dot file.
Abosrbs constants into a vertex's attribute. -> const=x
All reflexive edges of a vertex are absorbed into its attribute. -> reflexive=true
Add bridge/routing vertices to maintain bipartite traversal along edges.
Reduce bridges to minimize routing nodes.
NOTE: (1) DOT must be a 2-regular graph (i.e., max fan-in/out = 2 for a node)
      (2) Graph CAN be a cyclic, as we take advantage of GraphViz to
          establish node ranks. GraphViz takes care of breaking cycles, etc.
      (3) Unroll capabilites are only for testing purposes. This does not 
          modify the constants in the nodes responsible for proper unrolling.
"""

import logging
import os
import argparse
import subprocess
from contexts.dot_context import dot_context

class dot_manager:

    def __init__ (self, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs'):
        fn_name = dot_manager.__init__.__name__
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
        self.dot_ctxt = dot_context(self.logger_name)
        self.const_type = ["constVal", "int64", "float32"]      # Constant attributes of nodes to search for
    
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
    
    def gen_dot_context (self, dot_fname: str=""):
        fn_name = dot_manager.gen_dot_context.__name__
        self.dot_ctxt.get_graph(dot_fname)
    
    # Traverse dot_context and aborb all constants into their vertices
    def absorb_constants (self):
        fn_name = dot_manager.absorb_constants.__name__
        dnodes = self.dot_ctxt.dot_nodes
        # Get all constant source nodes
        const_src_names = [n.get_name() for n in dnodes if n.get("opcode") == "const"]
        # Add the attributes 'constVal', 'float32', 'int64' to the destination nodes.
        for src_name in const_src_names:
            _, children = self.dot_ctxt.get_children(src_name)
            src_attr = self.dot_ctxt.get_attribute(src_name, self.const_type)
            self.logger.debug(f'{fn_name} ||| attribute = {src_attr}')
            for cn in children:
                cn_name = cn.get_name()
                self.dot_ctxt.set_attribute(cn_name, src_attr)
                # Remove edge from parent to child
                self.dot_ctxt.dot_graph.del_edge(src_name, cn_name)
            # Remove the source node
            self.dot_ctxt.dot_graph.del_node(src_name)
        # Update the context
        self.dot_ctxt.update(fn_name)

    # Traverse dot_context and absorb reflexive edges into their vertices
    def absorb_reflexive (self):
        fn_name = dot_manager.absorb_reflexive.__name__
        dnodes = self.dot_ctxt.dot_nodes
        dedges = self.dot_ctxt.dot_edges
        # Find all edges with same source and destination
        for e in dedges:
            src = e.get_source()
            dest = e.get_destination()
            if (src == dest):
                # Add attribute 'reflexive=true' for corresponding sources
                for n in dnodes:
                    if (n.get_name() == src):
                        n.set("reflexive", "true")
                # Delete edges from graph
                self.dot_ctxt.dot_graph.del_edge(src, dest)
        # Update the context
        self.dot_ctxt.update(fn_name)

    def absorb_IO (self):
        fn_name = dot_manager.absorb_IO.__name__
        dnodes = self.dot_ctxt.dot_nodes
        # Get all IO source nodes
        in_srcs = []
        out_srcs = []
        for n in dnodes:
            n_opcode = n.get("opcode")
            if (n_opcode == "input"): in_srcs.append(n)
            elif (n_opcode == "output"): out_srcs.append(n)
        target_nodes = in_srcs + out_srcs
        in_delim = len(in_srcs)
        for i, target in enumerate(target_nodes):
            target_name = target.get_name()
            if (i < in_delim):
                _, cp_nodes = self.dot_ctxt.get_children(target_name)
            else:
                _, cp_nodes = self.dot_ctxt.get_parents(target_name)
            for cpn in cp_nodes:
                end_name = cpn.get_name()
                if (i < in_delim):
                    cpn.set("direct_in", "true")
                    self.dot_ctxt.dot_graph.del_edge(target_name, end_name)
                else:
                    cpn.set("direct_out", "true")
                    self.dot_ctxt.dot_graph.del_edge(end_name, target_name)
            self.dot_ctxt.dot_graph.del_node(target_name)
        # Update the context
        self.dot_ctxt.update(fn_name)

    # Assign Unique ID to each node, except bridge nodes
    def assign_opID (self):
        fn_name = dot_manager.assign_opID.__name__
        dnodes = self.dot_ctxt.dot_nodes
        op_id = 0
        for n in dnodes:
            if (n.get('opcode') != 'bridge'):
                n.set("opID", op_id)
                op_id += 1

    # Assign rank attributes to vertices
    def assign_rank (self):
        fn_name = dot_manager.assign_rank.__name__
        # We take advantage of dot from GraphViz to generate a DOT file with ranks
        # Visit https://forum.graphviz.org/t/ever-have-questions-about-the-ranking-of-a-large-graph/1511/2 for explanation
        tmp_src_fname = "tmp_rank_src.dot"
        tmp_dest_fname = "tmp_rank_dest.dot"
        self.dot_ctxt.dot_graph.write_raw(tmp_src_fname)
        with open(tmp_dest_fname, 'w') as ofile:
            subprocess.run(["dot", "-Gphase=3", tmp_src_fname], stdout=ofile)
        # create a temporary context to read the dot file with rank info
        t_dctxt = dot_context(self.logger_name)
        t_dctxt.get_graph(tmp_dest_fname)
        # Delete temporary files
        try:
            os.remove(tmp_src_fname)
            os.remove(tmp_dest_fname)
        except Exception as e:
            self.logger.error(f'{fn_name} ||| {e}')
        # Copy over the ranks from temporary context over to this one
        dnodes = self.dot_ctxt.dot_nodes
        for n in dnodes:
            for tn in t_dctxt.dot_nodes:
                if (n.get_name() == tn.get_name()):
                    n.set("rank", tn.get("rank"))
    
    # Make graph bipartite
    def make_bipartite (self):
        fn_name = dot_manager.make_bipartite.__name__
        # Traverse through the graph and add buffer nodes between them
        # when parent and child are on same set (even/odd rank)
        dnodes = self.dot_ctxt.dot_nodes
        for i, n in enumerate(dnodes):
            # Get src node's rank
            src_name = n.get_name()
            src_rank = int(n.get("rank"))
            _, children = self.dot_ctxt.get_children(src_name)
            self.logger.debug(f'{fn_name} ||| Children = {children}')
            for dest in children:
                dest_name = dest.get_name()
                dest_rank = int(dest.get("rank"))
                self.logger.debug(f'{fn_name} ||| src ({src_name}) rank = {src_rank}; dest ({dest_name}) rank = {dest_rank}')
                # compute source and destination node's set
                src_set = src_rank%2
                dest_set = dest_rank%2
                # Check if both nodes have the same set
                if (src_set == dest_set):
                    # Find edge connecting src and dest
                    og_edge = self.dot_ctxt.dot_graph.get_edge(src_name, dest_name)[0]
                    self.logger.debug(f'{fn_name} ||| og_edge = {og_edge}')
                    # Get attributes of edge connecting src and dest and the parent opID
                    og_opID = n.get("opID")
                    og_edge_attr = list(og_edge.get_attributes().items())
                    self.logger.debug(f'{fn_name} ||| og_opID = {og_opID}, og_edge_attributes = {og_edge_attr}')
                    # Split the edge into two, bridged by a bridge/routing node
                    # Copy parent 'opID' to facilitate node level configuration 
                    # (MUX) post edge placement during mapping
                    bridge_name = "bridge_"+str(i)
                    bridge_node_attr = [("opcode", "bridge"), ("opID", og_opID), ("rank", str(src_rank+1))]
                    bridge_node = self.dot_ctxt.new_node(bridge_name, bridge_node_attr)
                    self.logger.debug(f'{fn_name} ||| Created new bridge | name = {bridge_node.get_name()}, attributes = {list(bridge_node.get_attributes().items())}')
                    bridge_edge_0_attr = [("operand", "any1input")]
                    bridge_edge_1_attr = og_edge_attr
                    bridge_edge_0 = self.dot_ctxt.new_edge(src_name, bridge_name, bridge_edge_0_attr)
                    bridge_edge_1 = self.dot_ctxt.new_edge(bridge_name, dest_name, bridge_edge_1_attr)
                    self.logger.debug(f'{fn_name} ||| Split og_edge through bridge: \n edge_0_name = {bridge_edge_0.get_source()}, attributes = {list(bridge_edge_0.get_attributes().items())} \n edge_1_name = {bridge_edge_1.get_source()}, attributes = {list(bridge_edge_1.get_attributes().items())}')
                    self.dot_ctxt.dot_graph.del_edge(src_name, dest_name)
                    self.dot_ctxt.dot_graph.add_node(bridge_node)
                    self.dot_ctxt.dot_graph.add_edge(bridge_edge_0)
                    self.dot_ctxt.dot_graph.add_edge(bridge_edge_1)
        # Update graph
        self.dot_ctxt.update(fn_name)

    # Unroll the DFG
    def unroll (self, unroll_factor: int=1, breadth: int=1, depth: int=1, offset: int=0, incremental: bool=False) -> bool:
        fn_name = dot_manager.unroll.__name__
        ret_val = True
        # Sanity check for unroll factor
        # Unroll_factor must be a product of breadth (--) and depth (|)
        if (not incremental and unroll_factor != (breadth * depth)):
            self.logger.error(f'{fn_name} ||| Product of depth and breadth must equal unroll-factor !')
            ret_val = False
        elif (incremental and offset < 0):
            self.logger.error(f'{fn_name} ||| Incremental unrolling cannot have a negative offset !')
            ret_val = False
        if (unroll_factor > 1 and ret_val):
            # Get og nodes and edges
            dnodes = self.dot_ctxt.dot_nodes
            dedges = self.dot_ctxt.dot_edges
            # New nodes and edges
            n_dnodes = []
            n_dedges = []
            self.logger.debug(f'{fn_name} ||| Unrolling DFG by {unroll_factor}')
            for i in range(breadth):
                unroll_inc = 0
                for j in range(depth):
                    unroll_suffix = f'_{i*depth+j}'
                    # Add a copy of nodes
                    for n in dnodes:
                        t_node_name = n.get_name() + unroll_suffix
                        t_node_attr = n.get_attributes()
                        if (incremental):
                            t_node_rank = int(t_node_attr['rank']) + unroll_inc + offset
                        else:
                            t_node_rank = int(t_node_attr['rank']) + self.dot_ctxt.dot_max_rank * j + offset
                        t_node_attr['rank'] = str(t_node_rank)
                        t_node_attr_list = list(t_node_attr.items())
                        t_node = self.dot_ctxt.new_node(t_node_name, t_node_attr_list)
                        n_dnodes.append(t_node)
                    # Add a copy of edges
                    for e in dedges:
                        t_edge_src_name = e.get_source() + unroll_suffix
                        t_edge_dest_name = e.get_destination() + unroll_suffix
                        t_edge_attr_list = list(e.get_attributes().items())
                        t_edge = self.dot_ctxt.new_edge(t_edge_src_name, t_edge_dest_name, t_edge_attr_list)
                        n_dedges.append(t_edge)
                    unroll_inc += 1
            # Delete existing edges and nodes from graph
            for n in dnodes:
                self.dot_ctxt.dot_graph.del_node(n.get_name())
            for e in dedges:
                self.dot_ctxt.dot_graph.del_edge(e.get_source(), e.get_destination())
            # Add new nodes and edges to graph
            for n in n_dnodes:
                self.dot_ctxt.dot_graph.add_node(n)
            for e in n_dedges:
                self.dot_ctxt.dot_graph.add_edge(e)
            # Update graph
            self.dot_ctxt.update(fn_name)
        return ret_val
    
    # Make all opcodes lowercase
    def make_lowerCase (self) -> None:
        fn_name = dot_manager.make_lowerCase.__name__
        dnodes = self.dot_ctxt.dot_nodes
        for n in dnodes:
            op = n.get('opcode')
            n.set('opcode', op.lower())

    # Print the dot file from dot_context
    def write_dot (self, dest_fname: str=""):
        self.dot_ctxt.dot_graph.write_raw(dest_fname)

def _test():
    fn_name = _test.__name__
    cwd = os.getcwd()

    # CMD parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', action='store', default="", dest='dot_file', help='DOT file to parse')
    parser.add_argument('-u', action='store', type=int, default=1, dest='dot_unroll', help='Unroll factor of DFG')
    parser.add_argument('-b', action='store', type=int, default=1, dest='dot_unroll_breadth', help='Unroll breadth')
    parser.add_argument('-d', action='store', type=int, default=1, dest='dot_unroll_depth', help='Unroll depth')
    parser.add_argument('-o', action='store', type=int, default=0, dest='dot_unroll_offset', help='Unroll depth offset')
    parser.add_argument('-I', action='store_true', dest='dot_unroll_incremental', help='Incremental unrolling in depth')
    args = parser.parse_args()

    # Setup Logging
    logger_name = "dot_manager"
    log_fname = "dot_manager.log"
    log_path = os.path.join(cwd, 'logs', log_fname)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)               # The level should be lowest level set in handlers
    log_format = logging.Formatter(fmt='%(asctime)s.%(msecs)03d - [%(levelname)s] ||| %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    # Stream Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_format)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    # File Handler
    file_handler = logging.FileHandler(log_path, mode='w')
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # Dot src path
    dot_fpath = os.path.join(cwd, 'dots/srcs', args.dot_file)
    # Dot Manager
    dot_man = dot_manager(logger_name)
    dot_man.gen_dot_context(dot_fpath)
    # Absorb constants
    dot_man.absorb_constants()
    # Absorb reflexive edges
    dot_man.absorb_reflexive()
    # Absorb IO
    dot_man.absorb_IO()
    # Assign opID to each node
    dot_man.assign_opID()
    # Assign rank to nodes
    dot_man.assign_rank()
    # Make the graph bipartite
    dot_man.make_bipartite()
    # Make all opcodes lowercase
    dot_man.make_lowerCase()
    # Unroll DFG
    if (dot_man.unroll(args.dot_unroll, args.dot_unroll_breadth, args.dot_unroll_depth, args.dot_unroll_offset, args.dot_unroll_incremental)):
        # Print Dot file
        dest_dot_unroll_desc = f'u{args.dot_unroll}b{args.dot_unroll_breadth}d{args.dot_unroll_depth}o{args.dot_unroll_offset}'
        dest_dot_desc = dest_dot_unroll_desc + 'i' if (args.dot_unroll_incremental) else dest_dot_unroll_desc
        dest_fname = str(args.dot_file).split('/')[-1].replace('.dot', f'_{dest_dot_desc}_output.dot')
        dest_fpath = os.path.join(cwd, 'dots/results', dest_fname)
        dot_man.write_dot(dest_fpath)

if __name__ == "__main__":
    _test()
