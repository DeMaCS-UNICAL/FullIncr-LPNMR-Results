#!/usr/bin/env python3

import subprocess
import sys
import time
import json
import os
import re
import tempfile
import hashlib
import traceback
import clingo

CONFIG_FILE = sys.argv[1] if len(sys.argv) > 1 else "config.json"
CACHE_FILE = "benchmarks_run/cache.json"
SCRIPT_START_TIME = time.strftime("%Y-%m-%d %H:%M:%S")
SCRIPT_START_TIME_FORMATTED = time.strftime("%Y-%m-%d-%H-%M-%S")

try:
    with open(CONFIG_FILE, "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
    sys.exit(1)

SYSTEMS = CONFIG.get("systems", {})

try:
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cache = {}

def get_enabled_systems():
    return {k: v for k, v in SYSTEMS.items() if v.get("enabled", False)}

def save_cache():
    os.makedirs("benchmarks_run", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def get_hash_from_files(file_list):
    s = ""
    for file in file_list:
        with open(file, "r") as f:
            s += f.read()
    return hashlib.sha256(s.encode()).hexdigest()

def writelogs(logs, name, filename):
    tm = time.strftime("%Y-%m-%d %H:%M:%S")
    valid_logs = [l.strip() for l in logs if l.strip()]
    if valid_logs:
        log_dir = f"benchmarks_run/{SCRIPT_START_TIME_FORMATTED}"
        os.makedirs(log_dir, exist_ok=True)
        log_file = f"{log_dir}/logs.txt"
        
        write_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
        
        with open(log_file, "a") as f2:
            if write_header:
                f2.write("timestamp;solver;name;instance_number;load;ground;solve;total\n")
            f2.write("\n".join([f"{tm};{name};{filename};{l}" for l in valid_logs]) + "\n")

def save_system_output(system_name, stdout_text, stderr_text, filename=None, instance_idx=None):
    log_dir = f"benchmarks_run/{SCRIPT_START_TIME_FORMATTED}"
    os.makedirs(log_dir, exist_ok=True)

    header = ""
    if filename:
        header = f"{'='*40}\nFile: {filename}"
        if instance_idx is not None:
            header += f" (Instance: {instance_idx})"
        header += f"\n{'='*40}\n"

    with open(f"{log_dir}/{system_name}_stdout.txt", "a") as f:
        if header: f.write(header)
        if stdout_text: f.write(str(stdout_text))
        if not stdout_text or not stdout_text.endswith("\n"): f.write("\n")

    with open(f"{log_dir}/{system_name}_stderr.txt", "a") as f:
        if header: f.write(header)
        if stderr_text: f.write(str(stderr_text))
        if not stderr_text or not stderr_text.endswith("\n"): f.write("\n")

def create_empty_dictionary():
    return {
        name: {"total": 0.0, "load": 0.0, "ground": 0.0, "solve": 0.0}
        for name in get_enabled_systems()
    }

def canonicalize_atom(atom):
    res = ""
    in_quote = False
    for char in atom:
        if char == '"':
            in_quote = not in_quote
            res += char
        elif char.isspace():
            if in_quote:
                res += char
        else:
            res += char
    return res

def extract_stats(stderr, key, suffix="s"):
    if key in stderr:
        try:
            return float(stderr.split(key)[1].strip().split(suffix)[0].strip())
        except (IndexError, ValueError):
            return 0.0
    return 0.0

def calc_time(lines):
    valid_lines = [l.strip() for l in lines if l.strip() and l.count(";") >= 4]

    times, loads, grounds, solves = [], [], [], []
    for l in valid_lines:
        parts = l.split(";")
        if not parts[4].replace("_", "").isalpha(): times.append(float(parts[4]))
        if not parts[1].replace("_", "").isalpha(): loads.append(float(parts[1]))
        if not parts[2].replace("_", "").isalpha(): grounds.append(float(parts[2]))
        if not parts[3].replace("_", "").isalpha(): solves.append(float(parts[3]))

    return sum(times), sum(loads), sum(grounds), sum(solves)

def parse_model(stdout_text):
    matches = re.findall(r'\{([^}]*)\}', stdout_text)
    if matches:
        last_match = matches[-1]
        atoms, current_atom, depth = [], "", 0
        for char in last_match:
            if char == '(': depth += 1
            elif char == ')': depth -= 1
            
            if char == ',' and depth == 0:
                if current_atom.strip():
                    atoms.append(canonicalize_atom(current_atom.strip()))
                current_atom = ""
            else:
                current_atom += char
        if current_atom.strip():
            atoms.append(canonicalize_atom(current_atom.strip()))
        return atoms

    lines = [l.strip() for l in stdout_text.splitlines() if l.strip()]
    if not lines:
        return None

    last_answer_idx = next((i for i, line in reversed(list(enumerate(lines))) if line.startswith("Answer:")), -1)
    if last_answer_idx != -1 and last_answer_idx + 1 < len(lines):
        model_line = lines[last_answer_idx + 1].strip()
        return [canonicalize_atom(a.strip()) for a in model_line.split() if a.strip()]

    keywords = [
        "Optimization:", "OPTIMUM FOUND", "Answer:", "SATISFIABLE", "UNSATISFIABLE", 
        "Calls :", "Time :", "CPU Time", "Models :", "Solving:", "Reading:", 
        "Preserving:", "Limit", "Threads", "Winner"
    ]
    
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if not any(line.startswith(kw) for kw in keywords):
            parts = line.split()
            if parts and any(not p.replace(".", "").isdigit() for p in parts):
                return [canonicalize_atom(a.strip()) for a in parts if a.strip()]
        
    return None

def parse_all_models(stdout_text):
    chunks = re.split(r'<END>', stdout_text)
    if chunks and not chunks[-1].strip():
        chunks = chunks[:-1]
    return [parse_model(chunk) for chunk in chunks]

def find_instances_encoding(filename):
    instances, encoding, background = [], "", ""
    is_first = True
    
    with open(filename, "r") as f:
        for line in f:
            line_strip = line.strip()
            if not line_strip.startswith("<load"):
                continue
            
            path = line_strip.split('path="')[1].split('"')[0]
            
            if 'background="true"' in line_strip:
                background = path
            elif is_first:
                is_first = False
                encoding = path
            else:
                instances.append(path)
                
    return encoding, instances, background

def strip_show_directives(filepath):
    if not filepath:
        return None
        
    with open(filepath, 'r') as f:
        lines = f.readlines()

    filtered = []
    for l in lines:
        stripped = l.strip()
        if stripped.startswith('#show') or (stripped.startswith('%') and '#show' in stripped):
            continue
        filtered.append(l)
        
    with tempfile.NamedTemporaryFile(mode='w', suffix='.asp', delete=False) as f:
        f.writelines(filtered)
        return f.name

def verify_model(model_atoms, encoding, instances_to_load, background):
    filtered_atoms = [a for a in model_atoms if not a.startswith("edge(") and not a.startswith("vertex(")]
    
    file_list = [encoding]
    if background:
        file_list.append(background)
    file_list.extend(instances_to_load)
    
    file_hash_base = get_hash_from_files(file_list)
    model_str = "".join(sorted(filtered_atoms))
    hasher = hashlib.sha256()
    hasher.update(file_hash_base.encode('utf-8'))
    hasher.update(model_str.encode('utf-8'))
    cache_key = hasher.hexdigest()
    
    if cache_key in cache:
        is_valid = cache[cache_key]
        if not is_valid:
            print(f"Verification failed (cached)! Evaluated {len(filtered_atoms)} conditions.")
        return is_valid
        
    is_valid = False
    try:
        ctl = clingo.Control(["1"])
        
        ctl.load(encoding)
        if background:
            ctl.load(background)
        for inst in instances_to_load:
            ctl.load(inst)
            
        constraint_str = "".join(f":- not {a}.\n" for a in filtered_atoms)
        if constraint_str:
            ctl.add("base", [], constraint_str)
            
        ctl.ground([("base", [])])
        
        with ctl.solve(yield_=True, async_=False) as handle:
            for m in handle:
                is_valid = True
                break
                
        cache[cache_key] = is_valid
        save_cache()
        if not is_valid:
            print(f"Verification failed! Evaluated {len(filtered_atoms)} conditions against files: {instances_to_load}")
            
    except Exception as e:
        is_valid = False
        print("Exception during verification:", e)
        
    return is_valid

def verify_unsat(encoding, instances_to_load, background, timeout=120):
    import clingo
    
    file_list = [encoding]
    if background:
        file_list.append(background)
    file_list.extend(instances_to_load)
    
    file_hash_base = get_hash_from_files(file_list)
    hasher = hashlib.sha256()
    hasher.update(file_hash_base.encode('utf-8'))
    hasher.update(b"UNSAT_CHECK")
    cache_key = hasher.hexdigest()
    
    if cache_key in cache:
        is_valid = cache[cache_key]
        if not is_valid:
            print(f"UNSAT Verification failed (cached)!")
        return is_valid
        
    is_valid = False
    try:
        ctl = clingo.Control(["1"])
        
        ctl.load(encoding)
        if background:
            ctl.load(background)
        for inst in instances_to_load:
            ctl.load(inst)
            
        ctl.ground([("base", [])])
        
        with ctl.solve(async_=True) as handle:
            finished = handle.wait(timeout)
            if not finished:
                handle.cancel()
                print("UNSAT verification timed out!")
                is_valid = False 
            else:
                res = handle.get()
                if res.unsatisfiable:
                    is_valid = True
                else:
                    is_valid = False
                    
        cache[cache_key] = is_valid
        save_cache()
        if not is_valid:
            print(f"UNSAT Verification failed or timed out!")
            
    except Exception as e:
        print("Exception during UNSAT verification:", e)
        is_valid = False
        
    return is_valid

def _run_standard_solver(solver_name, filename, timeout, base_command, parse_stats_func):
    encoding, instances, background = find_instances_encoding(filename)
    
    if solver_name == "dlv2":
        with open(encoding, "r") as f:
            lines = f.readlines()
        if lines and lines[0].startswith("%@"):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.asp', delete=False) as temp_f:
                temp_f.write("% " + lines[0][1:] + "".join(lines[1:]))
                encoding = temp_f.name

    no_show_encoding = strip_show_directives(encoding)
    no_show_bg = strip_show_directives(background)

    sum_total = sum_load = sum_ground = sum_solve = 0.0

    try:
        for index, instance in enumerate(instances):
            command = base_command + [no_show_encoding, instance]
            if no_show_bg:
                command.append(no_show_bg)

            try:
                res = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=timeout)
                save_system_output(solver_name, res.stdout, res.stderr, filename, index)
                atoms = parse_model(res.stdout)
                
                if atoms is not None:
                    if not verify_model(atoms, no_show_encoding, [instance], no_show_bg):
                        writelogs([f"{index};ERROR_VERIFY;0;0;0;0"], solver_name, filename)
                        sum_total += timeout
                        continue
                else:
                    if not verify_unsat(no_show_encoding, [instance], no_show_bg, timeout=timeout+30):
                        writelogs([f"{index};ERROR_UNSAT_VERIFY;0;0;0;0"], solver_name, filename)
                        sum_total += timeout
                        continue

                t_tot, t_load, t_ground, t_solve = parse_stats_func(res)
                sum_total += t_tot
                sum_load += t_load
                sum_ground += t_ground
                sum_solve += t_solve

                writelogs([f"{index};{t_load};{t_ground};{t_solve};{t_tot};0"], solver_name, filename)

            except subprocess.TimeoutExpired as e:
                save_system_output(solver_name, e.stdout if hasattr(e, 'stdout') and e.stdout else "", e.stderr if hasattr(e, 'stderr') and e.stderr else "TIMEOUT", filename, index)
                writelogs([f"{index};0;0;0;{timeout};0"], solver_name, filename)
                sum_total += timeout
            except Exception as e:
                save_system_output(solver_name, "", f"EXCEPTION: {e}\n{traceback.format_exc()}", filename, index)
                print(f"Exception in {solver_name} on instance {index}: {e}")
                traceback.print_exc()
                writelogs([f"{index};ERROR;0;0;0;0"], solver_name, filename)
                sum_total += timeout
    finally:
        if no_show_encoding: os.remove(no_show_encoding)
        if no_show_bg: os.remove(no_show_bg)
        if solver_name == "dlv2" and encoding != find_instances_encoding(filename)[0]:
            os.remove(encoding)

    return sum_total, sum_load, sum_ground, sum_solve


def clingo_check(filename, timeout, base_command):
    def parse_stats(res):
        total_val = extract_stats(res.stdout, "Time         :") or extract_stats(res.stderr, "Time         :") or extract_stats(res.stdout, "CPU Time", suffix=" ")
        solve_val = extract_stats(res.stdout, "Solving:") or extract_stats(res.stderr, "Solving:")
        ground_val = max(0.0, total_val - solve_val)
        return total_val, 0.0, ground_val, solve_val
        
    return _run_standard_solver("clingo", filename, timeout, base_command, parse_stats)

def dlv2_check(filename, timeout, base_command):
    def parse_stats(res):
        load_val = extract_stats(res.stderr, "Non-ground program parsing time:")
        ground_val = extract_stats(res.stderr, "Grounding time:")
        solve_val = extract_stats(res.stderr, "Solving time:")
        return load_val + ground_val + solve_val, load_val, ground_val, solve_val
        
    return _run_standard_solver("dlv2", filename, timeout, base_command, parse_stats)

def clingo_api_check(name, filename, timeout, base_command):
    encoding, instances, background = find_instances_encoding(filename)
    
    no_show_encoding = strip_show_directives(encoding)
    no_show_bg = strip_show_directives(background)
    
    num_instances = len(instances) if instances else 1
    batch_timeout = timeout * num_instances
    command = base_command + [filename, str(timeout)]

    sum_total = sum_load = sum_ground = sum_solve = 0.0

    try:
        res = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=batch_timeout)
        save_system_output(name, res.stdout, res.stderr, filename)
        all_models = parse_all_models(res.stdout)
        
        if all_models:
            for mi, model_atoms in enumerate(all_models):
                inst_to_check = [instances[mi]] if mi < len(instances) else instances[-1:]
                if model_atoms is not None:
                    if not verify_model(model_atoms, no_show_encoding, inst_to_check, no_show_bg):
                        writelogs([f"{mi};ERROR_VERIFY;0;0;0;0"], name, filename)
                        return 9999999999, 9999999999, 9999999999, 9999999999
                else:
                    if not verify_unsat(no_show_encoding, inst_to_check, no_show_bg, timeout=timeout+30):
                        writelogs([f"{mi};ERROR_UNSAT_VERIFY;0;0;0;0"], name, filename)
                        sum_total += timeout
        
        lines = res.stderr.strip().split("\n")
        writelogs(lines, name, filename)
        sum_total, sum_load, sum_ground, sum_solve = calc_time(lines)

    except subprocess.TimeoutExpired as e:
        save_system_output(name, e.stdout if hasattr(e, 'stdout') and e.stdout else "", e.stderr if hasattr(e, 'stderr') and e.stderr else "TIMEOUT", filename)
        if e.stderr:
            lines = e.stderr.strip().split("\n")
            if lines: writelogs(lines, name, filename)
        writelogs(["0;9999999999;9999999999;9999999999;9999999999;0"], name, filename)
        sum_total = 9999999999
    finally:
        if no_show_encoding: os.remove(no_show_encoding)
        if no_show_bg: os.remove(no_show_bg)

    return sum_total, sum_load, sum_ground, sum_solve


