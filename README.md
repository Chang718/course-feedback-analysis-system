# DTS114TC Coursework
This is software component of coursework for module DTS114TC, divided into Task1 and Task2.

## Project Structure
```
├── .github/workflows/     # GitHub Actions config (must be placed at repo root, originally part of Task2)
├── Task1/                 # Source code & docs for Task 1
├── Task2/                 # Source code & docs for Task 2
├── ai_in_se_cw.yml        # Conda environment configuration file
└── .gitignore             # Ignore private config and cache files
```

## Environment Setup
Create conda environment from yaml file:
```bash
conda env create -f ai_in_se_cw.yml
conda activate ai_in_se_cw
```
> This environment contains additional libraries not covered in course materials, required to run codes successfully.

## How to Run
- Task1: Check `Task1/README.md` for detailed usage
- Task2: Check `Task2/README.md` for detailed usage

## File Description
1. **.github/workflows/**
Workflow files are stored in repository root due to GitHub Actions path restriction, though functionally belongs to Task2.
2. **.gitignore**
Excludes `.env` confidential configuration files and redundant cache files.
