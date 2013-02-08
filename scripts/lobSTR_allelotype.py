def usage():
    print """
To train the genotyping noise model from a set of aligned reads:
python lobSTR_allelotype.py train [OPTIONS] --bam <input.bam> --out <output_prefix>

To run STR profiling on a set of aligned reads:
python lobSTR_allelotype.py classify [OPTIONS] --bam <input.bam> --noise_model  <noisemodel.txt> [--rmdup] --out <output_prefix> --sex [M|F]

To run training and classification on a set of aligned reads:
python lobSTR_allelotype.py both [OPTIONS] --bam <input.bam> --noise_model <noisemodel.txt> [--rmdup] --out <output_prefix> --sex [M|F]

To allelotyping without using a stutter noise model:
python lobSTR_allelotype.py simple [OPTIONS] --bam <input.bam> [--rmdup] --out <output_prefix> --sex [M|F]

Options:
--no-rmdup: don't remove pcr duplicates before genotyping
-u: filter all reads differing by non unit copy number

***NOTE*** bam file MUST be sorted and indexed using:
samtools sort [-on] [-m <maxMem>] <in.bam> <out.prefix>
samtools index <out.prefix.bam>

"""
import os 
import sys
import getopt
from  genotyper_utils import *

try:
    command = sys.argv[1]
except: command = "--help"

if command not in ["train", "classify", "both","simple"]:
    usage()
    if command != "--help" and command != "-h":
        print "command %s invalid"%command
    sys.exit(2)
try:
    opts, args = getopt.getopt(sys.argv[2:], "hvu", ["help","bam=", "noise_model=", "no-rmdup", "out=","sex=","verbose","notlob"])
except getopt.GetoptError, err:
    # print help information and exit:
    print str(err) # will print something like "option -a not recognized"
    usage()
    sys.exit(2)
args = [item[0] for item in opts]

min_het_freq = 0.25

if command == "train":
    if (not("--bam" in args and "--out" in args)):
        usage()
        sys.exit(2)
if command == "classify":
    if (not("--bam" in args and "--noise_model" in args and "--out" in args and "--sex" in args)):
        usage()
        sys.exit(2)
if command == "both":
    if (not("--bam" in args and "--out" in args and "--sex" in args)):
        usage()
        sys.exit(2)
if command == "simple":
    if (not("--bam" in args and "--out" in args and "--sex" in args)):
        usage()
        sys.exit(2)


# initialize variables
bam_file = ""
noise_model = NoiseModel()
rmdup = True
prefix = ""
sex = "M"
verbose = False
notlob = False
unit = False

# get values from arguments
for o,a in opts:
    if o == "--verbose" or o == "-v": verbose = True
    if o == "-u": unit = True
    if o == "--bam": bam_file = a
    if o == "--noise_model":
        noise_model.ReadFromFile(a)
    if o == "--no-rmdup": rmdup = False
    if o == "--out": prefix = a
    if o == "--sex":
        sex = a
        if sex not in ["M", "F"]:
            usage()
            print "sex must be 'M' or 'F'"
            sys.exit(2)
    if o == "--notlob":
        notlob = True
    if o == "--help" or o == "-h": 
        usage()
        sys.exit(2)

if command == "train" or command == "both":
    if sex == "F": 
        usage()
        print "cannot train on female sample... need homozygous chrX and chrY for training"
        sys.exit(2)

def main():
    print "Running allelotyping with command %s"%command
    nm = noise_model
    # 1. Add reads to read container
    if verbose:
        print "Adding reads to read container..."
    read_container = ReadContainer()
    read_container.AddReadsFromFile(bam_file, unit = unit)

    # 2. Perform pcr dup removal if specified
    if (rmdup):
        if verbose:
            print "Performing pcr duplicate removal..."
        read_container.RemovePCRDuplicates()

    # 3. Train/classify
    if command == "train" or command == "both":
        if verbose:
            print "Training noise model..."
        nm = NoiseModel(read_container = read_container)
        nm.train()
        nm.WriteToFile("%s.noisemodel.txt"%prefix)
    if command == "classify" or command == "both":
        if verbose:
            print "Classifying genotypes..."
        genotyper = Genotyper(nm, sex)
        genotyper.genotype(read_container, "%s.genotypes.tab"%prefix)
    if command == "simple":
        genotyper = Genotyper(nm, sex, simple = True)
        genotyper.genotype(read_container, "%s.genotypes.tab"%prefix, simple = True)

main()