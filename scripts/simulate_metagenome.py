#!/usr/bin/env python
import argparse
import os, sys
from os import listdir
from os.path import isfile, join
import subprocess
import re
import numpy as np
from collections import Counter
# for relative imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from src.HelperFuncs import run_simulation, compute_rel_abundance

bbtools_loc = os.path.abspath("../utils/bbmap")


def main():
    parser = argparse.ArgumentParser(description="This script uses BBTools randomreads.sh to simulate reads from a"
                                                 "metagenome.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', '--reference_file', type=str, help="Database that you want to generate reads from.")
    parser.add_argument('-o', '--out_file', type=str, help="The output simulated metagenome.")
    parser.add_argument('-n', '--num_reads', type=int, help="The number of reads to simulate.")
    parser.add_argument('-l', '--len_reads', type=int, help="The length of the reads to generate.", default=150)
    parser.add_argument("--noisy", action='store_true', help="If you want to inject noise in the simulated reads")
    # parse the args
    args = parser.parse_args()
    reference_file = os.path.abspath(args.reference_file)
    out_file = os.path.abspath(args.out_file)
    ext = out_file.split(".")[-1]
    if ext not in ["fq", "fastq"]:
        raise Exception(f"Output file extension must be one of fq or fastq. Yours was {ext}")
    num_reads = args.num_reads
    if not num_reads:
        raise Exception("Must specify the number of reads via --num_reads")
    len_reads = args.len_reads
    if not len_reads:
        raise Exception("Must specify the length of the reads via --len_reads")
    noisy = args.noisy
    # run the simulation
    run_simulation(reference_file, out_file, num_reads, len_reads, noisy=noisy)
    # For some really odd reason, some (but not all) of the underscores in the names are converted to left brackets {
    # So let's replace them back
    subprocess.run("sed -i 's/{/_/g' " + out_file, stdout=subprocess.PIPE, shell=True)
    matches_tally = compute_rel_abundance(out_file)
    # Save this for later use
    # Sort it first, descending order
    matches_tally_sorted = {k: v for k, v in sorted(matches_tally.items(), key=lambda item: -item[1])}
    with open(f"{out_file}.abund", 'w') as fid:
        for key, value in matches_tally_sorted.items():
            fid.write(f"{key}\t{value}\n")



if __name__ == "__main__":
    main()
