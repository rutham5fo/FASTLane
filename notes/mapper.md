# mapper.py

## Methods

### `run(dot_ctxt: dot_context=None, dot_blocks: int=-1)`
Runs placer on given dot file according to cgra_context built from config files.
- **Sanity check**: Checks if DFG blocks and CGRA blocks match and if DOT Context is available.
- **Mapping Process**: If the placer runs successfully, it then runs the router.
- **Timing**: Measures the run-time of the mapper.
- **Status**: Reports whether the mapping was a success or failure.

### `validate(dot_ctxt: dot_context=None)`
Validates the mapping by checking all edges in the DFG.
- **Edge Validation**: Iterates through each edge in the DOT graph.
- **Source PE Search**: Finds the source Processing Element (PE) in the mapper context.
- **Destination PE Search**: Finds the matching destination PE.
- **Validation Result**: Reports whether the validation was a success or failure.
