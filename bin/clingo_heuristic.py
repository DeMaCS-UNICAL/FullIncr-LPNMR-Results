#!/usr/bin/python3

import argparse
import sys
import time

import clingo


def find_instances_encoding(filename):
    instances = []
    encoding = ""
    is_first = True
    background = ""
    with open(filename, "r") as f:
        lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if is_first and 'path="' in stripped:
                is_first = False
                encoding = stripped.split('path="')[1].split('"')[0]
            elif 'background="true"' in stripped:
                background = stripped.split('path="')[1].split('"')[0]
            elif "load" in stripped and 'path="' in stripped:
                instance = stripped.split('path="')[1].split('"')[0]
                instances.append(instance)
    return encoding, instances, background


def run_benchmark(template_file, timeout_per_instance=1500, use_heuristic=True):
    encoding, instances, background = find_instances_encoding(template_file)

    if not instances:
        print("No instances found in template.", file=sys.stderr)
        return

    previous_model_symbols = set()

    sum_total = 0.0
    sum_load = 0.0
    sum_ground = 0.0
    sum_solve = 0.0

    for index, instance in enumerate(instances):
        instance_start = time.time()

        load_start = time.time()
        
        ctl_args = ["1"]
        if use_heuristic:
            ctl_args.append("--heuristic=Domain")

        ctl = clingo.Control(
            ctl_args,
            logger=lambda code, msg: None,
        )

        ctl.load(encoding)
        if background:
            ctl.load(background)

        with open(instance, "r") as f:
            instance_content = f.read()
        ctl.add("instance", [], instance_content)
        load_time = time.time() - load_start

        ground_start = time.time()
        ctl.ground([("base", []), ("instance", [])])
        
        if use_heuristic and previous_model_symbols:
            with ctl.backend() as backend:
                for atom in ctl.symbolic_atoms:
                    sym_str = str(atom.symbol)
                    if sym_str in previous_model_symbols:
                        backend.add_heuristic(atom.literal, clingo.HeuristicType.True_, 100, 100, [])
                    else:
                        backend.add_heuristic(atom.literal, clingo.HeuristicType.False_, 100, 100, [])

        ground_time = time.time() - ground_start

        solve_start = time.time()
        best_model = []
        timed_out = False

        remaining_timeout = timeout_per_instance - (time.time() - instance_start)
        if remaining_timeout <= 0:
            timed_out = True
        else:
            try:
                with ctl.solve(
                    yield_=True, async_=False
                ) as handle:
                    for model in handle:
                        if model.optimality_proven:
                            best_model = [str(s) for s in model.symbols(shown=True)]
                            break
                        else:
                            best_model = [str(s) for s in model.symbols(shown=True)]

                        elapsed = time.time() - instance_start
                        if elapsed > timeout_per_instance:
                            timed_out = True
                            break
            except RuntimeError:
                timed_out = True

        solve_time = time.time() - solve_start
        total_time = time.time() - instance_start

        if timed_out:
            total_time = 9999999999
            solve_time = 9999999999

        if best_model:
            previous_model_symbols = set(best_model)

            print("Answer: 1", file=sys.stdout)
            print(" ".join(best_model), file=sys.stdout)
            print("SATISFIABLE", file=sys.stdout)
        else:
            print("UNSATISFIABLE", file=sys.stdout)

        print("<END>", file=sys.stdout)
        sys.stdout.flush()

        print(
            f"{index};{load_time:.6f};{ground_time:.6f};{solve_time:.6f};{total_time:.6f};0",
            file=sys.stderr,
        )

        sum_total += total_time
        sum_load += load_time
        sum_ground += ground_time
        sum_solve += solve_time

        if timed_out:
            break

    return sum_total, sum_load, sum_ground, sum_solve


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clingo Python API incremental heuristic solver.")
    parser.add_argument("template", help="Path to template.xml")
    parser.add_argument("timeout", type=int, nargs="?", default=1500, help="Timeout per instance (default: 1500)")
    parser.add_argument(
        "--no-heuristic",
        action="store_false",
        dest="use_heuristic",
        help="Disable the incremental heuristic (use Clingo's default heuristic)",
    )
    parser.set_defaults(use_heuristic=True)

    args = parser.parse_args()

    run_benchmark(args.template, args.timeout, args.use_heuristic)