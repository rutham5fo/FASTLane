# Auto Experimenter - ANNOTATED (Corrected Implementation)

## Overview
This document annotates the original `auto_exp_multi_block_overload_run.md` with detailed clarifications to ensure correct execution and replicability.

## Instructions Checklist
- [ ] DFG Processing loop and Experiment Pseudo-Code must be in sync (always).

## General Rules
- Minimize token usage by keeping outputs short. All internally generated lists unless explicitly stated must not be printed on standard output to avoid token consumption.
- Due to un-foreseen circumstance, if an edit is required in any other file than those described in Experiment rules, prompt user for approval.
- First run must always be done step-by-step, attaining the approval from user regarding the correctness of your understanding of the task.
- All lists are zero-indexed.
- Do not bother with commands not used in the Experiment.
- You are permitted to execute any non-sudo shell command to progress the experiment.
- Use './.tmp' directory for temp files. Ask user before deleting temp generated files.
- When all steps have been approved, run autonomously till completion of experiment.

## Experiment Rules

### Parameters
- result_dir = 'varBlks_u2b1d2'
- allowed_pes = {'PE_int_alu', 'PE_int_muldiv', 'PE_float_alu', 'PE_float_muldiv'}
- pe_cost = {1, 3, 2, 4} # (corresponding to allowed_pes: PE_int_alu=1, PE_int_muldiv=3, PE_float_alu=2, PE_float_muldiv=4)
- max_block_size = 256
- initial_block_size = 8
- **initial_recall_step (DERIVED, NOT constant)** = `ceil(block_size / (len(allowed_pes) * 4))`

### Block Size Management (CRITICAL)
- The `block_size` in `cgra_config.yaml` is initialized to `initial_block_size` (8) at the start of each DFG mapping iteration.
- **IMPORTANT:** `block_size` is a **per-DFG variable**, not a global constant for all DFGs in a block count.
- `block_size` can grow from `initial_block_size` up to a maximum of `max_block_size` (256) (sequence: 8 → 16 → 32 → 64 → 128 → 256).
- When a mapping fails, check the failure reason:
  - If `Opcode[some_opcode] not supported`: This is a PE type limitation. Consult `pe_config.yaml` and potentially change PE composition. If no suitable PE exists, add DFG to `skipped.log`.
  - If capacity failure (no available PE): **Double the block_size for THAT DFG only** and retry the mapping with the same DFG.
  - Retry loop continues until either SUCCESS, an opcode error occurs, or block_size reaches `max_block_size` (capacity exhausted).

### Composition Constraint
- The number of elements in a block (determined by composition) must always equal `block_size`.
- Example: if `block_size = 16`, composition might be `[{'PE_int': 16}]`, `[{'PE_int': 8}, {'PE_int': 8}]`, `[{'PE_float': 8}, {'PE_int': 8}]`, or `[{'PE_float': 16}]` etc.
- Block composition can only be positive integers or 0.
- Each DFG iteration must start with the initial condition:
  - The CGRA composition must consist of equal amounts of all PE types from `allowed_pes`.
  - Example: if `block_size = 16`, then composition = `[{'PE_int_alu': 4, 'PE_int_muldiv': 4, 'PE_float_alu': 4, 'PE_float_muldiv': 4}]`, etc.
  - `fixed_PE`, `rep_PE` and `vic_PE` are **per-block** variables.
  - `fixed_PE` list is empty.
  - `rep_PE`, `vic_PE` are both None.
  - `recall_step` = `ceil(block_size / (len(allowed_pes) * 4))` (recomputed when block_size changes)

### Block Count Iterations
- Outer loop: iterate `blocks` from 2 to `max_blocks` (8 in this case).
- For each `blocks` value, set:
  - `blocks` in cgra_config.yaml = current block count
  - `overload` = 0 if blocks == 2, else 1
  - `block_size` = 8 (reset for this block count iteration)
- Then process all DFGs matching pattern `*_B<blocks>_*` for that block count.

