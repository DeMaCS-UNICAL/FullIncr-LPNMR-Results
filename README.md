# FullIncr-LPNMR-Results

Benchmark results for the LPNMR Paper about full incremental heuristics

The structure of the repository:
- the *bin* folder contains the binary files used during the testing.
- the *problems* folder contains the instances, encoding and other files for each benchmark
- the *benchmark_system.py* runs the benchmarks, with settings specified by the *config.json* file
- the *generate_csvs.py* script takes in input (from command line) the log file and makes the ordered folder structure of *results*
- *results* contains the result times of the test that we have done
- *requirements.txt* is the list of required python libraries.