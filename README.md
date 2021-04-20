Template project for Spine case studies
=======================================

This template can be used for creating Spine Toolbox projects that have
explicitly defined dependencies and can be shared easily. The README file consists
of two parts: first part gives instructions for setting up the project and the 
second part serves as a template for the final project README.


Setting up
----------

If you plan to use a binary distribution version of Spine Toolbox, please test 
your project using that distribution. In this case, you can skip the Python 
environment set-up.

### Python environment

A Python virtual environment is recommended for isolating the project dependecies. 
Package `virtualenv` is good for this. 

---
**Note for conda users**

If your main Python environment is managed by conda, please install virtualenv 
using `conda install virtualenv`.

If you already have a conda environment for Spine Toolbox, *do not* use that.
Just start with the base environment.

You *can* also create a new conda environment for the case study, but 
virtualenv is recommended because of not depending on additional software (conda).

---

Create a virtual environment for the project using

    > virtualenv .venv
    > .venv\Scripts\activate
    
On Linux, use `source venv/bin/activate`.

Edit file `requirements.txt` to match your project needs. You can start with the 
latest branch tips of the Spine packages (Engine, DB API and Toolbox), but after 
you have checked that everything works please freeze the versions of those packages 
to specific commits or (preferably) release tags to ensure future replicability.

Install Python packages to the virtual environment using

    (.venv) > pip install -r requirements.txt


### Julia environment

Edit file `.julia/Project.toml` to specify the required packages and their
exact versions. 
The version of SpineOpt to use is defined here.

Create a new Julia environment to `.julia/` with

    (.venv) > julia create_julia_env.jl
    
Also run `.julia/init.jl` to re-build PyCall if necessary.


### Spine Toolbox

You should now be able to launch Spine Toolbox using

    (.venv) > spinetoolbox
    
In the Toolbox settings, you need to set the active Julia project to the 
current project directory.


Preparing for distribution
----------------------------

Freeze the Python environment to make sure others will have the same packages. 
To write the pinned version numbers at the end of the requirements file, use

    (.venv) > pip freeze > requirements.txt
    
Edit this README file to include any project specific stuff below. The first part 
‘Setting up’ can be removed. Also the file *add_julia_packages.jl* can be removed 
once *Project.toml* and *Manifest.toml* have been created under *.julia/*

Files to include in the final project bundle:
- `requirements.txt`
- `.julia/Project.toml`
- `.julia/Manifest.toml`
- `.spinetoolbox/project.json`
- original data files needed for the project (preferably under `data/`)
- data processing scipts (preferably under `scripts/`)
- Julia scripts for SpineOpt (under e.g. `models/`)
- tool specification files

Files that can be omitted:
- `.venv/*`
- `create_julia_env.jl`
- local Spine data store files (`*.sqlite`) which are automatically populated
- result files
- log files


--------------------------------------------------------------------------------

Spine Case Study XY
===================

This is a Spine Toolbox project for ...


Instructions for use
--------------------

### Python environment

Python 3.7, pip 19.1 or higher and `virtualenv` package are required. Note: If 
your main Python environment is managed by conda, please install virtualenv using 
`conda install virtualenv`.

First create a Python virtual environment and activate it.

    > virtualenv .venv
    > .venv\Scripts\activate
    
On Linux, use `source .venv/bin/activate`.
    
Install Python dependencies.

    (.venv) > pip install -r requirements.txt
    
    
### Julia environment

Julia 1.2 is required.
    
Instantiate Julia environment with

    (.venv) > julia .julia/init.jl


### Spine Toolbox

You should now be able to launch Spine Toolbox using

    (.venv) > spinetoolbox
    
In the Toolbox settings, you need to set the active Julia project to the folder 
*.julia* in the current project directory.

