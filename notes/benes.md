# benes.py

## General Algorithm
For better understanding of the algorithm, check this paper out: "Design and implementation of fast and hardware-efficient parallel processing elements to set full and partial permutations in Beneš networks." by Labson Koloko, Takahiro Matsumoto, and Hitoshi Obara

## Methods

### `reset_benes()`
Resets all the switch-control-bits.

### `propogate(stage: int, perm: list)`
Given a list of source permutation, stage, and switch_setting, propagate the sources towards the stage's destination permutation.

### `prep_pass(stage: int, switch_map: list, src: int, dest: int, perm: list)`
- **Switch Routing Logic**: Since we start by routing the switch-chain through subnet_0 (lower), finding the dest_buddy of cur_switch will lead to a source in the next switch. This source must route through subnet_1, and the buddy of that source (in the next switch) must once again route through subnet_0. Hence, following the switch-chain using the double-buddy switch will always land on a source that must route through subnet_0.
- **Finding Next Switch**: Find the next switch in the chain.
- **Switch Port Pairing**: Each switch is considered to have an even and odd pair of ports. Source-side buddies are always even-odd pairs.
- **Destination Side Buddies**: Depending on the Benes physical structure, destination-side buddies might be even-odd pairs or all even/odd pairs (same parity). In this case, the buddy is also the same parity, spread by stage_split.
- **Chain Completion**: This means the buddy leads back to the chain leader, so we close the loop here and exit.

### `normalize_perm(stage: int, perm: list)`
Normalizes the permutation by removing the LSBs.
Duplicates post-normalization indicate faulty SCB generation in the previous stage, since all destinations in the permutation must be unique at any given stage's input (post-normalization).

### `run(permutation: list)`
Runs the Benes routing algorithm from sources to destinations.
- **Permutation Balancing**: Balances the permutation by assigning random destinations to unassigned sources and rearranging the permutation according to the port list, i.e., all sources must be in ascending order.
- **Destination-Tag-Routing (DTR)**: Performs Destination-Tag-Routing (DTR) for forward passes.
- **Permutation Propagation**: Propagates the current permutation through switches based on SCBs set above and computes the new permutation for the next stage.
- **Route Validation**: Validates if all sources were successfully routed.
