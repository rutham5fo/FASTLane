# Auto Experimenter
You are an agent that will call scripts following the pattern described below.
First understand General and Experiment rules. Then start Experiment.

## General Rules
- Minimize token usage by keeping outputs short. All internally generated lists unless explicitly stated must not be printed on standard output to avoid token consumption.
- Due to un-foreseen circumstance, if an edit is required in any other file, than those described in Experiment rules, prompt user for approval.
- First run must always be done step-by-step, attaining the approval from user regarding the correctness of your understanding of the task.
- All lists are zero-indexed.
- Do not bother with commands not used in the Experiment.
- You are permited to execute any non-sudo shell command to progress the experiment.
- Use './.tmp' directory for temp files. Ask user before deleting temp generated files.
- When all steps have been approved, run autonomously till completion of experiment.

## Experiment Rules
- Everything enclosed within '/beg_pylike' and '/end_pylike', is to be interpreted as a python-like script. Wherein, anything enclosed in <> is to be substituted with the value of the defined variable name.
- You are only free to edit the following files without user approval (explicit approval required only on first run):
    - './configs/cgra_config.yaml'
- All editable files must be backed up into './.backup' before beginning experiment. The user can replace the edited files with the backups if required.
- 'blocks' in 'cgra_config.yaml' must always be fixed to 2.
- the number of elements in a block (determined by composition) must always equal the 'block_size'.
- 'block_size' in 'cgra_config.yaml' is initialized to 8 at the start of each DFG mapping iteration.
- Refer to './configs/pe_config.yaml' when editing 'cgra_config.yaml' for complete context.
- Search cli output for 'Mapping: [SUCCESS/FAILED]' to determine mapping status. In-case of failure:
    - If 'Opcode[some opcode]' is not supported: Consult 'pe_config.yaml' to find a PE type that supports required opcode and edit cgra composition with appropriate PE type (Note: this is a homogenuous CGRA, hence all blocks must be of same type). Should you not find an appropriate PE, append DFG name to 'skipped.log' in ./claude/logs (create file if non-existent).
    - Else: double the current block-size, make appropriate changes in 'cgra_config.yaml' and re-run DFG iteration.
- Experiment is complete when the for-loop terminates after iterating over all DFGs.

## Experiment
/beg_pylike
cmd = Command list
for (dfg_name in './dots/results/blks2_noUnroll'):
    run cmd: mapper with <map_dfg_path=blks2_noUnroll/dfg_name>, <map_dfg_name=dfg_name>
/end_pylike

## Command list
- dfg_gen: python3 -m dots_manager.manager -f <src_dfg_name>.dot --force --cgra-radix 2 --cgra-blocks 2 -u <ufactor> -b <bfactor> -d <dfactor>
- mapper: python3 -m mapper.mapper -f <map_dfg_path> --log-level info --log-name <map_dfg_name> --log-dir claude/logs --combine-logs
