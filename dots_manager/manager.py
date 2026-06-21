
"""
Builds the graph from .dot file.
Abosrbs constants into a vertex's attribute. -> const=x
All reflexive edges of a vertex are absorbed into its attribute. -> reflexive=true
Add bridge/routing vertices to maintain bipartite traversal along edges.
Reduce bridges to minimize routing nodes.

WARNING:
Why the number of blocks matter in a DFG:-
Consider the case -> n0=rank0, n1=rank1, n3=rank4
A In a 2 block CGRA, this will require no bridge nodes,
whereas in a 4 block CGRA, this will require 2 bridge nodes.
The placer is fast but dumb, it places nodes as they appear in 
the list. Hence, does not check for legality (distance between child and parent)
before placing the nodes. A check is possible by using DFS traversal in placer,
to insert a child-parent distance check (dist==1). But for now simply check using
the block count parameter (B) attached to the output file.

NOTE: (1) Graph CAN be cyclic, as we take advantage of GraphViz to
          establish node ranks. GraphViz takes care of breaking cycles.
      (2) Unroll capabilites are only for testing purposes. This does not 
          modify the constants in the nodes responsible for proper unrolling.
      (3) Fan-in/out legalization is only for data-paths.
          Since, there is only on predicate in/out in the CGRA.
          So ensure predicate fanin/outs are legalized in compiler!

TODO: (1) Annotating edges needs to be part of the compiler,
          this is not the right place to annotate the edges.
"""

