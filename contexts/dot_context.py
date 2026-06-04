"""
Context for dot file
"""

import logging
import pydot
import os

class dot_context:

    def __init__ (self, logger_name: str='', log_level: int=logging.INFO, log_dir: str='logs'):
        # Logger setup
        self.logger_name = None
        self.logger = None
        if (logger_name):
            self.logger_name = logger_name
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger_name = self.__class__.__name__
            self.logger = self.log_setup(self.logger_name, log_level, log_dir)
        # State vars
        self.dot_fpath = None        # Path to the dot_file for this context
        self.dot_graph = None
        self.dot_nodes = []
        self.dot_edges = []
        self.dot_max_rank = None
        self.node_meta = {}
    
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

    def get_node_meta (self) -> None:
        fn_name = dot_context.get_node_meta.__name__
        # Traverse through all nodes and populate node metadata {name:{fanin:int, parents:list, fanout:int, children:list, attributes:list}}
        max_rank = 0
        n_meta = {}
        for n in self.dot_nodes:
            # Add node
            n_name = n.get_name()
            n_meta[n_name] = {}
            #self.logger.debug(f'{fn_name} ||| Current node = {n_name}:')
            # Find metadata
            n_rank = n.get('rank')
            if (n_rank is not None):
                n_rank = int(n_rank)
                if (n_rank > max_rank):
                    max_rank = n_rank
            fin_cnt = 0
            fout_cnt = 0
            p_names = []
            c_names = []
            for e in self.dot_edges:
                e_src = e.get_source()
                e_dst = e.get_destination()
                #self.logger.debug(f'{fn_name} ||| Current Edge = ({e_src}, {e_dst}):')
                if (e_dst == n_name):
                    fin_cnt += 1
                    p_names.append(e_src)
                if (e_src == n_name):
                    fout_cnt += 1
                    c_names.append(e_dst)
            n_meta[n_name]["fanin"] = fin_cnt
            n_meta[n_name]["parents"] = p_names
            n_meta[n_name]["fanout"] = fout_cnt
            n_meta[n_name]["children"] = c_names
            n_meta[n_name]["attributes"] = list(n.get_attributes().items())
        self.dot_max_rank = max_rank
        self.node_meta = n_meta
        #self.logger.debug(f'{fn_name} ||| Node Metadata = {self.node_meta}')

    # Read dot file and get the graph
    def get_graph (self, dot_fpath: str="") -> None:
        fn_name = dot_context.get_graph.__name__
        try:
            self.dot_graph = pydot.graph_from_dot_file(dot_fpath)[0]
        except Exception as e:
            self.logger.error(f'{fn_name} ||| {e}')
        # Store file path
        self.dot_fpath = dot_fpath
        # Populate nodes and edges
        self.dot_nodes = self.dot_graph.get_nodes()
        self.dot_edges = self.dot_graph.get_edges()
        self.logger.debug(f'{fn_name} ||| Read dot_file \"{dot_fpath}\": \n dot_nodes = {[n.get_name() for n in self.dot_nodes]} \n dot_edges = {[e.get_source() for e in self.dot_edges]}')
        # Get node metadata
        self.get_node_meta()

    # Update context from graph
    def update (self, caller_name: str="") -> None:
        fn_name = dot_context.update.__name__
        self.dot_nodes = self.dot_graph.get_nodes()
        self.dot_edges = self.dot_graph.get_edges()
        # Print
        self.logger.debug(f'{fn_name} ||| Updated graph ({caller_name}): \n New dot_nodes = {[n.get_name() for n in self.dot_nodes]} \n New dot_edges = {[e.get_source() for e in self.dot_edges]}')
        # Get node metadata
        self.get_node_meta()

    def get_attribute (self, node_name: str="", attribute_name: list=[]) -> list | None:
        fn_name = dot_context.get_attribute.__name__
        attr = None
        if (node_name):
            for n in self.dot_nodes:
                if (n.get_name() == node_name):
                    attr = []
                    for key in attribute_name:
                        attr.append((key, n.get(key)))
                    break
        return attr
    
    def set_attribute (self, node_name: str="", attribute_kv: list=[]) -> None:
        fn_name = dot_context.set_attribute.__name__
        for n in self.dot_nodes:
            if (n.get_name() == node_name):
                for pair in attribute_kv:
                    key = pair[0]
                    val = pair[1]
                    if (val is not None):
                        n.set(key, val)
                break
    
    def get_children (self, node_name: str="") -> tuple:
        fn_name = dot_context.get_children.__name__
        # Find all destination nodes the const sources connect to
        # Similarly get the fanout of each const source node
        children = []
        node_fanout = []
        if (node_name):
            # Find corresponding node metadata
            for c_name in self.node_meta[node_name]["children"]:
                # All nodes are assumed to have unique names, hence only return the first node in list
                cn = self.dot_graph.get_node(c_name)
                if (cn):
                    if (len(cn) > 1):
                        self.logger.warning(f'{fn_name} ||| Multiple nodes with identical name; Returning first occurence')
                    children.append(cn[0])
            node_fanout.append(self.node_meta[node_name]["fanout"])
        return (node_fanout, children)
    
    def get_parents (self, node_name: str="") -> tuple:
        fn_name = dot_context.get_parents.__name__
        # Find parents and fanin of sources
        parents = []
        node_fanin = []
        if (node_name):
            # Find corresponding node's metadata
            for p_name in self.node_meta[node_name]["parents"]:
                # All nodes are assumed to have unique names, hence only return the first node in list
                pn = self.dot_graph.get_node(p_name)
                if (pn):
                    if (len(pn) > 1):
                        self.logger.warning(f'{fn_name} ||| Multiple nodes with identical name; Returning first occurence')
                    parents.append(pn[0])
            node_fanin.append(self.node_meta[node_name]["fanin"])
        return (node_fanin, parents)
    
    def new_node (self, node_name: str="", node_attributes_kv: list=[]) -> pydot.Node | None:
        fn_name = dot_context.new_node.__name__
        ret_node = None
        if (node_name):
            ret_node = pydot.Node(node_name)
            if (node_attributes_kv):
                for pair in node_attributes_kv:
                    ret_node.set(pair[0], pair[1])
        return ret_node
    
    def new_edge (self, src_name: str="", dest_name: str="", edge_attributes_kv: list=[]) -> pydot.Edge | None:
        fn_name = dot_context.new_edge.__name__
        ret_edge = None
        if (src_name and dest_name):
            ret_edge = pydot.Edge(src_name, dest_name)
            if (edge_attributes_kv):
                for pair in edge_attributes_kv:
                    ret_edge.set(pair[0], pair[1])
        return ret_edge
    
    def print_data (self) -> None:
        fn_name = dot_context.print_data.__name__
        self.logger.debug(f'{fn_name} ||| Context data: \n dot_nodes = {[n.get_name() for n in self.dot_nodes]} \n dot_edges = {[e.get_source() for e in self.dot_edges]}')
    