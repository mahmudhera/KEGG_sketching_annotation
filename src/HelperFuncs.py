import os
import subprocess
import re
from collections import Counter
import numpy as np
import pandas as pd
import pathlib
import tempfile
from os.path import exists
import multiprocessing
import matplotlib.pyplot as plt

bbtools_loc = os.path.abspath("../utils/bbmap")
diamond_loc = os.path.abspath("../utils/")


def run_simulation(reference_file, out_file, num_reads, len_reads=150, noisy=False, num_orgs=250):
    """
    This function runs a simulation using bbtools "randomreads.sh"
    :param reference_file: The input sequences from which to make a metagenome
    :param out_file: the name of the output simulation (must be a FASTQ file, so ending in fq or fastq)
    :param num_reads: number of reads to simulate
    :param len_reads: how long the reads are (default is 150bp)
    :param noisy: flag if you want noise injected to the simulation
    :param num_orgs: specify the number of organisms/genes/proteins/etc. to include in the simulation
    :return: None
    """
    # First subsample the database so there are only num_orgs in the new reference file
    with tempfile.NamedTemporaryFile(suffix=pathlib.Path(reference_file).suffix) as subsample_ref_file:
    #with open('/tmp/test.faa', 'w') as subsample_ref_file:
        # do the subsampling
        cmd = f"{bbtools_loc}/./reformat.sh in={reference_file} out={subsample_ref_file.name} ow=t " \
              f"samplereadstarget={num_orgs} ignorejunk=t iupacToN=f crashjunk=f fixjunk=f"
        res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        if res.returncode != 0:
            raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
        # then generate the metagenome
        cmd = f"{bbtools_loc}/./randomreads.sh "
        # Things we always want set to true
        simple_names = "t"
        illumina_names = "f"
        overwrite = "t"
        metagenome = "t"
        banns = "t"
        # Note: reads by default are exactly 150bp long, not paired
        cmd += f"simplenames={simple_names} overwrite={overwrite} illuminanames={illumina_names} metagenome={metagenome} banns={banns} "
        if noisy:
            # TODO: hard code these for now, look up realistic values later
            snprate = 0.01
            insrate = 0.01
            delrate = 0.01
            subrate = 0.01
            nrate = 0.01
            cmd += f"snprate={snprate} insrate={insrate} delrate={delrate} subrate={subrate} nrate={nrate} "
        else:
            cmd += f"snprate=0 insrate=0 delrate=0 subrate=0 nrate=0 maxsnps=0 maxinss=0 maxdels=0 maxsubs=0 maxns=0 adderrors=f "
        cmd += f"ref={subsample_ref_file.name} out={out_file} reads={num_reads} length={len_reads} "
        res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        if res.returncode != 0:
            raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
    return


