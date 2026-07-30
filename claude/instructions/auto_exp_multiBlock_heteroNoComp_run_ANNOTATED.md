# Auto Experimenter - ANNOTATED (Corrected Implementation)

## Overview
This document annotates the original `auto_exp_multiBlock_homo_run_ANNOTATED.md` to run with heterogenous CGRA configs.

## Instructions Checklist
- [ ] DFG Processing loop and Experiment Pseudo-Code must be in sync (always).

## General Rules
- Minimize token usage by keeping outputs short. All internally generated lists unless explicitly stated must not be printed on standard output to avoid token consumption.
- Due to un-foreseen circumstance, if an edit is required in any other file than those described in Experiment rules, prompt user for approval.
- First run must always be done step-by-step, attaining the approval from user regarding the correctness of your understanding of the task.
- All lists are zero-indexed.
- Do not bother with commands not used in the Experiment.
- You are permitted to execute any non-sudo shell command to progress the experiment.
- Use './.tmp' directory for temp and new files whose path has not be explicitly defined. Ask user before deleting temp generated files.
- Log experiment results. Do not dump everything, log landmark events, tracking events, and final results.
- When all steps have been approved, run autonomously till completion of experiment.
- Upon successfull completion, copy relevant files (including experiment result file) into './claude/runs/<this_file_name>/' (create folder if necessary). Place all logs inside './claude/runs/<this_file_name>/logs/' (create folder if necessary). Add a README.md as guide for experiment reproducibility. **NOTE**: Following the guide should exactly reproduce the experiment result file.

## Experiment Rules

