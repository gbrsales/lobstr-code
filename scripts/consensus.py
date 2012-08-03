debug = True
MINDIST = 0.85
MAXDIST = 0.05
EXTENDREF = 15
clustalw_exe = "clustalw2"
from nw import *
import sys
import os
import random
from Bio.Align.Applications import ClustalwCommandline

class Consensus:
    """
    Consensus: given the reads aligned to an STR locus, determine
    the consensus sequence of the two alleles present
    """

    def __init__(self, allele1, allele2, all_reads, ref):
        # keep track of the reference allele sequence
        self.ref_allele = ref
        self.allele1 = allele1
        self.allele2 = allele2
        # dictionary of (key: allele, value: list of aligned sequences)
        self.reads = {}
        # dictionary of ID -> nucleotides
        self.readIdToSeq = []
        count = 0
        for read in all_reads.split(","):
            sequence, allele, strand = read.split(":")[0:3]
            allele = int(allele)
            try:
                self.reads[allele].append(count)
            except:
                self.reads[allele] = [count]
            self.readIdToSeq.append(sequence)
            count = count + 1
        if debug: 
            print
            print "allele1", self.allele1
            print "allele2", self.allele2
            print "ref allele", self.ref_allele
            print "reads", self.reads
            for item in self.readIdToSeq: print item

        # get pairwise distances
        self.pairwise_distances = self.GetPairwiseDistances()
    
    def GetConsensusSequences(self):
        """
        Main function of Consensus class
        Get consensus sequences of each allele
        """

        if self.allele1 != self.allele2:
            reads1, reads2 = self.AssignReadsToTwoAlleles()
            seq1 = self.AlignReads(reads1)
            seq2 = self.AlignReads(reads2)
        else:
            num_alleles_present, reads1, reads2 = self.GetNumAlleles()
            if num_alleles_present == 1:
                seq1 = self.AlignReads(reads1)
                seq2 = seq1
            else:
                seq1 = self.AlignReads(reads1)
                seq2 = self.AlignReads(reads2)
        seq1_adjusted, seq1_cigar = self.AdjustAlignment(seq1)
        seq2_adjusted, seq2_cigar = self.AdjustAlignment(seq2)
        return seq1_adjusted, seq2_adjusted, seq1_cigar, seq2_cigar

    def GetDistance(self,seq1,seq2):
        """
        Get alignment distance between two sequences
        Uses NW with no end gap penalty
        """
        score = nw_noeg(seq1,seq2)
        return score

    def GetPairwiseDistances(self):
        """
        Given a set of reads, return pairwise distances 
        based on alignments
        """
        nseqs = len(self.readIdToSeq)
        pd = [[0]*nseqs for i in range(nseqs)]
        for i in range(nseqs):
            for j in range(i,nseqs):
                dist = self.GetDistance(self.readIdToSeq[i],self.readIdToSeq[j])
                pd[i][j] = dist
                pd[j][i] = dist
        if debug:
            print "pairwise distance matrix"
            for i in range(len(pd)): print pd[i]
        return pd

    def GetAvgDistance(self,read, reads):
        """ 
        Get average distance from one
        read to a set of reads
        """
        if len(reads) == 0: return 0
        dist = 0
        for item in reads:
            dist = dist + self.pairwise_distances[read][item]
        return dist*1.0/len(reads)
        
    def AssignReadsToTwoAlleles(self):
        """
        Given that the two alleles are different lengths, assign reads
        to the appropriate allele.
        """
        # start with reads already assigned to those alleles
        reads1 = self.reads[self.allele1]
        reads2 = self.reads[self.allele2]

        for read in range(len(self.readIdToSeq)):
            if read not in reads1 and read not in reads2:
                # get avg. dist to reads1
                dist1 = self.GetAvgDistance(read, reads1)
                # get avg. dist to reads2
                dist2 = self.GetAvgDistance(read, reads2)
                if max([dist1,dist2]) < MINDIST:
                    if debug:
                        sys.stderr.write("Read %s discarded\n"%self.readIdToSeq[read])
                elif dist1 > dist2:
                    reads1.append(read)
                else:
                    reads2.append(read)
        return reads1, reads2

    def AlignReads(self, read_list):
        """
        Perform multiple alignment on a list of sequences
        """
        if len(read_list) == 1: return self.readIdToSeq[read_list[0]]
        if len(read_list) == 0: return ""
        # make fasta file of sequences
        randint = random.randint(0,1000)
        fname="%s.fa"%randint
        f = open(fname,"w")
        for read in read_list:
            f.write(">%s\n"%read)
            f.write(self.readIdToSeq[read]+"\n")
        f.close()
        clustalw_cline = ClustalwCommandline(clustalw_exe,infile="%s.fa"%randint)
        clustalw_cline()
        alignment = self.ParseClustal("%s.aln"%randint)
        os.system("rm %s*"%randint)
        return alignment
    
    def ParseClustalGetSeqs(self, alnfile):
        """ 
        Parse clustal .aln file to get
        ref seq and allele seq
        """
        refseq = ""
        alleleseq = ""
        f = open(alnfile,"r")
        line = f.readline()
        block_seqs = []
        while line != "":
            if "CLUSTAL" in line:
                line = f.readline()
                while line.strip() == "":
                    line = f.readline()
            if line != "" and line.strip() == "":
                # process last block and start new one
                if len(block_seqs)>1:
                    refseq += block_seqs[0]
                    alleleseq += block_seqs[1]
                block_seqs = []
            else:
                if "*" not in line:
                    block_seqs.append(line.strip().split()[1])
            line = f.readline()
        # parse last block
        if len(block_seqs) > 1:
            refseq += block_seqs[0]
            alleleseq += block_seqs[1]
        return alleleseq, refseq

    def ParseClustal(self, alnfile):
        """ 
        Parse clustal .aln file to get
        consensus sequence
        """
        seq = ""
        f = open(alnfile,"r")
        line = f.readline()
        block_seqs = []
        while line != "":
            if "CLUSTAL" in line:
                line = f.readline()
                while line.strip() == "":
                    line = f.readline()
            if line != "" and line.strip() == "":
                # process last block and start new one
                if len(block_seqs)>0:
                    for i in range(len(block_seqs[0])):
                        chars = []
                        for b in range(len(block_seqs)):
                            newchar = block_seqs[b][i]
                            chars.append(newchar)
                        conchar = self.GetMajorityVote(chars)
                        if conchar != "-":
                            seq += conchar
                block_seqs = []
            else:
                if "*" not in line:
                    block_seqs.append(line.strip().split()[1])
            line = f.readline()
        # parse last block
        if len(block_seqs) > 0:
            for i in range(len(block_seqs[0])):
                chars = []
                for b in range(len(block_seqs)):
                    newchar = block_seqs[b][i]
                    if newchar != "-" and newchar != "N":
                        chars.append(newchar)
                conchar = self.GetMajorityVote(chars)
                seq += conchar
        return seq
    
    def GetMajorityVote(self, charlist):
        """
        Get majority vote from a list of characters
        """
        if len(charlist) == 0: return ''
        maxitem = ''
        maxcount = 0
        for item in set(charlist):
            num = charlist.count(item)
            if num>maxcount:
                maxitem = item
                maxcount = num
        return maxitem
        
    def MergeMostSimilar(self,pdmatrix):
        """
        Merge most similar entries in distance matrix
        """
        # find pair to merge
        minscore = 100
        s1 = -1
        s2 = -1
        for i in range(len(pdmatrix)):
            for j in range(i+1,len(pdmatrix)):
                score = pdmatrix[i][j]
                if score <= minscore:
                    minscore = score
                    s1 = i
                    s2 = j
        # merge closest pair s1 and s2
        nseqs = len(pdmatrix) - 1
        newpdmatrix = []
        # add all other rows, replacing dist to s1
        # and s2 with average
        for i in range(len(pdmatrix)):
            if i != s1 and i != s2:
                newrow = []
                for j in range(len(pdmatrix)):
                    if j != s1 and j != s2:
                        newrow.append(pdmatrix[i][j])
                newrow.append((pdmatrix[i][s1]+pdmatrix[i][s1])/2.0)
                newpdmatrix.append(newrow)
        # add row of s1/s2 merged
        newrow=[]
        for i in range(len(newpdmatrix)):
            newrow.append(newpdmatrix[i][-1])
        newrow.append(0)
        newpdmatrix.append(newrow)
        return newpdmatrix, s1, s2

    def GetNumAlleles(self):
        """
        Given that allele lengths are the same, determine how many
        alleles are present
        """
        # get all sequences with reported allele
        seqs = self.reads[self.allele1]
        if len(seqs) == 1:
            return 1, seqs, []
        tmp = [self.pairwise_distances[i] for i in seqs]
        newpd = []
        for item in tmp:
            newpd.append([1-item[i] for i in seqs])
        # repeatedly join most similar sequences
        names = [str(i) for i in range(len(newpd))]
        while len(newpd) > 2:
            newpd,s1,s2 = self.MergeMostSimilar(newpd)
            names = [str(names[i]) for i in range(len(names)) if i != s1 and i !=s2] + [names[s1]+":"+names[s2]]
        if newpd[0][1]> MAXDIST:
            return 2, [int(item) for item in names[0].split(":")], [int(item) for item in names[1].split(":")]
        else:
            return 1, seqs,[]

    def AdjustAlignment(self, sequence):
        """
        Adjust alignment to have the same start and end coordinates as 
        the reference allele.
        """
        # Clustalw alignment of ref vs. allele
        randint = random.randint(0,10000)
        f = open("%s.fa"%randint,"w")
        f.write(">ref\n")
        f.write(self.ref_allele+"\n")
        f.write(">allele\n")
        f.write(sequence+"\n")
        f.close()
        clustalw_cline = ClustalwCommandline(clustalw_exe,infile="%s.fa"%randint,endgaps=True,gapopen=8,pairgap=5,pwgapopen=8,gapext=0.0)
        if debug:
            print clustalw_cline
        clustalw_cline()
        allele, ref = self.ParseClustalGetSeqs("%s.aln"%randint)
        os.system("rm %s*"%randint)
        if debug:
            print "allele",allele
            print "ref   ",ref
        # remove end gaps from ref
        i = 0
        while ref[i] == "-":
            i = i + 1
        ref = ref[i:]
        allele = allele[i:]
        i = len(allele)-1
        while ref[i] == "-":
            i = i-1
        ref = ref[:i+1]
        allele = allele[:i+1]
        # remove extra 10 flanking added to ref
        numrev = 0
        i = 0
        while numrev < EXTENDREF:
            if ref[i] != "-":
                numrev = numrev + 1
            i = i+1
        ref = ref[i:]
        allele = allele[i:]
        i = len(ref)-1
        numrev = 0
        while numrev < EXTENDREF:
            if ref[i] != "-":
                numrev = numrev + 1
            i = i-1
        ref = ref[:i+1]
        allele = allele[:i+1]

        # make cigar score (use m to indicate SNP)
        cigar = []
        for i in range(len(allele)):
            if allele[i] == ref[i]: cigar.append("M")
            elif allele[i] == "-": cigar.append("D")
            elif ref[i] == "-": cigar.append("I")
            else: cigar.append("m")
        if len(cigar) == 0: return "",""
        if len(cigar) == 1: return allele, cigar[0]
        cigarstring = ""
        curcount = 1
        curchar = cigar[0]
        for i in range(1,len(cigar)):
            newchar = cigar[i]
            if newchar != curchar:
                cigarstring = cigarstring + str(curcount)+curchar
                curcount = 1
                curchar = newchar
            else:
                curcount = curcount + 1
        cigarstring = cigarstring + str(curcount)+curchar
        allele = allele.replace("-","")
        if debug:
            print "aligned allele", allele
            print "aligned ref   ", ref
            print "cigar string", cigarstring
            print
        return allele, cigarstring