def calculate_total_times(filename, per_instance_timeout):
    results = create_empty_dictionary()
    active_systems = get_enabled_systems()
    encoding, instances, background = find_instances_encoding(filename)
    num_instances = len(instances) if instances else 1

    for name, config in active_systems.items():
        sys_type = config["type"]
        command = config["command"]

        if sys_type in ["incremental-clingo", "incremental-dlv2"]:
            batch_timeout = per_instance_timeout * num_instances
            with open(filename, "r") as f:
                xml_content = f.read()

            try:
                res = subprocess.run(command, capture_output=True, text=True, errors="replace", input=xml_content, timeout=batch_timeout)
                save_system_output(name, res.stdout, res.stderr, filename)
                all_models = parse_all_models(res.stdout)
                
                if all_models:
                    verify_failed = False
                    for mi, model_atoms in enumerate(all_models):
                        if model_atoms is None and sys_type == "incremental-dlv2":
                            continue
                            
                        inst_to_check = [instances[mi]] if mi < len(instances) else instances[-1:]
                        
                        if model_atoms is not None:
                            if not verify_model(model_atoms, encoding, inst_to_check, background):
                                writelogs([f"{mi};ERROR_VERIFY;0;0;0;0"], name, filename)
                                verify_failed = True
                                break
                        else:
                            if not verify_unsat(encoding, inst_to_check, background, timeout=per_instance_timeout):
                                writelogs([f"{mi};ERROR_UNSAT_VERIFY;0;0;0;0"], name, filename)
                                verify_failed = True
                                break
                                
                    if verify_failed:
                        results[name]["total"] = 9999999999
                        continue

                lines = res.stderr.strip().split("\n")
                if len(lines) > 1:
                    writelogs(lines[1:], name, filename)
                    t_tot, t_load, t_ground, t_solve = calc_time(lines)
                    results[name].update({"total": t_tot, "load": t_load, "ground": t_ground, "solve": t_solve})

            except subprocess.TimeoutExpired as e:
                save_system_output(name, e.stdout if hasattr(e, 'stdout') and e.stdout else "", e.stderr if hasattr(e, 'stderr') and e.stderr else "TIMEOUT", filename)
                if e.stderr:
                    lines = e.stderr.strip().split("\n")
                    if len(lines) > 1: writelogs(lines[1:], name, filename)
                writelogs(["0;9999999999;9999999999;9999999999;9999999999;0"], name, filename)
                results[name]["total"] = 9999999999

        elif sys_type == "clingo":
            t, l, g, s = clingo_check(filename, per_instance_timeout, command)
            results[name].update({"total": t, "load": l, "ground": g, "solve": s})
            
        elif sys_type == "dlv2":
            t, l, g, s = dlv2_check(filename, per_instance_timeout, command)
            results[name].update({"total": t, "load": l, "ground": g, "solve": s})
            
        elif sys_type == "clingo_api":
            t, l, g, s = clingo_api_check(name, filename, per_instance_timeout, command)
            results[name].update({"total": t, "load": l, "ground": g, "solve": s})

    return results

