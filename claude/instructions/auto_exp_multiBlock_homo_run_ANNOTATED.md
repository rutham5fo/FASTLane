# Auto Experimenter - ANNOTATED (Corrected Implementation)

## Overview
This document annotates the original `auto_exp_multi_block_overload_run.md` with detailed clarifications to ensure correct execution and replicability.

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
- result_dir = varBlks_u2b1d2

### Block Size Management (CRITICAL)
- The `block_size` in `cgra_config.yaml` is initialized to 8 at the start of each DFG mapping iteration.
- **IMPORTANT:** `block_size` is a **per-DFG variable**, not a global constant for all DFGs in a block count.
- `block_size` can grow from 8 up to a maximum of 256 (sequence: 8 → 16 → 32 → 64 → 128 → 256).
- When a mapping fails, check the failure reason:
  - If `Opcode[some_opcode] not supported`: This is a PE type limitation. Consult `pe_config.yaml` and potentially change PE composition. If no suitable PE exists, add DFG to `skipped.log`.
  - If capacity failure (no available PE): **Double the block_size for THAT DFG only** and retry the mapping with the same DFG.
  - Retry loop continues until either SUCCESS, an opcode error occurs, or block_size reaches 256 (capacity exhausted).

### Composition Constraint
- The number of elements in a block (determined by composition) must always equal `block_size`.
- All blocks in the CGRA must have the same composition (homogeneous CGRA).
- Example: if `block_size = 16`, composition might be `[{'PE_int': 16}]` or `[{'PE_int': 8}, {'PE_int': 8}]`, etc.

### Block Count Iterations
- Outer loop: iterate `blocks` from 2 to `max_blocks` (8 in this case).
- For each `blocks` value, set:
  - `blocks` in cgra_config.yaml = current block count
  - `overload` = 0 if blocks == 2, else 1
  - `block_size` = 8 (reset for this block count iteration)
- Then process all DFGs matching pattern `*_B<blocks>_*` for that block count.

### DFG Processing Loop (CRITICAL - PER-DFG BLOCK_SIZE DOUBLING)
1. For each block count iteration (e.g., blocks=2, 3, 4...):
   2. Find all DFG files: `./dots/results/<result_dir>/*_B<blocks>_*_output.dot`
   3. For each DFG file found:
      - Set local `current_block_size = 8` (reset for each new DFG)
      - **Retry Loop (for THIS DFG only):**
        - Update `block_size` in cgra_config.yaml to `current_block_size`
        - Run mapper on the DFG
        - Check output for `Mapping: SUCCESS/FAILED`
        - If SUCCESS: record success, move to next DFG
        - If FAILED:
          - If output contains `Opcode[...]`: unsupported opcode error → add DFG to skipped.log, move to next DFG
          - Else: capacity error → `current_block_size *= 2`, go back to retry loop
      - End retry loop (either success or opcode error)

## Experiment Pseudo-code

```python
MAX_BLOCK_SIZE = 256

for blocks in range(2, 9):  # 2 to 8 inclusive
    set cgra_config.yaml: blocks = blocks
    set cgra_config.yaml: overload = (0 if blocks == 2 else 1)
    
    dfg_files = find_all_matching("./dots/results/<result_dir>/*_B{blocks}_*_output.dot")
    
    for dfg_file in dfg_files:
        dfg_name = basename(dfg_file)
        current_block_size = 8
        
        while current_block_size <= MAX_BLOCK_SIZE:
            # Update config for this DFG attempt
            set cgra_config.yaml: block_size = current_block_size
            set cgra_config.yaml: composition = [{'PE_int': current_block_size}] * blocks
            
            # Run mapper
            output = run_mapper(dfg_file, dfg_name)
            
            if "Mapping: SUCCESS" in output:
                print(f"✓ {dfg_name} (block_size={current_block_size})")
                break
            elif "Mapping: FAILED" in output:
                if "Opcode[" in output:
                    # Unsupported opcode - consult pe_config.yaml to find appropriate PE
                    opcode = extract_opcode(output)
                    pe_type = get_supporting_pe(search for opcode in pe_config.yaml)
                    if (no supporting pe found):
                      print(f"✗ {dfg_name} (opcode: {opcode})")
                      log_to_skipped(dfg_name, opcode)
                      break
                    else:
                      set cgra_config.yaml: composition = [{pe_type: current_block_size}] * blocks
                      print(f"  Retry {dfg_name} with PE_type={pe_type}")
                      continue
                else:
                    # Capacity issue - retry with doubled block_size
                    current_block_size *= 2
                    if current_block_size <= MAX_BLOCK_SIZE:
                        print(f"  Retry {dfg_name} with block_size={current_block_size}")
                        continue
                    else:
                        # Exhausted max block_size
                        print(f"✗ {dfg_name} (capacity exhausted at block_size=256)")
                        log_to_skipped(dfg_name, "capacity_exhausted")
                        break
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
- [ ] Ensure `./dots/results/<result_dir>/` contains DFG files
- [ ] Ensure `./claude/logs/` directory exists
- [ ] Create or clear `./claude/logs/skipped.log`
- [ ] For each block count (2-8):
  - [ ] Set blocks and overload in config
  - [ ] For each matching DFG:
    - [ ] Initialize current_block_size = 8
    - [ ] Retry loop (while current_block_size ≤ 256):
      - [ ] Update block_size in config to current_block_size
      - [ ] Run mapper
      - [ ] Check result:
        - SUCCESS → log success with block_size, move to next DFG
        - FAILED (opcode) → search 'pe_config.yaml' to get supporting pe, retry with supporting pe, else log to skipped.log, move to next DFG
        - FAILED (capacity) → double current_block_size, retry if ≤ 256, else log as exhausted
- [ ] Report final results with block_size requirements per successful DFG
- [ ] Verify truly skipped DFGs (opcode errors + capacity exhausted at 256)