### DFG Processing Loop (CRITICAL - PER-DFG BLOCK_SIZE AND COMPOSITION VARIATION)
1. For each block count iteration (e.g., blocks=2, 3, 4...):
   2. Find all DFG files: `./dots/results/<result_dir>/*_B<blocks>_*_output.dot`
   3. For each DFG file found:
      - Set local `current_block_size = initial_block_size` (8) (reset for each new DFG)
      - Initialize: `fixed_PE = []`, `rep_PE = None`, `vic_PE = None`, `recall_step = initial_recall_step` (10)
      - Set composition to equal distribution: `[{'PE_int_alu': current_block_size/4, 'PE_int_muldiv': current_block_size/4, 'PE_float_alu': current_block_size/4, 'PE_float_muldiv': current_block_size/4}]`
      - **Retry Loop (for THIS DFG only):**
        - Update `block_size` and `composition` in cgra_config.yaml
        - Run mapper on the DFG
        - Check output for `Mapping: SUCCESS/FAILED`
        - If SUCCESS: record success, move to next DFG
        - If FAILED:
          - If output contains `Opcode[...]`: unsupported opcode error → add DFG to skipped.log, move to next DFG
          - Else: not due to unsupported opcode (capacity/PE placement issue):
            - **Composition Variation Loop (before increasing block_size):**
              - While mapping is failing due to lack of supporting PEs in composition of **CURRENT block** (block mentioned in mapper output):
                - Extract failing opcode and find all PE types from `pe_config.yaml` that support it
                - `rep_PE`, `vic_PE` and `fixed_PE` refer to current block instances
                - Set `rep_PE` as the cheapest PE type (by `pe_cost`) among those that support the opcode
                - If `rep_PE` is same `vic_PE`:
                  - This means the current `vic_PE` dropped below its required minimum value due to a transfer in last iteration. To avoid a loop of transfers, move `vic_PE` to `fixed_PE`.
                - Set `vic_PE` as the most expensive PE type (by `pe_cost`), excluding `rep_PE` and items in `fixed_PE`. If none found, `vic_PE` = None
                - If `vic_PE` is not None:
                  - Transfer `recall_step` PEs from new `vic_PE` to `rep_PE` in composition
                  - If `vic_PE` count in composition has dropped to 0 post transfer:
                    - Move `vic_PE` to `fixed_PE` list (PE is depleted)
                  - re-run mapper
                - Else:
                  - Halve `recall_step` (floor to nearest integer)
                  - If `recall_step == 0`: break from composition loop, proceed to block_size increase
                  - Else: reset to initial composition and conditions (except `recall_step`), re-run mapper
            - If composition variation exhausted or no improvement: `current_block_size *= 2`, reset composition to equal distribution, recompute `recall_step`, go back to retry loop
      - End retry loop (either success or opcode error)

## Experiment Pseudo-code

```python
# Parameters (from Experiment Rules)
RESULT_DIR = <result_dir>
ALLOWED_PES = <allowed_pes>
PE_COST = <pe_cost>
MAX_BLOCK_SIZE = <max_block_size>
INITIAL_BLOCK_SIZE = <initial_block_size>

def compute_initial_recall_step(block_size):
    import math
    return math.ceil(block_size / (len(ALLOWED_PES) * 4))

def equal_composition(block_size):
    per_pe = block_size // len(ALLOWED_PES)
    return [{pe: per_pe for pe in ALLOWED_PES}]

def pe_has_available_count(composition, pe_type):
    # Check if PE type has any count > 0 in composition
    for block_comp in composition:
        if pe_type in block_comp and block_comp[pe_type] > 0:
            return True
    return False

for blocks in range(2, 9):  # 2 to 8 inclusive
    set cgra_config.yaml: blocks = blocks
    set cgra_config.yaml: overload = (0 if blocks == 2 else 1)
    
    dfg_files = find_all_matching(f"./dots/results/{RESULT_DIR}/*_B{blocks}_*_output.dot")
    
    for dfg_file in dfg_files:
        dfg_name = basename(dfg_file)
        current_block_size = INITIAL_BLOCK_SIZE
        recall_step = compute_initial_recall_step(current_block_size)
        fixed_PE = []
        rep_PE = None
        vic_PE = None
        
        while current_block_size <= MAX_BLOCK_SIZE:
            composition = equal_composition(current_block_size)
            
            # Composition variation loop
            success = False
            while True:
                set cgra_config.yaml: block_size = current_block_size
                set cgra_config.yaml: composition = composition
                
                output = run_mapper(dfg_file, dfg_name)
                
                if "Mapping: SUCCESS" in output:
                    print(f"✓ {dfg_name} (block_size={current_block_size}, composition={composition})")
                    success = True
                    break
                elif "Mapping: FAILED" in output:
                    if "Opcode[" in output:
                        # Unsupported opcode - terminal failure for this DFG
                        opcode = extract_opcode(output)
                        print(f"✗ {dfg_name} (unsupported opcode: {opcode})")
                        log_to_skipped(dfg_name, opcode)
                        break
                    else:
                        # PE placement issue - attempt composition variation
                        opcode = extract_opcode(output)
                        
                        # Check if vic_PE has been depleted
                        if rep_PE and vic_PE and not pe_has_available_count(composition, vic_PE):
                            # Move depleted vic_PE to fixed_PE
                            fixed_PE.append(vic_PE)
                            new_vic_PE = find_most_expensive_pe(ALLOWED_PES, PE_COST, exclude={rep_PE} | set(fixed_PE))
                            if new_vic_PE:
                                vic_PE = new_vic_PE
                                transfer_pes(composition, vic_PE, rep_PE, recall_step)
                                continue
                            else:
                                # No suitable victim PE found, halve recall_step
                                recall_step = floor(recall_step / 2)
                                if recall_step < 1:
                                    # recall_step exhausted, move to block_size increase
                                    break
                                else:
                                    # Reset to initial composition with reduced recall_step
                                    composition = equal_composition(current_block_size)
                                    fixed_PE = []
                                    rep_PE = None
                                    vic_PE = None
                                    continue
                        else:
                            # First failure or vic_PE still has available PEs
                            supporting_pes = find_supporting_pes_for_opcode(opcode, pe_config)
                            if supporting_pes:
                                # Select rep_PE as the cheapest PE type among those supporting the opcode
                                rep_PE = min(supporting_pes, key=lambda pe: PE_COST[pe])
                                vic_PE = find_most_expensive_pe(ALLOWED_PES, PE_COST, exclude={rep_PE} | set(fixed_PE))
                                # Verify vic_PE has available PEs
                                if vic_PE and pe_has_available_count(composition, vic_PE):
                                    transfer_pes(composition, vic_PE, rep_PE, recall_step)
                                    continue
                                else:
                                    # No suitable victim PE with available count, halve recall_step
                                    recall_step = floor(recall_step / 2)
                                    if recall_step < 1:
                                        break
                                    else:
                                        # Reset to initial composition with reduced recall_step
                                        composition = equal_composition(current_block_size)
                                        fixed_PE = []
                                        rep_PE = None
                                        vic_PE = None
                                        continue
                            else:
                                # No PE type supports this opcode - unsupported opcode
                                print(f"✗ {dfg_name} (unsupported opcode: {opcode})")
                                log_to_skipped(dfg_name, opcode)
                                break
            
            if success:
                # DFG successfully mapped
                break
            else:
                # Composition variations exhausted or opcode error, try larger block_size
                if current_block_size >= MAX_BLOCK_SIZE:
                    print(f"✗ {dfg_name} (capacity exhausted at block_size=256)")
                    log_to_skipped(dfg_name, "capacity_exhausted")
                    break
                else:
                    current_block_size *= 2
                    recall_step = compute_initial_recall_step(current_block_size)
                    fixed_PE = []
                    rep_PE = None
                    vic_PE = None
                    print(f"  Retry {dfg_name} with block_size={current_block_size}, recall_step={recall_step}")
```