import logging
import os
import argparse
import subprocess
from contexts.dot_context import dot_context
from contexts.cgra_context import cgra_context

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

    # Traverse dot_context and aborb all constants into their vertices
    def absorb_constants (self, dual_reg: bool=False):
        fn_name = dot_manager.absorb_constants.__name__
        dnodes = self.dot_ctxt.dot_nodes
        marked_nodes = []
        for n in dnodes:
            n_name = n.get_name()
            if (n_name not in marked_nodes):
                # If there is no relexive attribute, the get() will return None
                # take advantage of that to transform the n_reflexive into a flag
                n_reflexive = n.get('reflexive') if (not dual_reg) else None
                # Get parents
                n_parents = self.dot_ctxt.get_parents(n_name)
                for p in n_parents:
                    p_name = p.get_name()
                    p_opcode = p.get('opcode')
                    immediate_en_attr = [('immediate', 'true')]
                    p_const_attr = self.dot_ctxt.get_attribute(p_name, self.const_type) + immediate_en_attr
                    # Check if parent is a constant and its legal to absorb
                    if (p_opcode == 'const' and n_reflexive is None):
                        # Absorb the parent
                        self.dot_ctxt.set_attribute(n_name, p_const_attr)
                        # Delete edge and mark node for removal
                        self.dot_ctxt.dot_graph.del_edge(p_name, n_name)
                        if (p_name not in marked_nodes):
                            marked_nodes.append(p_name)
                        break
        # Remove all marked nodes
        for m in marked_nodes:
            self.dot_ctxt.dot_graph.del_node(m)
        # Update context
        self.dot_ctxt.update(fn_name)

    # Absorb IO nodes, only one absorbption per node possible.
    def absorb_IO (self):
        fn_name = dot_manager.absorb_IO.__name__
        dnodes = self.dot_ctxt.dot_nodes
        # Get all IO source nodes
        marked_nodes = []
        for n in dnodes:
            n_name = n.get_name()
            if (n_name not in marked_nodes):
                n_parents = self.dot_ctxt.get_parents(n_name)
                n_children = self.dot_ctxt.get_children(n_name)
                # Look for input nodes to absorb
                for p in n_parents:
                    p_name = p.get_name()
                    p_opcode = p.get('opcode')
                    if (p_opcode == 'input'):
                        n.set('direct_in', 'true')
                        self.dot_ctxt.dot_graph.del_edge(p_name, n_name)
                        if (p_name not in marked_nodes):
                            marked_nodes.append(p_name)
                        break
                # Look for output nodes to absorb
                for c in n_children:
                    c_name = c.get_name()
                    c_opcode = c.get('opcode')
                    absorb_full = n.get('direct_in')
                    if (c_opcode == 'output' and absorb_full is None):
                        n.set('direct_out', 'true')
                        self.dot_ctxt.dot_graph.del_edge(n_name, c_name)
                        if (c_name not in marked_nodes):
                            marked_nodes.append(c_name)
                        break
        for m in marked_nodes:
            self.dot_ctxt.dot_graph.del_node(m)
        # Update the context
        self.dot_ctxt.update(fn_name)

    def annotate_data_edges (self, predicate_enable: bool=False) -> None:
        fn_name = dot_manager.annotate_data_edges.__name__
        dedges = self.dot_ctxt.dot_edges
        for e in dedges:
            e_src = e.get_source()
            src_node = self.dot_ctxt.get_node(e_src)
            src_opcode = src_node.get('opcode')
            # Add data label to all edges except those originating
            # from icmp nodes, when predication is enabled.
            if (src_opcode == 'icmp' and predicate_enable):
                continue
            e.set('data', 'true')
        # Update graph
        self.dot_ctxt.update(fn_name)

    def annotate_predicate_edges (self, predicate_enable: bool=False) -> None:
        fn_name = dot_manager.annotate_predicate_edges.__name__
        dedges = self.dot_ctxt.dot_edges
        for e in dedges:
            e_src = e.get_source()
            src_node = self.dot_ctxt.get_node(e_src)
            src_opcode = src_node.get('opcode')
            if (src_opcode == 'icmp' and predicate_enable):
                e.set('predicate', 'true')
        # Update graph
        self.dot_ctxt.update(fn_name)

    def legalize_fanin (self, in_edge_list: list, dest_node, in_edge_count: int, max_fanin: int, base_new_node_count: int=0) -> None:
        fn_name = dot_manager.legalize_fanin.__name__
        dest_name = dest_node.get_name()
        dest_attr = list(dest_node.get_attributes().items())
        new_in_edge_list = []
        new_node_count = base_new_node_count
        for ie_sel in range(0, in_edge_count, max_fanin):
            if (ie_sel+1 == in_edge_count):
                new_in_edge_list.append(in_edge_list[ie_sel])
                break
            else:
                # Add a new node to consolidate 2 edges from list
                new_node_name = dest_name + f'_fin_{new_node_count}'
                new_node_attr = dest_attr
                new_node = self.dot_ctxt.new_node(new_node_name, new_node_attr)
                self.dot_ctxt.dot_graph.add_node(new_node)
                new_node_count += 1
                # Connect the edges to new node and delete the old ones
                ie_0_src = in_edge_list[ie_sel].get_source()
                ie_0_attr = list(in_edge_list[ie_sel].get_attributes().items())
                ie_1_src = in_edge_list[ie_sel+1].get_source()
                ie_1_attr = list(in_edge_list[ie_sel+1].get_attributes().items())
                #self.logger.debug(f'{fn_name} ||| ie_0 = {ie_0_src} -> {new_node_name}, ie_0_attr = {ie_0_attr} | ie_1 = {ie_1_src} -> {new_node_name}, ie_1_attr = {ie_1_attr}')
                new_ie_0 = self.dot_ctxt.new_edge(ie_0_src, new_node_name, ie_0_attr)
                new_ie_1 = self.dot_ctxt.new_edge(ie_1_src, new_node_name, ie_1_attr)
                self.dot_ctxt.dot_graph.del_edge(ie_0_src, dest_name)
                self.dot_ctxt.dot_graph.del_edge(ie_1_src, dest_name)
                # Create output edge from new_node towards destination and append this edge to new_edge_list
                new_edge_attr = ie_0_attr + [('merge', 'true')]
                self.logger.debug(f'{fn_name} ||| new_edge = {new_node_name} -> {dest_name}, new_edge_attr = {new_edge_attr}')
                new_edge = self.dot_ctxt.new_edge(new_node_name, dest_name, new_edge_attr)
                new_in_edge_list.append(new_edge)
                self.dot_ctxt.dot_graph.add_edge(new_ie_0)
                self.dot_ctxt.dot_graph.add_edge(new_ie_1)
                self.dot_ctxt.dot_graph.add_edge(new_edge)
        if (len(new_in_edge_list) > max_fanin):
            # Recursive reduce
            self.legalize_fanin(new_in_edge_list, dest_node, len(new_in_edge_list), max_fanin, new_node_count)
    
    def legalize_fanout (self, out_edge_list: list, src_node, out_edge_count: int, max_fanout: int, base_new_node_count: int=0) -> None:
        fn_name = dot_manager.legalize_fanout.__name__
        src_name = src_node.get_name()
        src_attr = list(src_node.get_attributes().items())
        new_out_edge_list = []
        new_node_count = base_new_node_count
        for oe_sel in range(0, out_edge_count, max_fanout):
            self.logger.debug(f'{fn_name} ||| Iter[{oe_sel}]')
            if (oe_sel+1 == out_edge_count):
                new_out_edge_list.append(out_edge_list[oe_sel])
                break
            else:
                # Add a new node to expand 2 edges from list
                new_node_name = src_name + f'_fout_{new_node_count}'
                new_node_attr = [('opcode', 'split')]
                new_node = self.dot_ctxt.new_node(new_node_name, new_node_attr)
                # Add new_node to graph
                self.dot_ctxt.dot_graph.add_node(new_node)
                new_node_count += 1
                # Connect the edges to new node and delete the old ones
                oe_0_dest = out_edge_list[oe_sel].get_destination()
                oe_0_attr = list(out_edge_list[oe_sel].get_attributes().items())
                oe_1_dest = out_edge_list[oe_sel+1].get_destination()
                oe_1_attr = list(out_edge_list[oe_sel+1].get_attributes().items())
                #self.logger.debug(f'{fn_name} ||| oe_0 = {new_node_name} -> {oe_0_dest}, oe_0_attr = {oe_0_attr} | oe_1 = {new_node_name} -> {oe_1_dest}, oe_1_attr = {oe_1_attr}')
                new_oe_0 = self.dot_ctxt.new_edge(new_node_name, oe_0_dest, oe_0_attr)
                new_oe_1 = self.dot_ctxt.new_edge(new_node_name, oe_1_dest, oe_1_attr)
                self.dot_ctxt.dot_graph.del_edge(src_name, oe_0_dest)
                self.dot_ctxt.dot_graph.del_edge(src_name, oe_1_dest)
                # Create output edge from new_node towards destination and append this edge to new_edge_list
                new_edge_attr = oe_0_attr + [('split', 'true')]
                new_edge = self.dot_ctxt.new_edge(src_name, new_node_name, new_edge_attr)
                new_out_edge_list.append(new_edge)
                #self.logger.debug(f'{fn_name} ||| new_edge = {src_name} -> {new_node_name}, new_edge_attr = {new_edge_attr}')
                # Add new edges to graph
                self.dot_ctxt.dot_graph.add_edge(new_oe_0)
                self.dot_ctxt.dot_graph.add_edge(new_oe_1)
                self.dot_ctxt.dot_graph.add_edge(new_edge)
        if (len(new_out_edge_list) > max_fanout):
            # Recursive reduce
            self.legalize_fanout(new_out_edge_list, src_node, len(new_out_edge_list), max_fanout, new_node_count)

    # Legalize the graph by fixing fanin/out of nodes
    def legalize_incidence (self, max_incidence: int=None):
        fn_name = dot_manager.legalize_incidence.__name__
        if (max_incidence is None or max_incidence < 2):
            err_msg = f'{fn_name} ||| Please provide maximum_incidence value ( >= 2) to legalize DFG !'
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        dnodes = self.dot_ctxt.dot_nodes
        for n in dnodes:
            n_name = n.get_name()
            n_parents = self.dot_ctxt.get_parents(n_name)
            n_children = self.dot_ctxt.get_children(n_name)
            # Consider only the data-edges
            n_fanin = 0
            n_fanout = 0
            ie_list = []
            oe_list = []
            for p in n_parents:
                p_name = p.get_name()
                ie = self.dot_ctxt.get_edge(p_name, n_name)
                if (ie.get('data') is not None):
                    n_fanin += 1
                    ie_list.append(ie)
            for c in n_children:
                c_name = c.get_name()
                oe = self.dot_ctxt.get_edge(n_name, c_name)
                if (oe.get('data') is not None):
                    n_fanout += 1
                    oe_list.append(oe)
            # Legalize fanin
            if (n_fanin > max_incidence):
                self.legalize_fanin(ie_list, n, n_fanin, max_incidence)
            # Legalize fanout
            if (n_fanout > max_incidence):
                self.legalize_fanout(oe_list, n, n_fanout, max_incidence)
        # Update graph
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
        # Update graph
        self.dot_ctxt.update(fn_name)
    
    # Make graph bipartite
    def make_bipartite (self, blocks: int=2):
        fn_name = dot_manager.make_bipartite.__name__
        if (blocks is None or blocks < 2):
            err_msg = f'{fn_name} ||| Please provide CGRA physical blocks value ( >= 2) to legalize DFG !'
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        # Traverse through the graph and add buffer nodes between them
        # when parent and child are not on adjacent sets.
        dnodes = self.dot_ctxt.dot_nodes
        # Since the DFG gets folded over the blocks during linear traversal.
        # We work with the relative rank of the node post DFG folding.
        # This enables us to work with displacement (shortest path) and constrains 
        # the relative rank into a triangle wave within the interval [0, blocks).
        get_mod_rank = lambda r, b: int(r%(2*(b-1)))
        get_rel_rank = lambda r, b: (b-1) - abs(get_mod_rank(r, b)-(b-1))
        get_node_region = lambda r, b: 1 if (get_mod_rank(r,b) < b-1) else -1
        get_bridge_dir = lambda src, dst, b: 1 if ((get_rel_rank(dst, b)-get_rel_rank(src, b))*get_node_region(src, b) > 0) else -1
        get_mod_shadow_rank = lambda r, b: 0 if (get_mod_rank(r, b) == 0) else 2*(b-1) - get_mod_rank(r, b)
        get_shadow_rank = lambda r, b: r + (get_mod_shadow_rank(r, b) - get_mod_rank(r, b))
        # Once the relative ranks are obtained, the absolute distance between the rank is computed.
        # For distances greater than 1, the appropriate number of bridge nodes are added to the edge.
        # NOTE: The bridge nodes must be constructed from the perspective of the destination node.
        #       i.e., in decreasing order of rank from the destination. This is to ensure the placer
        #       places the bridge nodes in the appropriate region.
        for n in dnodes:
            # Get src node's rank
            src_name = n.get_name()
            src_rank = int(n.get("rank"))
            rel_src_rank = get_rel_rank(src_rank, blocks)
            children = self.dot_ctxt.get_children(src_name)
            self.logger.debug(f'{fn_name} ||| Children = {children}')
            for cid, dest in enumerate(children):
                dest_name = dest.get_name()
                dest_rank = int(dest.get("rank"))
                rel_dest_rank = get_rel_rank(dest_rank, blocks)
                self.logger.debug(f'{fn_name} ||| src ({src_name}) rank = {src_rank}, rel_src_rank = {rel_src_rank}; dest ({dest_name}) rank = {dest_rank}, rel_dest_rank = {rel_dest_rank}')
                # Check if both nodes are not adjacent
                set_diff = abs(rel_dest_rank-rel_src_rank)
                # If they are on the same block, i.e., set_diff = 0, force them appart by a single block
                forced_set_diff = 2 if (set_diff == 0) else set_diff
                max_bridges = forced_set_diff-1
                if (set_diff != 1):
                    # Find edge connecting src and dest
                    og_edge = self.dot_ctxt.get_edge(src_name, dest_name)
                    self.logger.debug(f'{fn_name} ||| og_edge = {og_edge}')
                    # Get attributes of edge connecting src and dest and the parent opID
                    og_opID = n.get("opID")
                    og_edge_attr = list(og_edge.get_attributes().items())
                    self.logger.debug(f'{fn_name} ||| og_opID = {og_opID}, og_edge_attributes = {og_edge_attr}')
                    bridge_seed_rank = src_rank+1 if (get_bridge_dir(src_rank, dest_rank, blocks) > 0) else get_shadow_rank(src_rank, blocks)+1
                    bridge_edge_attr = []
                    if (og_edge.get('data') is not None):
                        bridge_edge_attr.append(('data', 'true'))
                    if (og_edge.get('predicate') is not None):
                        bridge_edge_attr.append(('predicate', 'true'))

                    # Split the edge, bridged by a bridge/routing node
                    # Copy parent 'opID' to facilitate node level configuration 
                    # (MUX) post edge placement during mapping

                    # Main
                    self.logger.debug(f'{fn_name} ||| forced_set_diff = {forced_set_diff}, max_bridges = {max_bridges}')
                    for b in range(max_bridges):
                        bridge_base_name = src_name if (b == 0) else f'extd_{src_name}_{cid}_{b-1}'
                        bridge_name = f'extd_{src_name}_{cid}_{b}'
                        bridge_rank = str(bridge_seed_rank+b)
                        bridge_node_attr = [("opcode", "bridge"), ("opID", og_opID), ("rank", str(bridge_rank))]
                        bridge_node = self.dot_ctxt.new_node(bridge_name, bridge_node_attr)
                        self.dot_ctxt.dot_graph.add_node(bridge_node)
                        self.logger.debug(f'{fn_name} ||| Created new bridge | name = {bridge_node.get_name()}, attributes = {list(bridge_node.get_attributes().items())}')
                        bridge_edge = self.dot_ctxt.new_edge(bridge_base_name, bridge_name, bridge_edge_attr)
                        self.dot_ctxt.dot_graph.add_edge(bridge_edge)
                    # Epilogue
                    bridge_name = f'extd_{src_name}_{cid}_{max_bridges-1}'
                    bridge_edge_attr = og_edge_attr
                    bridge_dest_edge = self.dot_ctxt.new_edge(bridge_name, dest_name, bridge_edge_attr)
                    self.dot_ctxt.dot_graph.add_edge(bridge_dest_edge)
                    # Delete OG edge
                    self.dot_ctxt.dot_graph.del_edge(src_name, dest_name)
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
            max_rank = self.dot_ctxt.dot_max_rank
            # New nodes and edges
            n_dnodes = []
            n_dedges = []
            self.logger.debug(f'{fn_name} ||| Unrolling DFG by {unroll_factor} | DFG_max_rank = {max_rank}')
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
                            t_node_rank = int(t_node_attr['rank']) + max_rank * j + offset
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