def make_sketches(ksize, scale_factor, file_name, sketch_type, out_dir, per_record=False):
    """
    This helper function will create the signature/sketches using sourmash
    :param ksize: the k-size to use
    :param scale_factor: the denominator of the scale factor to use (so >=1)
    :param file_name: the file to sketch
    :param sketch_type: amino acid (aa, protein) or nucleotide (nt, dna)
    :param out_dir: Where to write the signature
    :param per_record: If you want sketches of each entry in the fasta file, or just of the full fasta file (default: False)
    :return: None
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    out_file = f"{os.path.join(out_dir, os.path.basename(file_name))}_k_{ksize}_scale_{scale_factor}.sig"
    if sketch_type == 'aa' or sketch_type == 'protein':
        sketch_type = "protein"
    elif sketch_type == 'nt' or sketch_type == 'dna':
        sketch_type = "dna"
    # Don't include this last line so we can work with translated DNA->Protein as well
    #else:
    #    raise Exception(f"Sketch_type must be one of 'aa' or 'nt. I was given {sketch_type}")
    if per_record:
        cmd = f"sourmash sketch {sketch_type} -f -p k={ksize},scaled={scale_factor},abund -o {out_file} --singleton {file_name}"
    else:
        cmd = f"sourmash sketch {sketch_type} -f -p k={ksize},scaled={scale_factor},abund -o {out_file} {file_name}"
    res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    if res.returncode != 0:
        raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
    return


def run_sourmash_gather(query, database, out_file, sketch_type, num_results=None, threshold_bp=1000, quiet=True):
    """
    This is a simple wrapper for sourmash gather. It is hard coded to ignore abundances, estimate the
    ani and ci, as well as not perform the prefetch steps.
    :param query: file containing the query sketch/signature
    :param database: file containing the database sketch/signature
    :param out_file: the output csv file with the results
    :param sketch_type: aa (for amino acid) or nt (for nucleotide)
    :param num_results: int, if you only want the top N results
    :param threshold_bp: int, stop the algorithm once the overlap is below this many base pairs
    :return:
    """
    ignore_abundance = False
    estimate_ani_ci = True
    no_prefetch = False  # if set to true, this will disable the prefetch step. This will result in a much slower execution since prefetch does a pre-filtering step to select only database entries relevant to the sample
    if sketch_type not in ['aa', 'nt', 'protein', 'dna']:
        raise Exception(f"sketch type must be one of aa or protein (amino acid) or nt or dna (nucleotide). Provided value was {sketch_type}")
    cmd = f"sourmash gather -o {out_file} "
    if ignore_abundance:
        cmd += "--ignore-abundance "
    if estimate_ani_ci:
        cmd += "--estimate-ani-ci "
    if no_prefetch:
        cmd += "--no-prefetch "
    if sketch_type == 'aa' or sketch_type == 'protein':
        cmd += "--protein "
    elif sketch_type == 'nt' or sketch_type == 'dna':
        cmd += "--dna "
    if num_results:
        cmd += f"--num-results {num_results} "
    if threshold_bp:
        cmd += f"--threshold-bp {threshold_bp} "
    if quiet:
        cmd += "-q "
    cmd += f"{query} {database}"
    res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    if res.returncode != 0:
        raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
    return



def check_extension(file_name):
    """
    Checks the file extension to see if it's protein or dna
    :param file_name: file name to check
    :return: 'protein' or 'dna'
    """
    suffix = pathlib.Path(file_name).suffix
    sketch_type = ""
    if suffix == ".fna":
        sketch_type = "dna"
    elif suffix == ".faa":
        sketch_type = "protein"
    else:
        raise Exception(f"Unknown extension {suffix}.")
    return sketch_type


def build_diamond_db(input_file, output_database):
    """
    This function is a simple wrapper for DIAMOND to create a reference database from protein sequences
    :param input_file: input reference FASTA file
    :param output_database: output database file (in DIAMOND binary format)
    :return: none
    """
    # DIAMOND will not automatically create folders
    if not exists(os.path.dirname(output_database)):
        os.makedirs(os.path.dirname(output_database))
    cmd = f"{diamond_loc}/./diamond makedb --in {input_file} -d {output_database}"
    res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    if res.returncode != 0:
        raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
    return


def run_diamond_blastx(query_file, database_file, out_file, num_threads=multiprocessing.cpu_count()):
    """
    This is a simple wrapper to take a metagenome/query file `query_file` that contains DNA sequences,
    translate it to protein space, and then align against the database file.
    :param query_file: Input FASTA/Q query file
    :param database_file: The database built with build_diamond_db
    :param out_file: The output tsv file. Format is:
    qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore
    :param num_threads: Number of threads to run (default=number of CPU cores on the machine you are using)
    :return: none
    """
    cmd = f"{diamond_loc}/./diamond blastx -d {database_file} -q {query_file} -o {out_file} -p {num_threads}"
    res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    if res.returncode != 0:
        raise Exception(f"The command {cmd} exited with nonzero exit code {res.returncode}")
    return


def parse_diamond_results(matches_file):
    """
    This parses the DIAMOND output csv file and returns some values about the results.
    :param matches_file: the output csv file from DIAMOND
    :return: 3-tuple: a) the set of gene identifiers that DIAMOND predicted to be in the sample
    b) the number of correct alignments (diamond aligned the read to the correct reference sequence)
    c) the number of incorrect alignments  (diamond aligned the read to the wrong reference sequence)
    """
    df = pd.read_csv(matches_file, sep='\t', header=0,
                       names=["qseqid", "sseqid", "pident", "length", "mismatch", "gapopen", "qstart", "qend", "sstart",
                              "send", "evalue", "bitscore"])
    query_names = list(df['qseqid'])
    regex = r'\_\.\_([a-z]{3}:[a-zA-Z]\w+)'
    regexc = re.compile(regex)
    query_ids = [re.findall(regexc, x)[0] for x in query_names]
    ref_ids = [x.split('|')[0] for x in df['sseqid']]
    if len(query_ids) != len(ref_ids):
        raise Exception(f"Something went wrong: there are {len(query_ids)} query ids, but {len(ref_ids)} ref ids.")
    inferred_ids = set()
    n_correct_alignments = 0
    n_incorrect_alignments = 0
    for true_id, inf_id in zip(query_ids, ref_ids):
        inferred_ids.add(inf_id)
        if true_id == inf_id:
            n_correct_alignments += 1
        else:
            n_incorrect_alignments += 1
    return inferred_ids, n_correct_alignments, n_incorrect_alignments


def calculate_sourmash_performance(gather_file, ground_truth_file, filter_threshold):
    """
    This function will parse the output from sourmash gather and turn it into a functional profile that we can compare
    to the ground truth.
    From the check_sourmash_correlation method, it appears that:
     f_unique_weighted correlates with reads mapped, median, mean coverage, and nucleotide_overlap

    :param gather_file: the csv output from sourmash
    :param ground_truth_file: the ground truth file (output from find_genes_in_sim.py)
    :param filter_threshold: ignore ground truth genes that have less than this many reads in the ground truth
    :return: a dataframe containing the performance characteristics of the sourmash results
    """
    if not os.path.exists(gather_file):
        raise Exception(f"File {gather_file} does not exist")
    if not os.path.exists(ground_truth_file):
        raise Exception(f"File {ground_truth_file} does not exist")

    sourmash_rel_abund_col = 'f_unique_weighted'
    ground_truth_rel_abund_col = 'reads_mapped'

    # s prefix is for "sourmash" while g prefix is for "ground truth"
    sdf = pd.read_csv(gather_file)
    gdf = pd.read_csv(ground_truth_file)
    # sort the ground truth by gene name, this will be the order that we stick with
    gdf = gdf.sort_values(by='gene_name')

    # remove the infrequent genes from the ground truth and from sourmash
    gdf = gdf[gdf['reads_mapped'] >= filter_threshold]
    # TODO: we may want to remove these from the sourmash results to, since otherwise it could artificially increase the FP rate


    # grab the sourmash infered gene names
    sgene_names = list(sdf['name'])
    sgene_names = [x.split('|')[0] for x in sgene_names]
    # replace the name column with the sourmash gene names
    sdf['name'] = sgene_names
    ggene_names = list(gdf['gene_name'])
    greads_mapped = np.sum(list(gdf['reads_mapped']))
    # subset the gather results to concentrate on the ones in the ground truth
    sdf_TP = sdf[sdf['name'].isin(ggene_names)]  # true positives in sourmash
    sdf_TP = sdf_TP.sort_values(by='name')  # sort by gene name
    sdf_FP = sdf[~sdf['name'].isin(ggene_names)]  # false positives in sourmash
    sdf_FN = gdf[~gdf['gene_name'].isin(sgene_names)]  # false negatives (ones in ground truth that aren't in sourmash)
    print(f"Out of {len(sdf)} sourmash results, TP={len(sdf_TP)} are in the ground truth, FP={len(sdf_FP)} are not, "
          f"and there are FN={len(sdf_FN)} in the ground truth that are not in the sourmash results")
    # subset the ground truth to only the ones in the gather results
    gdf_TP = gdf[gdf['gene_name'].isin(sgene_names)]  # subset the ground truth to concentrate on the ones in the gather results
    gdf_TP = gdf_TP.sort_values(by='gene_name')
    metrics = ['TP', 'FP', 'FN', 'precision', 'recall', 'F1', 'corr', 'L1_f_unique_weighted_reads_mapped', 'percent_correct_predictions', 'total_number_of_predictions']
    # calculate the performance metrics
    performance = dict()
    performance['TP'] = len(sdf_TP)
    performance['FP'] = len(sdf_FP)
    performance['FN'] = len(sdf_FN)
    performance['precision'] = performance['TP'] / float(performance['TP'] + performance['FP'])
    performance['recall'] = performance['TP'] / float(performance['TP'] + performance['FN'])
    if performance['TP']:
        performance['F1'] = 2 * performance['precision'] * performance['recall'] / float(performance['precision'] + performance['recall'])
    else:
        performance['F1'] = 0
    performance['corr'] = np.corrcoef(sdf_TP[sourmash_rel_abund_col], gdf_TP[ground_truth_rel_abund_col])[0][1]
    sdf_TP_vec = np.array(sdf_TP[sourmash_rel_abund_col].values)
    sdf_TP_vec = sdf_TP_vec / np.sum(sdf_TP_vec)
    gdf_TP_vec = np.array(gdf_TP[ground_truth_rel_abund_col].values)
    gdf_TP_vec = gdf_TP_vec / np.sum(gdf_TP_vec)
    performance['L1_f_unique_weighted_reads_mapped'] = np.sum(np.abs(sdf_TP_vec - gdf_TP_vec))
    performance['percent_correct_predictions'] = len(sdf_TP) / float(len(sdf_TP) + len(sdf_FP))
    performance['total_number_of_predictions'] = len(sdf_TP) + len(sdf_FP)
    print(performance)
    # TODO: decide if we want just these metrics, or if we want to iterate over a bunch of filter_threshold
    # TODO: so just print these for now


def check_sourmash_correlation(gather_file, ground_truth_file, corr_threshold=0.9):
    """
    Since we don't know which columns of sourmash gather correlate with which columns of the ground truth, we need to
    just check them all
    :param gather_file: results of sourmash gather
    :param ground_truth_file: the output of find_genes_in_sim.py
    :param corr_threshold: only print out stats if the correlation coef is above this threshold
    :return: None
    """

    if not os.path.exists(gather_file):
        raise Exception(f"File {gather_file} does not exist")
    if not os.path.exists(ground_truth_file):
        raise Exception(f"File {ground_truth_file} does not exist")
    # s prefix is for "sourmash" while g prefix is for "ground truth"
    sdf = pd.read_csv(gather_file)
    gdf = pd.read_csv(ground_truth_file)
    # sort the ground truth by gene name, this will be the order that we stick with
    gdf = gdf.sort_values(by='gene_name')
    # grab the sourmash infered gene names
    sgene_names = list(sdf['name'])
    sgene_names = [x.split('|')[0] for x in sgene_names]
    # replace the name column with the sourmash gene names
    sdf['name'] = sgene_names
    ggene_names = list(gdf['gene_name'])
    greads_mapped = np.sum(list(gdf['reads_mapped']))
    # subset the gather results to concentrate on the ones in the ground truth
    sdf_TP = sdf[sdf['name'].isin(ggene_names)]  # true positives in sourmash
    sdf_TP = sdf_TP.sort_values(by='name')  # sort by gene name
    sdf_FP = sdf[~sdf['name'].isin(ggene_names)]  # false positives in sourmash
    sdf_FN = gdf[~gdf['gene_name'].isin(sgene_names)]  # false negatives (ones in ground truth that aren't in sourmash)
    print(f"Out of {len(sdf)} sourmash results, TP={len(sdf_TP)} are in the ground truth, FP={len(sdf_FP)} are not, "
          f"and there are FN={len(sdf_FN)} in the ground truth that are not in the sourmash results")
    # subset the ground truth to only the ones in the gather results
    gdf_TP = gdf[gdf['gene_name'].isin(sgene_names)]  # subset the ground truth to concentrate on the ones in the gather results
    gdf_TP = gdf_TP.sort_values(by='gene_name')  # sort by gene name
    # iterate over all the columns of the gather results and return the correlation coefficient with the number of reads mapped
    ground_truth_cols = ['nucleotide_overlap', 'median_coverage', 'mean_coverage', 'reads_mapped']
    sourmash_cols = ['intersect_bp', 'f_orig_query', 'f_match', 'f_unique_to_query',
                     'f_unique_weighted', 'average_abund', 'median_abund', 'std_abund',
                     'f_match_orig', 'unique_intersect_bp',
                     'gather_result_rank', 'remaining_bp']
    for gt_col in ground_truth_cols:
        for col in sourmash_cols:
            corr = np.corrcoef(sdf_TP[col], gdf_TP['reads_mapped'])[0][1]
            if corr > corr_threshold:
                print(f"gt: {gt_col}, sm:{col}: corr={corr}")

# TODO: calculate weighted stats. Need to understand what the difference columns in the sourmash gather results are actually returning