### Logging
- log composition details for each DFG (**not** every iteration, **only** the final iteration's composition irrespective of success or failure) in the same path as mapper log.

### Parameters
- result_dir = varBlks_u2b1d2
- allowed_pes = {'PE_int_alu', 'PE_int_muldiv', 'PE_float_alu', 'PE_float_muldiv'}
- pe_cost = {1, 3, 2, 4} # (corresponding to allowed_pes: PE_int_alu=1, PE_int_muldiv=3, PE_float_alu=2, PE_float_muldiv=4)
- max_block_size = 256

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
- Example: if `block_size = 16`, composition might be `[{'PE_int': 16}]`, `[{'PE_int': 8}, {'PE_int': 8}]`, `[{'PE_float': 8}, {'PE_int': 8}]`, or `[{'PE_float': 16}]` etc.
- Block composition can only be positive integers or 0.
- The CGRA composition must consist of equal amounts of all PE types from `allowed_pes`.
- Example: if `block_size = 16`, then composition = `[{'PE_int_alu': 4, 'PE_int_muldiv': 4, 'PE_float_alu': 4, 'PE_float_muldiv': 4}]`, etc.

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
allowed_pes = ['PE_int_alu', 'PE_int_muldiv', 'PE_float_alu', 'PE_float_muldiv']

for blocks in range(2, 9):  # 2 to 8 inclusive
    set cgra_config.yaml: blocks = blocks
    set cgra_config.yaml: overload = (0 if blocks == 2 else 1)
    
    dfg_files = find_all_matching("./dots/results/<result_dir>/*_B{blocks}_*_output.dot")
    
    for dfg_file in dfg_files:
        dfg_name = basename(dfg_file)
        current_block_size = 8
        dfg_completed = False
        final_composition = None
        final_result = None
        
        while current_block_size <= MAX_BLOCK_SIZE and not dfg_completed:
            # Composition: equal distribution of all 4 PE types
            pe_per_type = current_block_size // 4
            composition = [{'PE_int_alu': pe_per_type, 'PE_int_muldiv': pe_per_type,
                            'PE_float_alu': pe_per_type, 'PE_float_muldiv': pe_per_type}] * blocks
            
            # Update config for this DFG attempt
            set cgra_config.yaml: block_size = current_block_size
            set cgra_config.yaml: composition = composition
            final_composition = composition
            
            # Run mapper
            output = run_mapper(dfg_file, dfg_name)
            
            if "Mapping: SUCCESS" in output:
                final_result = "SUCCESS"
                print(f"✓ {dfg_name} (block_size={current_block_size})")
                dfg_completed = True
                
            elif "Mapping: FAILED" in output:
                if "Opcode[" in output:
                    # Unsupported opcode - check pe_config.yaml for supporting PE
                    opcode = extract_opcode(output)
                    supporting_pe = find_supporting_pe(opcode)  # Search pe_config.yaml
                    
                    if supporting_pe is None:
                        # No supporting PE found - skip DFG
                        final_result = f"FAILED (unsupported opcode: {opcode})"
                        print(f"✗ {dfg_name} (opcode: {opcode})")
                        log_to_skipped(dfg_name, f"unsupported_opcode_{opcode}")
                        dfg_completed = True
                    else:
                        # Retry with supporting PE type
                        retry_composition = [{supporting_pe: current_block_size}] * blocks
                        set cgra_config.yaml: composition = retry_composition
                        final_composition = retry_composition
                        
                        output = run_mapper(dfg_file, dfg_name)
                        
                        if "Mapping: SUCCESS" in output:
                            final_result = "SUCCESS"
                            print(f"✓ {dfg_name} (block_size={current_block_size}, PE={supporting_pe})")
                            dfg_completed = True
                        else:
                            # Retry with supporting PE failed
                            if "Opcode[" in output:
                                # Still opcode error - skip DFG
                                final_result = f"FAILED (opcode {opcode} unsupported even with {supporting_pe})"
                                print(f"✗ {dfg_name} (opcode: {opcode} unsupported)")
                                log_to_skipped(dfg_name, f"unsupported_opcode_{opcode}")
                                dfg_completed = True
                            else:
                                # Capacity error on retry - try larger block_size
                                if current_block_size * 2 <= MAX_BLOCK_SIZE:
                                    current_block_size *= 2
                                    print(f"  Retry {dfg_name} with block_size={current_block_size}")
                                    continue
                                else:
                                    final_result = "FAILED (capacity exhausted)"
                                    print(f"✗ {dfg_name} (capacity exhausted at block_size=256)")
                                    log_to_skipped(dfg_name, "capacity_exhausted")
                                    dfg_completed = True
                else:
                    # Capacity issue (no PE available) - retry with doubled block_size
                    if current_block_size * 2 <= MAX_BLOCK_SIZE:
                        current_block_size *= 2
                        print(f"  Retry {dfg_name} with block_size={current_block_size}")
                        continue
                    else:
                        # Exhausted max block_size
                        final_result = "FAILED (capacity exhausted)"
                        print(f"✗ {dfg_name} (capacity exhausted at block_size=256)")
                        log_to_skipped(dfg_name, "capacity_exhausted")
                        dfg_completed = True
        
        # Log composition details for this DFG after processing completes
        if final_composition is not None:
            log_composition_details(dfg_name, current_block_size, final_composition,
                                   mapping_result=final_result)
```

## Command list
- mapper: `python3 -m mapper.mapper -f <map_dfg_path> --log-level info --log-name <map_dfg_name> --log-dir claude/logs --combine-logs`

## Key Differences from Original (Corrected Version)

1. **Per-DFG block_size tracking**: Each DFG has its own `current_block_size` that starts at 8 and doubles on capacity failures.
2. **Retry loop per DFG**: The mapping retry happens within the DFG loop, not at the block count level.
3. **Composition update**: Each time `block_size` changes, update composition to match: if doubling from `block_size` from 8 to 16, composition changes from `[{'PE_int_alu': 2, 'PE_int_muldiv': 2, 'PE_float_alu': 2, 'PE_float_muldiv': 2}]` to `[{'PE_int_alu': 4, 'PE_int_muldiv': 4, 'PE_float_alu': 4, 'PE_float_muldiv': 4}]`, accordingly.
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