def main():
    fn_name = main.__name__
    cwd = os.getcwd()

    # CMD parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', action='store', default="", dest='dot_file', help='DOT file to parse')
    parser.add_argument('--auto', action='store_true', dest='dot_auto', help='Automate DFG generation')
    parser.add_argument('--cgra-radix', action='store', type=int, default=None, dest='dot_max_incidence', help='Max incidence of DFG node')
    parser.add_argument('--cgra-blocks', action='store', type=int, default=None, dest='dot_blocks', help='Number of physical blocks in CGRA')
    parser.add_argument('-u', action='store', type=int, default=1, dest='dot_unroll', help='Unroll factor of DFG')
    parser.add_argument('-b', action='store', type=int, default=1, dest='dot_unroll_breadth', help='Unroll breadth')
    parser.add_argument('-d', action='store', type=int, default=1, dest='dot_unroll_depth', help='Unroll depth')
    parser.add_argument('-o', action='store', type=int, default=0, dest='dot_unroll_offset', help='Unroll depth offset')
    parser.add_argument('-I', action='store_true', dest='dot_unroll_incremental', help='Incremental unrolling in depth')
    parser.add_argument('-P', action='store_true', dest='dot_predicate_enable', help='Enable flag indicating arch supports predication')
    parser.add_argument('--dual-reg', action='store_true', dest='dot_dual_reg', help='Flag to enable absorbtion of constants on top of reflexive')
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

    # Print setup
    dest_dot_unroll_desc = f'B{args.dot_blocks}_DR{1 if (args.dot_dual_reg) else 0}_u{args.dot_unroll}b{args.dot_unroll_breadth}d{args.dot_unroll_depth}o{args.dot_unroll_offset}_P{1 if (args.dot_predicate_enable) else 0}'
    dest_dot_desc = dest_dot_unroll_desc + 'i' if (args.dot_unroll_incremental) else dest_dot_unroll_desc
    dest_fname = str(args.dot_file).split('/')[-1].replace('.dot', f'_{dest_dot_desc}_output.dot')
    dest_fpath = os.path.join(cwd, 'dots/results', dest_fname)

    # Paths
    dot_fpath = os.path.join(cwd, 'dots/srcs', args.dot_file)
    cgra_cfg_fpath = os.path.join(cwd, 'configs', 'cgra_config.yaml')
    pe_cfg_fpath = os.path.join(cwd, 'configs', 'pe_config.yaml')

    # CGRA context
    cgra_ctxt = cgra_context(cgra_cfg_fpath, pe_cfg_fpath, 'CGRA')

    # State var setup
    auto_en = args.dot_auto
    dual_reg_en = args.dot_dual_reg
    predicate_en = args.dot_predicate_enable
    max_incidence = cgra_ctxt.cgra_radix if (auto_en) else args.dot_max_incidence
    blocks = cgra_ctxt.cgra_phy_blocks if (auto_en) else args.dot_blocks

    # Dot Manager
    dot_man = dot_manager(logger_name)

    # DFG gen
    while (True):
        dot_man.gen_dot_context(dot_fpath)
        # Absorb reflexive edges
        dot_man.absorb_reflexive()
        # Absorb constants
        dot_man.absorb_constants(dual_reg_en)
        # Absorb IO
        dot_man.absorb_IO()
        # Annotate edges
        dot_man.annotate_data_edges(predicate_en)
        dot_man.annotate_predicate_edges(predicate_en)
        # Legalize DFG incidence
        dot_man.legalize_incidence(max_incidence)
        # Assign rank to nodes
        dot_man.assign_rank()
        # Unroll DFG
        if (dot_man.unroll(args.dot_unroll, args.dot_unroll_breadth, args.dot_unroll_depth, args.dot_unroll_offset, args.dot_unroll_incremental)):
            # Assign opID to each node
            dot_man.assign_opID()
            # Make the graph bipartite
            dot_man.make_bipartite(blocks)
            # Make all opcodes lowercase
            dot_man.make_lowerCase()
            # Validate
            total_nodes = len(dot_man.dot_ctxt.dot_nodes)
            logger.info(f'{fn_name} ||| Blocks = {blocks} | Total nodes = {total_nodes}')
            if (auto_en):
                est_cgra_size = blocks * cgra_ctxt.cgra_block_size
                if (total_nodes > est_cgra_size):
                    blocks += 1
                    logger.info(f'{fn_name} ||| Generated DFG nodes exceeds estimated CGRA size, re-run with blocks = {blocks}')
                    continue
            else:
                in_str = input('Write dot file (y/n): ')
                if (in_str and in_str.lower()[0] == 'n'):
                    logger.info(f'{fn_name} ||| Dot file write failed !')
                    break
            # Print Dot file
            dot_man.write_dot(dest_fpath)
            logger.info(f'{fn_name} ||| Dot file write succeeded !')
            break

if __name__ == "__main__":
    main()
