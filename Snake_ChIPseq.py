# ---------------------------------------------------------------------------- #
import glob
import fnmatch
import os
import re
import sys
import yaml

# from SnakeFunctions import *
include: 'SnakeFunctions.py'
from Check_Config import *
localrules: makelinks

BASEDIR           = workflow.basedir
SCRIPT_PATH       = os.path.join(BASEDIR,'Scripts')
RULES_PATH        = os.path.join(BASEDIR,'Rules')
PARAMS_PATH       = '.'
SETTINGS_NAME     = 'settings.yaml'
SAMPLE_SHEET_NAME = 'sample_sheet.yaml'


# ---------------------------------------------------------------------------- #
# check config validity
if check_config(config) == 1:
    quit()

# ---------------------------------------------------------------------------- #
# settings input
with open(os.path.join(BASEDIR, SETTINGS_NAME), 'r') as stream:
    SETTINGS = yaml.load(stream)

# sample sheet input    
with open(os.path.join(BASEDIR, SAMPLE_SHEET_NAME), 'r') as stream:
    SAMPLE_SHEET = yaml.load(stream)


# Function parameter
APP_PARAMS = SOFTWARE_CONFIG['params']

# Software executables
TOOLS = SETTINGS['tools']
SOFTWARE = [TOOLS[tool_name]['executable'] for tool_name in TOOLS.keys()]
SOFTWARE = dict(zip(TOOLS.keys(), SOFTWARE))

# ---------------------------------------------------------------------------- #
# Variable definition
GENOME       = config['genome']['name']
GENOME_FASTA = config['genome']['fasta']
NAMES        = config['samples'].keys()
PEAK_NAMES   = config['peak_calling'].keys()
PATH_FASTQ   = config['fastq']
PARAMS       = config['params']
ANNOTATION   = config['annotation']


# Directory structure definition
PATH_MAPPED     = 'Mapped/Bowtie'
PATH_QC         = 'FastQC'
PATH_INDEX      = 'Bowtie2_Index'
PATH_LOG        = 'Log'
PATH_PEAK       = 'Peaks/MACS2'
PATH_BW         = 'BigWig'
PATH_IDR        = 'Peaks/IDR'
PATH_HUB        = 'UCSC_HUB'
PATH_ANALYSIS   = "Analysis"
PATH_ANNOTATION = 'Annotation'


# Directory structure for saved R objects
PATH_RDS            = os.path.join(PATH_ANALYSIS, 'RDS')
PATH_RDS_ANNOTATION = os.path.join(PATH_RDS, 'Annotation')
PATH_RDS_FEATURE    = os.path.join(PATH_RDS, 'Feature_Combination')
PATH_RDS_TEMP       = os.path.join(PATH_RDS, 'Temp')


# Hub variables which describe the types of files that can be used in the hub
TRACK_PATHS = {
    'bigWig' : {'path': PATH_MAPPED, 'suffix': 'bw', 'type':'bigWig'},
    'macs' :{'path': PATH_PEAK, 'suffix': 'bb', 'type':'bigBed'},
    'idr' : {'path': PATH_IDR, 'suffix': 'IDR.narrowPeak'}
}

# Collects the locations of all peaks
PEAK_NAME_LIST = {}

#
# ---------------------------------------------------------------------------- #
# config defaults
if not ('extend' in config['params'].keys()):
    config['params']['extend'] = 0


if GENOME_FASTA == None:
    prefix_default = ''
    GENOME_FASTA = ''
else:
    prefix_default = os.path.join(PATH_INDEX, GENOME)


PREFIX = os.path.join(set_default('index', prefix_default, config), GENOME)
print(PREFIX)

# ----------------------------------------------------------------------------- #
# include rules
include: os.path.join(RULES_PATH, 'Mapping.py')
include: os.path.join(RULES_PATH, 'FastQC.py')
include: os.path.join(RULES_PATH, 'BamToBigWig.py')

# ----------------------------------------------------------------------------- #
# RULE ALL
COMMAND    = []
INDEX      = [PREFIX + '.1.bt2']
BOWTIE2    = expand(os.path.join(PATH_MAPPED, "{name}", "{name}.sorted.bam.bai"), name=NAMES)
CHRLEN     = [PREFIX + '.chrlen.txt']
FASTQC     = expand(os.path.join(PATH_QC,     "{name}", "{name}.fastqc.done"), name=NAMES)
BW         = expand(os.path.join(os.getcwd(), PATH_MAPPED, "{name}", "{name}.bw"),  name=NAMES)
LINKS      = expand(os.path.join(PATH_BW,  "{ex_name}.bw"),  ex_name=NAMES)

