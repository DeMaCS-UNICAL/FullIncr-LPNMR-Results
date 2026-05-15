#!/usr/bin/env python3

import pandas as pd
import os
import sys

def get_problem_folder_name(name):
    clean_name = str(name)
    if clean_name.startswith('problems/'):
        clean_name = clean_name[len('problems/'):]
    clean_name = clean_name.replace('/input.xml', '')
    clean_name = clean_name.replace('/inp.txt', '')
    clean_name = clean_name.replace('/template.xml', '')
    return clean_name.replace('/', '_')

def process_results():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'results.csv'
    output_dir = 'results'
    
    try:
        df = pd.read_csv(input_file, sep=';', usecols=[0, 1, 2, 3, 4, 5, 6, 7], 
                         names=['timestamp', 'solver', 'name', 'instance_number', 'load', 'ground', 'solve', 'total'],
                         header=0)
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    metrics = {
        'load': 'load',
        'ground': 'ground',
        'solve': 'solve',
        'total': 'total'
    }
    
    for name, group in df.groupby('name'):
        folder_name = get_problem_folder_name(name)
        folder_path = os.path.join(output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        for file_prefix, col_name in metrics.items():
            pivot_df = group.pivot_table(index='instance_number', columns='solver', values=col_name)
            
            csv_path = os.path.join(folder_path, f"{file_prefix}.csv")
            pivot_df.to_csv(csv_path)
            
    print(f"Successfully processed results into '{output_dir}' folder.")

if __name__ == '__main__':
    process_results()