## Command list
- mapper: `python3 -m mapper.mapper -f <map_dfg_path> --log-level info --log-name <map_dfg_name> --log-dir claude/logs --combine-logs`

## Key Differences from Original (Corrected Version)

1. **Per-DFG block_size tracking**: Each DFG has its own `current_block_size` that starts at 8 and doubles on capacity failures.
2. **Retry loop per DFG**: The mapping retry happens within the DFG loop, not at the block count level.
3. **Composition update**: Each time `block_size` changes, update composition to match: if doubling from 8 to 16, composition changes from `[{'PE_int': 8}] * blocks` to `[{'PE_int': 16}] * blocks` (or split across multiple PE types while maintaining total = block_size).
4. **Opcode failures are terminal**: Unsupported opcodes cannot be fixed by increasing block_size; only add to skipped.log.

## Execution Checklist

- [ ] Backup `./configs/cgra_config.yaml` to `./.backup/cgra_config.yaml`
- [ ] Ensure `./dots/results/<result_dir>/` contains DFG files (where result_dir = varBlks_u2b1d2)
- [ ] Ensure `./claude/logs/` directory exists
- [ ] Create or clear `./claude/logs/skipped.log`
- [ ] For each block count (2-8):
  - [ ] Set blocks and overload in config
  - [ ] For each matching DFG:
    - [ ] Initialize: current_block_size = initial_block_size (8), compute recall_step = ceil(block_size / (len(allowed_pes) * 4)), fixed_PE = [], rep_PE = None, vic_PE = None
    - [ ] Set composition to equal distribution of all PE types from allowed_pes
    - [ ] Retry loop (while current_block_size ≤ max_block_size (256)):
      - [ ] Update block_size and composition in config to current_block_size
      - [ ] Run mapper
      - [ ] Check result:
        - SUCCESS → log success with block_size and final composition, move to next DFG
        - FAILED (opcode) → search 'pe_config.yaml' to get supporting pe, retry with supporting pe, else log to skipped.log, move to next DFG
        - FAILED (capacity/PE placement) → attempt composition variation loop:
          - [ ] While failing and composition variations exist:
            - [ ] Check if vic_PE count in composition has dropped to 0
            - [ ] If yes: move vic_PE to fixed_PE, find new vic_PE by cost (excluding rep_PE and fixed_PE), if found transfer recall_step PEs else halve recall_step
            - [ ] If no: find all PE types supporting the failing opcode from pe_config, select rep_PE as the cheapest, find vic_PE by cost (excluding rep_PE and fixed_PE), **verify vic_PE has available PEs**, transfer recall_step PEs, re-run
            - [ ] If no suitable vic_PE or recall_step reaches 1: break composition loop
          - [ ] If composition loop exhausted: double current_block_size, reset composition to equal distribution, recompute recall_step, retry if ≤ max_block_size, else log as exhausted
- [ ] Report final results with block_size and composition requirements per successful DFG
- [ ] Verify truly skipped DFGs (opcode errors + capacity exhausted at max_block_size)