COMMAND = COMMAND + INDEX + BOWTIE2 + CHRLEN + BW + LINKS + FASTQC



# ----------------------------------------------------------------------------- #
if 'peak_calling' in set(config.keys()):
    if len(config['peak_calling'].keys()) > 0:
        MACS  = []
        QSORT = []
        suffix = 'narrowPeak'
        for name in PEAK_NAMES:
            suffix = get_macs2_suffix(name, config)

            MACS    = MACS  + [os.path.join(PATH_PEAK,  name, name + "_peaks." + suffix)]
            QSORT   = QSORT + [os.path.join(PATH_PEAK,  name, name + "_qsort.bed" )]
            PEAK_NAME_LIST[name] = QSORT[-1]
        
        include: os.path.join(RULES_PATH, 'Peak_Calling.py')
        COMMAND = COMMAND + MACS + QSORT

# # ----------------------------------------------------------------------------- #
if 'idr' in set(config.keys()):
    if len(config['idr'].keys()) > 0:
        IDR = []
        for name in config['idr'].keys():
            IDR = IDR + [os.path.join(PATH_IDR, name, name + ".bed")]
            PEAK_NAME_LIST[name] = IDR[-1]

        include: os.path.join(RULES_PATH, 'IDR.py')
        COMMAND = COMMAND + IDR

# # ----------------------------------------------------------------------------- #
HUB_NAME = None
if 'hub' in set(config.keys()):
    HUB_NAME = config['hub']['name']
    HUB = [os.path.join(PATH_HUB, HUB_NAME, 'done.txt')]
    BB  = expand(os.path.join(PATH_PEAK,  "{name}", "{name}.bb"),  name=config['peak_calling'].keys())

    include: os.path.join(RULES_PATH, 'UCSC_Hub.py')
    COMMAND = COMMAND + BB + HUB


# ---------------------------------------------------------------------------- #
gtf_index = 'gtf' in set(config['annotation'].keys())
if gtf_index:
    LINK_ANNOTATION    = [os.path.join(PATH_ANNOTATION, 'GTF_Link.gtf')]
    PREPARE_ANNOTATION = [os.path.join(PATH_ANNOTATION, 'Processed_Annotation.rds')]

    ANNOTATE_PEAKS     = expand(os.path.join(PATH_RDS_TEMP,'{name}','{name}.Annotate_Peaks.rds'), name=PEAK_NAMES)
    
#     EXTRACT_SIGNAL_ANNOTATION = expand(os.path.join(PATH_RDS_TEMP,'{name}','{name}.Extract_Signal_Annotation.rds'), name=PEAK_NAMES)    

#     include: os.path.join(RULES_PATH, 'Extract_Signal_Annotation.py')
    include: os.path.join(RULES_PATH, 'Prepare_Annotation.py')
    COMMAND = COMMAND + LINK_ANNOTATION + PREPARE_ANNOTATION + ANNOTATE_PEAKS 

# ---------------------------------------------------------------------------- #
if 'feature_combination' in set(config.keys()):
    FEATURE_NAMES = config['feature_combination'].keys()
    if len(FEATURE_NAMES) > 0:

        FEATURE = expand(os.path.join(PATH_RDS_FEATURE,'{name}_FeatureCombination.rds'), 
        name = FEATURE_NAMES)
    
    include: os.path.join(RULES_PATH, 'Feature_Combination.py')
    COMMAND = COMMAND + FEATURE

# ----------------------------------------------------------------------------- #
# extracts ChIP/Cont signal profiles around the peaks
# EXTRACT_SIGNAL_PEAKS = expand(os.path.join(PATH_RDS_TEMP,'{name}','{name}.Extract_Signal_Peaks.rds'), name=PEAK_NAMES)
# COMMAND = COMMAND + EXTRACT_SIGNAL_PEAKS


# ----------------------------------------------------------------------------- #
# if 'feature_combination' in set(config.keys()) and 'gtf' in set(config['annotation'].keys()


# ----------------------------------------------------------------------------- #
rule all:
    input:
        COMMAND