if __name__ == "__main__":
    _raw_problems = CONFIG.get("problems", [])
    files = []
    
    for item in _raw_problems:
        if isinstance(item, str):
            files.append(item)
        elif isinstance(item, dict) and item.get("enabled", True) and "path" in item:
            files.append(item["path"])

    NUMBER = CONFIG.get("number_of_runs", 1)
    TIMEOUT = CONFIG.get("timeout", 1500)

    if not files:
        print("No files configured in 'problems' list.")
        sys.exit(0)

    for file in files:
        encoding, instances, background = find_instances_encoding(file)
        res_sum = create_empty_dictionary()
        table_spaces = 15

        for i in range(NUMBER):
            results = calculate_total_times(file, TIMEOUT)
            for key, value in results.items():
                res_sum[key]["total"] += value["total"]
                res_sum[key]["load"] += value["load"]
                res_sum[key]["ground"] += value["ground"]
                res_sum[key]["solve"] += value["solve"]

        print(f"{'/'.join(file.strip().split('/'))}")
        for key, value in res_sum.items():
            t_val = value["total"]
            t_str = f"{t_val / NUMBER:.3f}s" if t_val < 999999999 else "tmout"
            l_str = f"{value['load'] / NUMBER:4.3f}s" if value["load"] < 999999999 else "tmout"
            g_str = f"{value['ground'] / NUMBER:4.3f}s" if value["ground"] < 999999999 else "tmout"
            s_str = f"{value['solve'] / NUMBER:4.3f}s" if value["solve"] < 999999999 else "tmout"

            padding = " " * (table_spaces - len(key))
            print(f"    {key}:{padding}{t_str}  --  load: {l_str}  --  ground: {g_str}  --  solve: {s_str}")
            
        sys.stdout.flush()